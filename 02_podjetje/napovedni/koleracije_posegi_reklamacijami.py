import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
from sqlalchemy import text
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

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

kategorije = sorted(df_cat['kategorija'].unique().tolist())
print(f"Kategorije: {len(kategorije)}")
print(f"Servisni posegi:\n{df_svc.to_string(index=False)}\n")

# ── 2. ZGRADI ENOTEN MODELING DATASET ZA VSAKO KATEGORIJO ───────────────────
#
# Struktura:
#   leto | reklamacije | servisni_posegi | svc_lag1 | rekl_lag1
#
# Lag featurji so ustvarjeni z .shift(1) — brez dict.get(year-1).
# Vrstice z NaN (prve vrstice po shiftu) so jasno označene, ne odstranjene,
# da ohranimo celoten časovni razpon za naivni model.

def build_dataset(kategorija: str) -> pd.DataFrame:
    """Zgradi poln modeling dataset za eno kategorijo."""
    # Reklamacije za to kategorijo po letu
    df_k = (df_cat[df_cat['kategorija'] == kategorija]
            .groupby('leto')['stevilo'].sum()
            .reset_index()
            .rename(columns={'stevilo': 'reklamacije'}))

    # Vse leto od 2013 do 2024 — zagotovimo polno časovno vrsto
    all_years = pd.DataFrame({'leto': range(2013, 2025)})
    df_k = all_years.merge(df_k, on='leto', how='left').fillna(0)
    df_k['reklamacije'] = df_k['reklamacije'].astype(int)

    # Dodaj servisne posege
    df_merged = df_k.merge(df_svc, on='leto', how='left')

    # Ustvari lag featurje z .shift(1) — pandas skrbi za poravnavo
    df_merged = df_merged.sort_values('leto').reset_index(drop=True)
    df_merged['svc_lag1']  = df_merged['servisni_posegi'].shift(1)
    df_merged['rekl_lag1'] = df_merged['reklamacije'].shift(1)

    return df_merged

# Prikaz dataseta za prvo kategorijo (debug)
sample_kat = kategorije[0]
df_sample  = build_dataset(sample_kat)
print(f"── Primer dataseta: {sample_kat.replace('Neskladnost ','')[:30]} ──")
print(df_sample.to_string(index=False))
print()

# ── 3. WALK-FORWARD BACKTEST ─────────────────────────────────────────────────
#
# Expanding window: train = df.iloc[:i], test = df.iloc[i:i+1]
# MIN_TRAIN = 4 (2013–2016 za trening, napoved od 2017 naprej)
#
# Modeli:
#   Naivni   → pred = rekl_lag1  (brez fittanja)
#   Model A  → X = [svc_lag1]
#   Model B  → X = [rekl_lag1, svc_lag1]
#
# Pravilo za NaN: če kateri feature v X_train ali X_test vsebuje NaN,
# model za to točko vrne None. Brez imputacije — to je metodološko čisteje.

MIN_TRAIN = 4
all_results = []

print("=" * 65)
print("── WALK-FORWARD BACKTEST ──")
print("=" * 65)

