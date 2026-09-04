import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
from sqlalchemy import text
from sklearn.linear_model import LinearRegression, Ridge, PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy import stats

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
from db_common import get_engine, ANALIZA_REKLAMACIJE_KAT

warnings.filterwarnings('ignore')

# ── 0. MySQL POVEZAVA ────────────────────────────────────────────────────────
# Nastavitve so v .env; stolpec kategorija je rekonstruiran iz vrsta_napake
# (glej db_common.py).

engine = get_engine()

# ── 1. NALOŽI PODATKE ────────────────────────────────────────────────────────

with engine.connect() as conn:

    # Reklamacije po letu in kategoriji
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

    # Prihodki
    df_rev = pd.read_sql(text("""
        SELECT year, revenue_eur FROM fotona_revenue ORDER BY year
    """), conn)

    # Servisni posegi po letu (tabela servisni_poseg, datum prevzema —
    # enako kot v koleracije_posegi_reklamacijami.py)
    df_svc = pd.read_sql(text("""
        SELECT
            YEAR(datum_prevzema) AS leto,
            COUNT(*)             AS servisni_posegi
        FROM servisni_poseg
        WHERE datum_prevzema IS NOT NULL
          AND YEAR(datum_prevzema) BETWEEN 2013 AND 2024
        GROUP BY YEAR(datum_prevzema)
        ORDER BY leto
    """), conn)

df_rev['revenue_mio'] = df_rev['revenue_eur'] / 1_000_000
rev_dict = df_rev.set_index('year')['revenue_mio'].to_dict()
svc_dict = df_svc.set_index('leto')['servisni_posegi'].to_dict()

years_all  = sorted(df_cat['leto'].unique().tolist())
kategorije = sorted(df_cat['kategorija'].unique().tolist())

print(f"Leta: {years_all[0]}–{years_all[-1]}")
print(f"Kategorije: {len(kategorije)}")
print(f"Servisni posegi naloženi za leta: {sorted(svc_dict.keys())}")
print(f"Testnih točk na kategorijo: {len(years_all) - 4}  (MIN_TRAIN=4)")
print("OPOMBA: Majhen vzorec (n=8) — rezultate interpretiraj previdno.\n")

# ── 2. KORELACIJSKA ANALIZA ──────────────────────────────────────────────────

print("="*70)
print("── KORELACIJSKA ANALIZA: reklamacije vs servisni posegi ──")
print("="*70)

# Skupne reklamacije po letu
total_rekl = (df_cat.groupby('leto')['stevilo'].sum()
              .reindex(years_all).fillna(0).values)
svc_vals   = np.array([svc_dict.get(yr, np.nan) for yr in years_all])

# Lag 0
mask0 = ~np.isnan(svc_vals)
r0, p0 = stats.pearsonr(total_rekl[mask0], svc_vals[mask0])
print(f"\nReklamacije(t) vs servisni posegi(t):    r={r0:.3f}, p={p0:.4f}")

# Lag 1
rekl_lag1 = total_rekl[1:]
svc_lag1  = svc_vals[:-1]
mask1     = ~np.isnan(svc_lag1)
r1, p1    = stats.pearsonr(rekl_lag1[mask1], svc_lag1[mask1])
print(f"Reklamacije(t) vs servisni posegi(t-1):  r={r1:.3f}, p={p1:.4f}")

# Korelacija po kategorijah
print(f"\n{'Kategorija':<35} {'r (lag0)':>9} {'r (lag1)':>9} {'p (lag0)':>9}")
print("-"*65)
kat_corr = {}
for kat in kategorije:
    df_k   = (df_cat[df_cat['kategorija']==kat]
              .groupby('leto')['stevilo'].sum()
              .reindex(years_all).fillna(0).values)
    mask   = ~np.isnan(svc_vals)
    rk0, pk0 = stats.pearsonr(df_k[mask], svc_vals[mask])

    rk1_vals = df_k[1:][~np.isnan(svc_vals[:-1])]
    sv1_vals = svc_vals[:-1][~np.isnan(svc_vals[:-1])]
    rk1, pk1 = stats.pearsonr(rk1_vals, sv1_vals) if len(rk1_vals) > 2 else (np.nan, np.nan)

    kat_s = kat.replace('Neskladnost ','').replace(' komponent','')
    print(f"{kat_s:<35} {rk0:>9.3f} {rk1:>9.3f} {pk0:>9.4f}")
    kat_corr[kat] = (rk0, rk1)

# ── 3. WALK-FORWARD BACKTEST ─────────────────────────────────────────────────

