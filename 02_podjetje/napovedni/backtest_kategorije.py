import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
from sqlalchemy import text
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
from db_common import get_engine, ANALIZA_REKLAMACIJE_KAT

warnings.filterwarnings('ignore')

# Izpisi vsebujejo znake (─, –), ki jih privzeta Windows konzola (cp1250)
# ne zna kodirati — brez tega se skripta sesuje z UnicodeEncodeError.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 0. MySQL POVEZAVA ────────────────────────────────────────────────────────
# Nastavitve so v .env; stolpec kategorija je rekonstruiran iz vrsta_napake
# (glej db_common.py).

engine = get_engine()

# ── 1. NALOŽI PODATKE ────────────────────────────────────────────────────────

with engine.connect() as conn:
    df_cat = pd.read_sql(text(f"""
        SELECT
            YEAR(pr.datum_prejema) AS leto,
            ar.kategorija,
            COUNT(*)               AS stevilo
        FROM {ANALIZA_REKLAMACIJE_KAT} ar
        JOIN prejem_reklamacije pr ON pr.reklamacija_id = ar.reklamacija_id
        WHERE pr.datum_prejema IS NOT NULL
          AND ar.kategorija IS NOT NULL
          AND ar.kategorija != 'Nerazporejeno'
          AND YEAR(pr.datum_prejema) BETWEEN 2013 AND 2024
        GROUP BY YEAR(pr.datum_prejema), ar.kategorija
        ORDER BY leto
    """), conn)

years_all = sorted(df_cat['leto'].unique().tolist())
kategorije = sorted(df_cat['kategorija'].unique().tolist())
print(f"Leta: {years_all[0]}–{years_all[-1]}  |  Kategorije: {len(kategorije)}")

# ── 2. MODELI ────────────────────────────────────────────────────────────────

models = {
    'Linearna':    LinearRegression(),
    'Ridge':       Ridge(alpha=1.0),
    'Polinomska':  make_pipeline(PolynomialFeatures(degree=2), LinearRegression()),
}

# ── 3. WALK-FORWARD BACKTEST ─────────────────────────────────────────────────
# Začnemo s 4 leti treninga (2013–2016), napovemo 2017
# Potem dodajamo leto za letom do 2023 → napoved 2024

MIN_TRAIN = 4
all_results = []

print(f"\n── Walk-forward backtest (min. trening: {MIN_TRAIN} leta) ──\n")

for kat in kategorije:
    df_k = (df_cat[df_cat['kategorija'] == kat]
            .groupby('leto')['stevilo'].sum())
    y_all = np.array([int(df_k.get(yr, 0)) for yr in years_all])

    kat_short = kat.replace('Neskladnost ', '').replace(' komponent', '')
    print(f"── {kat_short} ──")
    print(f"{'Leto':>4} | {'N train':>7} | {'Dejanske':>8} | {'Linearna':>9} | "
          f"{'Ridge':>6} | {'Polinomska':>10} | {'Najboljši':>10} | {'Napaka':>7} | {'Napaka%':>8}")
    print("-" * 90)

    for i in range(MIN_TRAIN, len(years_all)):
        X_train = np.array(years_all[:i]).reshape(-1, 1)
        y_train = y_all[:i]
        X_test  = np.array([[years_all[i]]])
        y_test  = y_all[i]
        yr_test = years_all[i]

        # Izbor modela BREZ pogleda v testno leto: vsak model se najprej
        # natrenira brez zadnjega trening leta in oceni na njem (validacija),
        # nato se za končno napoved natrenira na celotnem treningu.
        # (Prejšnja verzija je "najboljšega" izbrala po dejanski testni
        # vrednosti, kar je uhajanje podatkov in optimistično pristrano.)
        preds, val_napake = {}, {}
        for mname, model in models.items():
            model.fit(X_train[:-1], y_train[:-1])
            val_pred = max(0, int(round(model.predict(X_train[-1:])[0])))
            val_napake[mname] = abs(val_pred - y_train[-1])

            model.fit(X_train, y_train)
            preds[mname] = max(0, int(round(model.predict(X_test)[0])))

        best_name = min(val_napake, key=val_napake.get)
        best_pred = preds[best_name]
        napaka    = y_test - best_pred
        napaka_pct = napaka / y_test * 100 if y_test > 0 else 0

        print(f"{yr_test:>4} | {i:>7} | {y_test:>8} | {preds['Linearna']:>9} | "
              f"{preds['Ridge']:>6} | {preds['Polinomska']:>10} | "
              f"{best_name:>10} | {napaka:>+7} | {napaka_pct:>+7.1f}%")

        all_results.append({
            'kategorija':   kat,
            'kat_short':    kat_short,
            'leto':         yr_test,
            'n_train':      i,
            'dejanske':     int(y_test),
            'linearna':     preds['Linearna'],
            'ridge':        preds['Ridge'],
            'polinomska':   preds['Polinomska'],
            'najboljsi':    best_name,
            'napoved':      best_pred,
            'napaka':       int(napaka),
            'napaka_pct':   round(napaka_pct, 1),
        })
    print()