for kat in kategorije:
    df = build_dataset(kat)
    kat_s = kat.replace('Neskladnost ', '').replace(' komponent', '')

    print(f"\n── {kat_s} ──")
    print(f"{'Leto':>4} | {'Dejanske':>8} | {'Naivni':>7} | "
          f"{'A:svc1':>7} | {'B:rek+svc':>10}")
    print("-" * 50)

    for i in range(MIN_TRAIN, len(df)):
        train = df.iloc[:i].copy()
        test  = df.iloc[i:i+1].copy()

        leto    = int(test['leto'].values[0])
        y_test  = int(test['reklamacije'].values[0])

        # ── Naivni: reklamacije prejšnjega leta ──────────────────────────────
        pred_naivni = int(train['reklamacije'].iloc[-1])

        # ── Model A: X = [svc_lag1] ──────────────────────────────────────────
        feat_A = ['svc_lag1']
        train_A = train.dropna(subset=feat_A)
        test_A_vals = test[feat_A].values

        if len(train_A) >= 2 and not np.any(np.isnan(test_A_vals)):
            mA = LinearRegression().fit(train_A[feat_A].values, train_A['reklamacije'].values)
            pred_A = max(0, int(round(mA.predict(test_A_vals)[0])))
        else:
            pred_A = None

        # ── Model B: X = [rekl_lag1, svc_lag1] ──────────────────────────────
        feat_B = ['rekl_lag1', 'svc_lag1']
        train_B = train.dropna(subset=feat_B)
        test_B_vals = test[feat_B].values

        if len(train_B) >= 2 and not np.any(np.isnan(test_B_vals)):
            mB = LinearRegression().fit(train_B[feat_B].values, train_B['reklamacije'].values)
            pred_B = max(0, int(round(mB.predict(test_B_vals)[0])))
        else:
            pred_B = None

        def fmt(v):
            return f"{v:>7}" if v is not None else f"{'N/A':>7}"

        print(f"{leto:>4} | {y_test:>8} | {pred_naivni:>7} | "
              f"{fmt(pred_A)} | {fmt(pred_B):>10}")

        all_results.append({
            'kategorija':  kat,
            'kat_short':   kat_s,
            'leto':        leto,
            'dejanske':    y_test,
            'pred_naivni': pred_naivni,
            'pred_A':      pred_A,
            'pred_B':      pred_B,
        })

df_bt = pd.DataFrame(all_results)

# ── 4. METRIKE ───────────────────────────────────────────────────────────────

def metrike(df_sub: pd.DataFrame, col: str):
    """MAE, RMSE, R² samo za vrstice kjer col ni None/NaN."""
    valid = df_sub[df_sub[col].notna()].copy()
    if len(valid) < 2:
        return np.nan, np.nan, np.nan
    d = valid['dejanske'].values.astype(float)
    n = valid[col].values.astype(float)
    return (mean_absolute_error(d, n),
            np.sqrt(mean_squared_error(d, n)),
            r2_score(d, n))

modeli = {
    'Naivni':    'pred_naivni',
    'A: svc1':   'pred_A',
    'B: rek+svc':'pred_B',
}

print(f"\n{'='*70}")
print("── PRIMERJAVA MODELOV — skupno (vse kategorije) ──")
print(f"{'='*70}")
print(f"{'Model':<16} {'N':>4} {'MAE':>8} {'RMSE':>8} {'R²':>7} "
      f"{'vs Naivni':>10} {'%':>8} {'Zmaga?':>8}")
print("-" * 70)

mae_naivni_sk, _, _ = metrike(df_bt, 'pred_naivni')

for label, col in modeli.items():
    valid_n = df_bt[df_bt[col].notna()]
    mae, rmse, r2 = metrike(df_bt, col)
    if np.isnan(mae):
        print(f"{label:<16} {'N/A':>4}")
        continue
    diff = mae_naivni_sk - mae
    pct  = diff / mae_naivni_sk * 100
    znak = '✓ DA' if diff > 0 else '✗ NE'
    print(f"{label:<16} {len(valid_n):>4} {mae:>8.1f} {rmse:>8.1f} {r2:>7.3f} "
          f"{diff:>+10.1f} {pct:>+7.1f}% {znak:>8}")

# ── Po kategorijah ───────────────────────────────────────────────────────────

print(f"\n{'='*75}")
print("── MAE PO KATEGORIJAH ──")
print(f"{'='*75}")
print(f"{'Kategorija':<30} {'N':>3} {'Naivni':>8} {'A:svc1':>8} "
      f"{'B:rek+svc':>10} {'Najboljši':>12}")
print("-" * 75)