MIN_TRAIN = 4

# Definicija modelov — brez data leakage, vsi featureji znani pred testnim letom
MODELI = {
    'Naivni':           None,   # reklamacije(t-1)
    'Lin(leto)':        None,   # X = [leto]
    'Lin(leto+rev)':    None,   # X = [leto, prihodki(t-1)]
    'Lin(rek_lag1)':    None,   # X = [reklamacije(t-1)]
    'Lin(leto+rek)':    None,   # X = [leto, reklamacije(t-1)]
    'Poisson(leto+rev)':None,   # X = [leto, prihodki(t-1)]
    'Lin(svc_lag1)':    None,   # X = [servisni_posegi(t-1)]
    'Lin(leto+svc)':    None,   # X = [leto, servisni_posegi(t-1)]
    'Lin(rek+svc)':     None,   # X = [reklamacije(t-1), servisni_posegi(t-1)]
    'Ridge(rek+svc)':   None,   # X = [reklamacije(t-1), servisni_posegi(t-1)]
    'AR2':              None,   # X = [reklamacije(t-1), reklamacije(t-2)]
}

all_results = []

print(f"\n{'='*70}")
print("── WALK-FORWARD BACKTEST ──")
print(f"{'='*70}\n")

for kat in kategorije:
    df_k  = (df_cat[df_cat['kategorija']==kat]
             .groupby('leto')['stevilo'].sum())
    y_all = np.array([int(df_k.get(yr, 0)) for yr in years_all])
    kat_s = kat.replace('Neskladnost ','').replace(' komponent','')

    print(f"── {kat_s} ──")
    print(f"{'Leto':>4} | {'Dej':>5} | {'Naivni':>7} | {'Lin':>5} | "
          f"{'+rev':>6} | {'rek1':>6} | {'leto+rek':>9} | "
          f"{'svc1':>6} | {'rek+svc':>8} | {'AR2':>5}")
    print("-"*75)

    for i in range(MIN_TRAIN, len(years_all)):
        train_years = years_all[:i]
        test_year   = years_all[i]
        y_train     = y_all[:i]
        y_test      = int(y_all[i])

        def safe_pred(model, X_tr, X_te, y_tr):
            """Fitaj model in vrni napoved, ali None če ni podatkov."""
            if X_tr is None or X_te is None:
                return None
            if np.any(np.isnan(X_tr)) or np.any(np.isnan(X_te)):
                return None
            try:
                model.fit(X_tr, y_tr)
                return max(0, int(round(model.predict(X_te)[0])))
            except Exception:
                return None

        X_leto_tr = np.array(train_years).reshape(-1,1)
        X_leto_te = np.array([[test_year]])

        # Prihodki lag1
        rev_tr = [rev_dict.get(yr-1, np.nan) for yr in train_years]
        rev_te = rev_dict.get(test_year-1, np.nan)
        X_rev_tr = np.column_stack([train_years, rev_tr]) if not any(np.isnan(rev_tr)) else None
        X_rev_te = np.array([[test_year, rev_te]]) if not np.isnan(rev_te) else None

        # Servisni posegi lag1
        svc_tr = [svc_dict.get(yr-1, np.nan) for yr in train_years]
        svc_te = svc_dict.get(test_year-1, np.nan)
        X_svc_tr = np.array(svc_tr).reshape(-1,1) if not any(np.isnan(svc_tr)) else None
        X_svc_te = np.array([[svc_te]]) if not np.isnan(svc_te) else None

        # reklamacije lag1
        rek_lag1_tr = y_train[:-1]
        rek_lag1_te = int(y_train[-1])

        # rek + svc lag1
        svc_lag1_tr = [svc_dict.get(yr-1, np.nan) for yr in train_years[1:]]
        svc_lag1_te = svc_dict.get(test_year-1, np.nan)
        has_rek_svc = (not any(np.isnan(svc_lag1_tr))) and (not np.isnan(svc_lag1_te))
        X_reksvc_tr = np.column_stack([rek_lag1_tr, svc_lag1_tr]) if has_rek_svc else None
        X_reksvc_te = np.array([[rek_lag1_te, svc_lag1_te]]) if has_rek_svc else None

        # AR2: reklamacije(t-1) in reklamacije(t-2)
        if i >= MIN_TRAIN + 1:
            X_ar2_tr = np.column_stack([y_train[1:-1], y_train[:-2]])
            X_ar2_te = np.array([[int(y_train[-1]), int(y_train[-2])]])
            y_ar2_tr = y_train[2:]
        else:
            X_ar2_tr = X_ar2_te = y_ar2_tr = None

        # ── Napovedi ────────────────────────────────────────────────────────
        pred_naivni    = int(y_train[-1])
        pred_lin       = safe_pred(LinearRegression(), X_leto_tr, X_leto_te, y_train)
        pred_lin_rev   = safe_pred(LinearRegression(), X_rev_tr, X_rev_te, y_train)
        pred_rek_lag1  = safe_pred(LinearRegression(),
                                   rek_lag1_tr.reshape(-1,1),
                                   np.array([[rek_lag1_te]]), y_train[1:])
        pred_leto_rek  = safe_pred(LinearRegression(),
                                   np.column_stack([train_years[1:], rek_lag1_tr]),
                                   np.array([[test_year, rek_lag1_te]]), y_train[1:])
        pred_poisson   = safe_pred(PoissonRegressor(max_iter=300), X_rev_tr, X_rev_te, y_train)
        pred_svc_lag1  = safe_pred(LinearRegression(),
                                   X_svc_tr, X_svc_te, y_train) if X_svc_tr is not None else None
        pred_leto_svc  = safe_pred(LinearRegression(),
                                   np.column_stack([train_years, svc_tr]) if X_svc_tr is not None else None,
                                   np.array([[test_year, svc_te]]) if not np.isnan(svc_te) else None,
                                   y_train)
        pred_rek_svc   = safe_pred(LinearRegression(), X_reksvc_tr, X_reksvc_te, y_train[1:])
        pred_ridge_reksvc = safe_pred(Ridge(alpha=1.0), X_reksvc_tr, X_reksvc_te, y_train[1:])
        pred_ar2       = safe_pred(LinearRegression(), X_ar2_tr, X_ar2_te, y_ar2_tr) if X_ar2_tr is not None else None

        def fmt(v):
            return f"{v:>6}" if v is not None else f"{'N/A':>6}"

        print(f"{test_year:>4} | {y_test:>5} | {pred_naivni:>7} | {pred_lin:>5} | "
              f"{fmt(pred_lin_rev)} | {fmt(pred_rek_lag1)} | {fmt(pred_leto_rek):>9} | "
              f"{fmt(pred_svc_lag1)} | {fmt(pred_rek_svc):>8} | {fmt(pred_ar2)}")

        all_results.append({
            'kategorija': kat, 'kat_short': kat_s,
            'leto': test_year, 'n_train': i, 'dejanske': y_test,
            'pred_naivni':      pred_naivni,
            'pred_lin':         pred_lin,
            'pred_lin_rev':     pred_lin_rev,
            'pred_rek_lag1':    pred_rek_lag1,
            'pred_leto_rek':    pred_leto_rek,
            'pred_poisson':     pred_poisson,
            'pred_svc_lag1':    pred_svc_lag1,
            'pred_leto_svc':    pred_leto_svc,
            'pred_rek_svc':     pred_rek_svc,
            'pred_ridge_reksvc':pred_ridge_reksvc,
            'pred_ar2':         pred_ar2,
        })
    print()