df_bt = pd.DataFrame(all_results)

# ── 4. POVZETEK METRIK PO KATEGORIJAH ────────────────────────────────────────

print("\n── Povzetek metrik po kategorijah ──")
print(f"{'Kategorija':<35} {'N':>3} {'MAE':>6} {'MAPE':>7} {'RMSE':>7} {'Najboljši model':>15}")
print("-" * 75)

for kat in kategorije:
    sub = df_bt[df_bt['kategorija'] == kat]
    mae  = sub['napaka'].abs().mean()
    mape = sub['napaka_pct'].abs().mean()
    rmse = np.sqrt((sub['napaka']**2).mean())
    best = sub['najboljsi'].mode()[0]
    kat_s = kat.replace('Neskladnost ', '').replace(' komponent', '')
    print(f"{kat_s:<35} {len(sub):>3} {mae:>6.1f} {mape:>6.1f}% {rmse:>7.1f} {best:>15}")

# ── 5. IZVOZI CSV ────────────────────────────────────────────────────────────

df_bt.to_csv('fotona_backtest_kategorije.csv', index=False, encoding='utf-8-sig')
print("\nIzvoženo: fotona_backtest_kategorije.csv")

# ── 6. VIZUALIZACIJA ─────────────────────────────────────────────────────────

colors = {
    'Neskladnost optičnih komponent':     '#534AB7',
    'Neskladnost elektronskih komponent': '#0F6E56',
    'Neskladnost mehanskih komponent':    '#D85A30',
    'Ni tehnična napaka':                 '#888780',
    'Neskladnost enote za sprej':         '#BA7517',
    'Neskladnost hladilnega sistema':     '#185FA5',
}

imenovalnik = {
    'Neskladnost optičnih komponent':     'Optične komponente',
    'Neskladnost elektronskih komponent': 'Elektronske komponente',
    'Neskladnost mehanskih komponent':    'Mehanske komponente',
    'Neskladnost hladilnega sistema':     'Hladilni sistem',
    'Neskladnost enote za sprej':         'Enota za sprej',
    'Ni tehnična napaka':                 'Ni tehnična napaka',
}

# Paneli urejeni po velikosti kategorije (največ reklamacij zgoraj levo)
kategorije_graf = (df_cat.groupby('kategorija')['stevilo'].sum()
                   .sort_values(ascending=False).index.tolist())

fig = plt.figure(figsize=(10, 13))
gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.75, wspace=0.3, top=0.90)