for kat in kategorije:
    sub   = df_bt[df_bt['kategorija'] == kat]
    kat_s = kat.replace('Neskladnost ', '').replace(' komponent', '')

    maes = {}
    for label, col in modeli.items():
        m, _, _ = metrike(sub, col)
        maes[label] = m

    valid_n = len(sub[sub['pred_naivni'].notna()])
    best = min(maes, key=lambda k: maes[k] if not np.isnan(maes[k]) else np.inf)
    naivni_mae = maes['Naivni']
    best_mae   = maes[best]
    pct = (naivni_mae - best_mae) / naivni_mae * 100 if naivni_mae > 0 else 0
    znak = '✓' if pct > 0 and best != 'Naivni' else ''

    def fm(v):
        return f"{v:>8.1f}" if not np.isnan(v) else f"{'N/A':>8}"

    print(f"{kat_s:<30} {valid_n:>3} {fm(maes['Naivni'])} {fm(maes['A: svc1'])} "
          f"{fm(maes['B: rek+svc']):>10} {best:>10} {znak} {abs(pct):.0f}%")

# ── 5. IZVOZI CSV ────────────────────────────────────────────────────────────

df_bt.to_csv('fotona_backtest_svc_clean.csv', index=False, encoding='utf-8-sig')
print("\nIzvoženo: fotona_backtest_svc_clean.csv")

# ── 6. VIZUALIZACIJA ─────────────────────────────────────────────────────────

colors_kat = {
    'Neskladnost optičnih komponent':     '#534AB7',
    'Neskladnost elektronskih komponent': '#0F6E56',
    'Neskladnost mehanskih komponent':    '#D85A30',
    'Ni tehnična napaka':                 '#888780',
    'Neskladnost enote za sprej':         '#BA7517',
    'Neskladnost hladilnega sistema':     '#185FA5',
}

fig = plt.figure(figsize=(16, 18))
gs  = gridspec.GridSpec(4, 2, figure=fig, hspace=0.5, wspace=0.35)
fig.suptitle('Walk-forward backtest: servisni posegi kot prediktor\n'
             '(Modeli A in B imajo napovedi le za leta z razpoložljivim svc_lag1)',
             fontsize=13, fontweight='bold')

# Graf 1: Skupna MAE primerjava
ax1 = fig.add_subplot(gs[0, :])
mae_vals, labels_plot = [], []
for label, col in modeli.items():
    m, _, _ = metrike(df_bt, col)
    if not np.isnan(m):
        mae_vals.append(m)
        labels_plot.append(label)

bar_colors = ['#27ae60' if l == 'Naivni' else
              '#e74c3c' if v == min(mae_vals) else '#b0b0b0'
              for v, l in zip(mae_vals, labels_plot)]
bars = ax1.bar(labels_plot, mae_vals, color=bar_colors, alpha=0.85, width=0.4)
ax1.axhline(y=mae_naivni_sk, color='#27ae60', linestyle='--',
            linewidth=1.5, label=f'Naivni ({mae_naivni_sk:.1f})')
for bar, mae in zip(bars, mae_vals):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
             f'{mae:.1f}', ha='center', fontsize=11, fontweight='bold')
ax1.set_ylabel('MAE (skupno povprečje)')
ax1.set_title('Skupna MAE: Naivni vs. A (svc_lag1) vs. B (rek+svc)\n'
              '(zelena = naivni baseline, rdeča = najboljši)')
ax1.legend(fontsize=10)
ax1.grid(axis='y', alpha=0.2)