# ── 4. METRIKE ───────────────────────────────────────────────────────────────

df_bt = pd.DataFrame(all_results)

modeli_cols = {
    'Naivni':        'pred_naivni',
    'Lin(leto)':     'pred_lin',
    'Lin(leto+rev)': 'pred_lin_rev',
    'Lin(rek_lag1)': 'pred_rek_lag1',
    'Lin(leto+rek)': 'pred_leto_rek',
    'Poisson':       'pred_poisson',
    'Lin(svc_lag1)': 'pred_svc_lag1',
    'Lin(leto+svc)': 'pred_leto_svc',
    'Lin(rek+svc)':  'pred_rek_svc',
    'Ridge(rek+svc)':'pred_ridge_reksvc',
    'AR2':           'pred_ar2',
}

print(f"\n{'='*90}")
print("── PRIMERJAVA MODELOV — skupno povprečje vseh kategorij ──")
print(f"{'='*90}")
print(f"{'Model':<18} {'MAE':>8} {'RMSE':>8} {'R²':>6} {'vs Naivni':>10} {'%':>8}")
print("-"*60)

# Skupni naivni MAE
mae_naivni_skupni = (df_bt['dejanske'] - df_bt['pred_naivni']).abs().mean()

for label, col in modeli_cols.items():
    sub = df_bt[df_bt[col].notna()].copy()
    if len(sub) == 0:
        continue
    napake  = sub['dejanske'] - sub[col]
    mae     = napake.abs().mean()
    rmse    = np.sqrt((napake**2).mean())
    try:
        r2  = r2_score(sub['dejanske'], sub[col])
    except Exception:
        r2  = np.nan
    diff    = mae_naivni_skupni - mae
    pct     = diff / mae_naivni_skupni * 100
    znak    = '✓' if diff > 0 else '✗'
    print(f"{label:<18} {mae:>8.1f} {rmse:>8.1f} {r2:>6.3f} {diff:>+10.1f} {pct:>+7.1f}% {znak}")