for idx, kat in enumerate(kategorije_graf):
    row, col = divmod(idx, 2)
    ax = fig.add_subplot(gs[row, col])

    sub   = df_bt[df_bt['kategorija'] == kat]
    color = colors.get(kat, '#333')

    # Vse dejanske vrednosti (vključno s trening leti)
    df_k  = (df_cat[df_cat['kategorija'] == kat].groupby('leto')['stevilo'].sum())
    y_vse = [int(df_k.get(yr, 0)) for yr in years_all]
    ax.plot(years_all, y_vse, 'o-', color=color,
            linewidth=2, markersize=5, zorder=3)

    # Napovedi (samo testna leta)
    ax.plot(sub['leto'], sub['napoved'], 's--', color=color,
            linewidth=2, markersize=6, alpha=0.75)

    # Stolpci napak
    mae_kat = sub['napaka'].abs().mean()
    for _, r in sub.iterrows():
        c = '#e74c3c' if abs(r['napaka']) > 1.5 * mae_kat else 'gray'
        ax.plot([r['leto'], r['leto']], [r['dejanske'], r['napoved']],
                color=c, linewidth=1.5, alpha=0.6)

    # Označi outlierje
    outliers = sub[sub['napaka'].abs() > 1.5 * mae_kat]
    for _, r in outliers.iterrows():
        ax.annotate(f"{int(r['napaka']):+d}",
                    (r['leto'], (r['dejanske'] + r['napoved']) / 2),
                    textcoords='offset points', xytext=(6, 0),
                    fontsize=9, color='#e74c3c')

    # Meja učno / testno obdobje
    train_end = years_all[MIN_TRAIN - 1]
    ax.axvspan(years_all[0] - 0.4, train_end + 0.4, alpha=0.08, color='gray')
    ax.axvline(x=train_end + 0.5, color='gray', linestyle=':', linewidth=1, alpha=0.6)

    ax.set_title(f'{imenovalnik[kat]}\nMAE = {mae_kat:.0f}', fontsize=13)
    ax.set_xlabel('Leto', fontsize=12)
    ax.set_ylabel('Reklamacije', fontsize=12)
    ax.set_xticks(years_all)
    ax.tick_params(axis='x', rotation=45, labelsize=11)
    ax.tick_params(axis='y', labelsize=11)
    ax.grid(axis='y', alpha=0.2)

# Ena skupna legenda za celotno sliko (nevtralne barve, ker so paneli
# barvno kodirani po kategoriji)
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
legenda = [
    Line2D([0], [0], color='#444', marker='o', linestyle='-',
           linewidth=2, markersize=5, label='Dejanske'),
    Line2D([0], [0], color='#444', marker='s', linestyle='--',
           linewidth=2, markersize=6, label='Napoved'),
    Patch(facecolor='gray', alpha=0.2, label=f'Učno obdobje (prva {MIN_TRAIN} leta)'),
]
fig.legend(handles=legenda, loc='upper center', ncol=3, fontsize=12,
           frameon=False, bbox_to_anchor=(0.5, 0.99))

plt.savefig('fotona_backtest_kategorije.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_backtest_kategorije.png")

# ── 7. NAPAKA PO LETU (skupni backtest) ──────────────────────────────────────

fig2, ax2 = plt.subplots(figsize=(12, 4))
fig2.suptitle('Skupna napaka backtesta po letu (vse kategorije)',
              fontsize=12, fontweight='bold')

skupna = df_bt.groupby('leto').agg(
    skupna_dejanska=('dejanske', 'sum'),
    skupna_napoved=('napoved', 'sum')
).reset_index()
skupna['napaka'] = skupna['skupna_dejanska'] - skupna['skupna_napoved']
skupna['napaka_pct'] = skupna['napaka'] / skupna['skupna_dejanska'] * 100

mae_sk = skupna['napaka'].abs().mean()
bar_colors = ['#e74c3c' if abs(v) > 1.5 * mae_sk else '#534AB7'
              for v in skupna['napaka']]

bars = ax2.bar(skupna['leto'], skupna['napaka'], color=bar_colors, alpha=0.8, width=0.6)
ax2.axhline(0, color='black', linewidth=0.8)
ax2.axhline( mae_sk, color='gray', linewidth=1, linestyle='--', alpha=0.6, label=f'+MAE ({mae_sk:.0f})')
ax2.axhline(-mae_sk, color='gray', linewidth=1, linestyle='--', alpha=0.6, label=f'-MAE ({mae_sk:.0f})')

for bar, (_, r) in zip(bars, skupna.iterrows()):
    ypos = bar.get_height() + 3 if bar.get_height() >= 0 else bar.get_height() - 18
    ax2.text(bar.get_x() + bar.get_width()/2, ypos,
             f"{int(r['napaka']):+d}\n({r['napaka_pct']:+.0f}%)",
             ha='center', fontsize=7)

ax2.set_xlabel('Leto')
ax2.set_ylabel('Napaka (dejanske − napovedane)')
ax2.set_xticks(skupna['leto'])
ax2.tick_params(axis='x', rotation=45)
ax2.legend(fontsize=9)
ax2.grid(axis='y', alpha=0.2)

plt.tight_layout()
plt.savefig('fotona_backtest_skupna_napaka.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_backtest_skupna_napaka.png")