# Grafi 2–7: Po kategorijah
for idx, kat in enumerate(kategorije):
    row = idx // 2 + 1
    col = idx % 2
    ax  = fig.add_subplot(gs[row, col])

    sub   = df_bt[df_bt['kategorija'] == kat]
    color = colors_kat.get(kat, '#333')
    kat_s = kat.replace('Neskladnost ', '').replace(' komponent', '')
    df_full = build_dataset(kat)

    # Polna časovna vrsta (vse leto)
    ax.plot(df_full['leto'], df_full['reklamacije'], 'o-',
            color=color, linewidth=2, markersize=5, label='Dejanske', zorder=3)

    # Naivni
    ax.plot(sub['leto'], sub['pred_naivni'], 's:',
            color='gray', linewidth=1.2, markersize=4, alpha=0.7, label='Naivni')

    # Model B (če ima napovedi)
    sub_B = sub[sub['pred_B'].notna()]
    if len(sub_B) > 0:
        ax.plot(sub_B['leto'], sub_B['pred_B'], '^--',
                color=color, linewidth=1.8, markersize=6, alpha=0.9,
                label='B: rek+svc')

    # Model A (če ima napovedi)
    sub_A = sub[sub['pred_A'].notna()]
    if len(sub_A) > 0:
        ax.plot(sub_A['leto'], sub_A['pred_A'], 'D:',
                color=color, linewidth=1.2, markersize=4, alpha=0.5,
                label='A: svc1')

    mae_n, _, _ = metrike(sub, 'pred_naivni')
    mae_b, _, _ = metrike(sub, 'pred_B')
    mae_a, _, _ = metrike(sub, 'pred_A')

    title_lines = [kat_s, f'Naivni MAE={mae_n:.0f}']
    if not np.isnan(mae_b):
        pct_b = (mae_n - mae_b) / mae_n * 100
        title_lines.append(f'B MAE={mae_b:.0f} ({pct_b:+.0f}%)')
    if not np.isnan(mae_a):
        pct_a = (mae_n - mae_a) / mae_n * 100
        title_lines.append(f'A MAE={mae_a:.0f} ({pct_a:+.0f}%)')

    ax.set_title('\n'.join(title_lines), fontsize=8)
    ax.set_xlabel('Leto', fontsize=8)
    ax.set_ylabel('Reklamacije', fontsize=8)
    ax.legend(fontsize=7, framealpha=0.8)
    ax.set_xticks(df_full['leto'].tolist())
    ax.tick_params(axis='x', rotation=45, labelsize=7)
    ax.grid(axis='y', alpha=0.2)

    # Meja trening/test
    ax.axvline(x=2016.5, color='gray', linestyle=':', linewidth=1, alpha=0.5)
    # Meja kjer se svc podatki začnejo
    if len(sub_B) > 0:
        ax.axvline(x=float(sub_B['leto'].min()) - 0.5,
                   color=color, linestyle=':', linewidth=1, alpha=0.4)
        ax.text(float(sub_B['leto'].min()) - 0.4,
                ax.get_ylim()[0] * 1.05, 'svc→', fontsize=6, color=color)

plt.savefig('fotona_backtest_svc_clean.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_backtest_svc_clean.png")

# ── 7. SKLEP ZA NALOGO ───────────────────────────────────────────────────────

print(f"\n{'='*65}")
print("── SKLEP ZA DIPLOMSKO NALOGO ──")
print(f"{'='*65}")
print(f"\nNaivni baseline MAE = {mae_naivni_sk:.1f} (n=48 testnih točk, 2017–2024)")

for label, col in [('A: svc_lag1', 'pred_A'), ('B: rek+svc', 'pred_B')]:
    mae, _, _ = metrike(df_bt, col)
    if np.isnan(mae):
        print(f"{label}: ni podatkov")
        continue
    n = len(df_bt[df_bt[col].notna()])
    diff = mae_naivni_sk - mae
    pct  = diff / mae_naivni_sk * 100
    if diff > 0:
        print(f"✓ Model {label} premaga naivni za {pct:.1f}%  "
              f"(MAE {mae_naivni_sk:.1f} → {mae:.1f},  n={n} testnih točk)")
    else:
        print(f"✗ Model {label} ne premaga naivnega  "
              f"(MAE {mae:.1f} vs {mae_naivni_sk:.1f},  n={n} testnih točk)")

print(f"\nOMEJITEV: Servisni posegi so na voljo le od 2020 naprej.")
print(f"  Modeli A/B imajo zato le 4 testne točke na kategorijo (2021–2024).")
print(f"  Za zanesljive zaključke bi potrebovali podatke od vsaj 2013.")