# ── Po kategorijah ───────────────────────────────────────────────────────────

print(f"\n{'='*90}")
print("── MAE PO KATEGORIJAH ──")
print(f"{'='*90}")

header = f"{'Kategorija':<25}" + "".join(f"{m:>12}" for m in modeli_cols)
print(header)
print("-"*90)

for kat in kategorije:
    sub   = df_bt[df_bt['kategorija']==kat]
    kat_s = kat.replace('Neskladnost ','').replace(' komponent','')
    row   = f"{kat_s:<25}"
    for label, col in modeli_cols.items():
        v = sub[sub[col].notna()]
        mae = (v['dejanske']-v[col]).abs().mean() if len(v) > 0 else np.nan
        row += f"{mae:>12.1f}" if not np.isnan(mae) else f"{'N/A':>12}"
    print(row)

# Najboljši model po kategoriji
print(f"\n── Najboljši model po kategoriji ──")
for kat in kategorije:
    sub   = df_bt[df_bt['kategorija']==kat]
    kat_s = kat.replace('Neskladnost ','').replace(' komponent','')
    best_label, best_mae = None, np.inf
    for label, col in modeli_cols.items():
        v = sub[sub[col].notna()]
        if len(v) == 0: continue
        mae = (v['dejanske']-v[col]).abs().mean()
        if mae < best_mae:
            best_mae, best_label = mae, label
    naivni_mae = (sub['dejanske']-sub['pred_naivni']).abs().mean()
    izboljsava = (naivni_mae - best_mae) / naivni_mae * 100
    znak = '✓' if izboljsava > 0 else '✗'
    print(f"  {kat_s:<33} → {best_label:<18} MAE={best_mae:.1f} "
          f"(naivni={naivni_mae:.1f}, {znak}{abs(izboljsava):.0f}%)")

# ── 5. IZVOZI CSV ────────────────────────────────────────────────────────────

df_bt.to_csv('fotona_backtest_final.csv', index=False, encoding='utf-8-sig')
print("\nIzvoženo: fotona_backtest_final.csv")

# ── 6. VIZUALIZACIJA ─────────────────────────────────────────────────────────

fig = plt.figure(figsize=(18, 16))
gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35)
fig.suptitle('Walk-forward backtest: primerjava modelov (Fotona reklamacije)',
             fontsize=14, fontweight='bold')

colors_model = [
    '#888780','#534AB7','#0F6E56','#D85A30','#BA7517',
    '#e74c3c','#1D9E75','#7F77DD','#2c3e50','#16a085','#e67e22'
]
colors_kat = {
    'Neskladnost optičnih komponent':     '#534AB7',
    'Neskladnost elektronskih komponent': '#0F6E56',
    'Neskladnost mehanskih komponent':    '#D85A30',
    'Ni tehnična napaka':                 '#888780',
    'Neskladnost enote za sprej':         '#BA7517',
    'Neskladnost hladilnega sistema':     '#185FA5',
}

# Graf 1: MAE primerjava vseh modelov (skupno)
ax1 = fig.add_subplot(gs[0, :])
mae_skupni = []
labels_plot = []
for label, col in modeli_cols.items():
    sub = df_bt[df_bt[col].notna()]
    if len(sub) == 0: continue
    mae = (sub['dejanske']-sub[col]).abs().mean()
    mae_skupni.append(mae)
    labels_plot.append(label)

bar_colors = ['#e74c3c' if m == min(mae_skupni) else
              '#27ae60' if l == 'Naivni' else '#b0b0b0'
              for m, l in zip(mae_skupni, labels_plot)]
bars = ax1.bar(labels_plot, mae_skupni, color=bar_colors, alpha=0.85, width=0.6)
ax1.axhline(y=mae_naivni_skupni, color='#27ae60', linestyle='--',
            linewidth=1.5, label=f'Naivni baseline ({mae_naivni_skupni:.1f})')
for bar, mae in zip(bars, mae_skupni):
    ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
             f'{mae:.1f}', ha='center', fontsize=8)
ax1.set_ylabel('MAE (povprečna absolutna napaka)')
ax1.set_title('Skupna MAE primerjava vseh modelov\n(rdeča = najboljši, zelena = naivni baseline)')
ax1.legend(fontsize=9)
ax1.tick_params(axis='x', rotation=25)
ax1.grid(axis='y', alpha=0.2)

# Graf 2: Korelacija reklamacije vs servisni posegi
ax2 = fig.add_subplot(gs[1, 0])
mask = ~np.isnan(svc_vals)
ax2.scatter(svc_vals[mask], total_rekl[mask],
            color='#534AB7', alpha=0.75, s=70, zorder=3)
for i, yr in enumerate(np.array(years_all)[mask]):
    ax2.annotate(str(yr), (svc_vals[mask][i], total_rekl[mask][i]),
                 textcoords='offset points', xytext=(5,3), fontsize=7)
z = np.polyfit(svc_vals[mask], total_rekl[mask], 1)
x_line = np.linspace(svc_vals[mask].min(), svc_vals[mask].max(), 100)
ax2.plot(x_line, np.poly1d(z)(x_line), '--', color='gray', linewidth=1.5)
ax2.set_xlabel('Servisni posegi')
ax2.set_ylabel('Reklamacije')
ax2.set_title(f'Korelacija: reklamacije vs servisni posegi\nr={r0:.3f}, p={p0:.4f}')
ax2.grid(alpha=0.2)

# Graf 3: Najboljši model vs naivni po kategorijah
ax3 = fig.add_subplot(gs[1, 1])
kat_labels_s = [k.replace('Neskladnost ','').replace(' komponent','') for k in kategorije]
mae_naivni_kat, mae_best_kat, best_model_kat = [], [], []
for kat in kategorije:
    sub = df_bt[df_bt['kategorija']==kat]
    mae_n = (sub['dejanske']-sub['pred_naivni']).abs().mean()
    best_l, best_m = None, np.inf
    for label, col in modeli_cols.items():
        if label == 'Naivni': continue
        v = sub[sub[col].notna()]
        if len(v) == 0: continue
        m = (v['dejanske']-v[col]).abs().mean()
        if m < best_m: best_m, best_l = m, label
    mae_naivni_kat.append(mae_n)
    mae_best_kat.append(best_m)
    best_model_kat.append(best_l)

x = np.arange(len(kategorije))
ax3.bar(x - 0.2, mae_naivni_kat, 0.35, label='Naivni', color='#888780', alpha=0.8)
ax3.bar(x + 0.2, mae_best_kat,   0.35, label='Najboljši model', color='#534AB7', alpha=0.8)
for i, (mn, mb, ml) in enumerate(zip(mae_naivni_kat, mae_best_kat, best_model_kat)):
    ax3.text(i+0.2, mb+0.5, ml[:8], ha='center', fontsize=6, rotation=45)
ax3.set_xticks(x)
ax3.set_xticklabels(kat_labels_s, rotation=20, ha='right', fontsize=8)
ax3.set_ylabel('MAE')
ax3.set_title('Naivni vs. najboljši model po kategorijah')
ax3.legend(fontsize=9)
ax3.grid(axis='y', alpha=0.2)

# Graf 4: Dejanske vs napovedane za najboljši skupni model
best_skupni_label = labels_plot[mae_skupni.index(min(mae_skupni))]
best_skupni_col   = modeli_cols[best_skupni_label]

ax4 = fig.add_subplot(gs[2, :])
for kat in kategorije:
    sub   = df_bt[(df_bt['kategorija']==kat) & df_bt[best_skupni_col].notna()]
    color = colors_kat.get(kat, '#333')
    kat_s = kat.replace('Neskladnost ','').replace(' komponent','')
    ax4.plot(sub['leto'], sub['dejanske'], 'o-', color=color,
             linewidth=1.5, markersize=4, alpha=0.8, label=f'{kat_s} (dej.)')
    ax4.plot(sub['leto'], sub[best_skupni_col], 's--', color=color,
             linewidth=1, markersize=4, alpha=0.5)

ax4.set_xlabel('Leto')
ax4.set_ylabel('Reklamacije')
ax4.set_title(f'Dejanske (polna) vs. napovedane (črtkana) — {best_skupni_label}')
ax4.legend(fontsize=7, ncol=3, framealpha=0.8)
ax4.set_xticks(years_all)
ax4.tick_params(axis='x', rotation=45)
ax4.grid(axis='y', alpha=0.2)

plt.savefig('fotona_backtest_final.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_backtest_final.png")