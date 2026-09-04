"""
Ali servisni posegi napovedujejo reklamacije? — MESEČNA granulacija.

Letna analiza (koleracije_posegi_reklamacijami.py) ima le 2 testni točki na
kategorijo, ker so servisni posegi na voljo šele od 2020. Na mesečni ravni
dobimo ~60 točk (2020-01 do 2024-12) in s tem ~30 testnih točk, kar omogoča
statistično smiselno primerjavo z naivnim baselinom.

Analiza je na ravni SKUPNIH mesečnih reklamacij (ne po kategorijah), da se
izognemo prelomu taksonomije napak 2019/2020 in ničelnim mesecem malih
kategorij.

Modeli (vsi featurji znani pred testnim mesecem, brez uhajanja):
    Naivni          → reklamacije(t-1)
    Sezonski naivni → reklamacije(t-12)
    AR(1)           → LinearRegression na [rekl_lag1]
    SVC(1..3)       → LinearRegression na [svc_lag1, svc_lag2, svc_lag3]
    AR+SVC          → LinearRegression na [rekl_lag1, svc_lag1]
    Ridge(AR+SVC)   → Ridge(alpha=1.0) na istih featurjih

Walk-forward: expanding window, MIN_TRAIN = 24 mesecev.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
from sqlalchemy import text
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy import stats

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
from db_common import get_engine

warnings.filterwarnings('ignore')

# ── 0. KONFIGURACIJA ─────────────────────────────────────────────────────────

OBDOBJE_OD = '2020-01-01'
OBDOBJE_DO = '2024-12-31'   # zadnje polno leto
MIN_TRAIN  = 24             # mesecev

engine = get_engine()

# ── 1. NALOŽI PODATKE ────────────────────────────────────────────────────────

with engine.connect() as conn:
    # Mesečne reklamacije (po datumu prejema; DISTINCT, ker ima lahko
    # reklamacija več zapisov o prejemu)
    df_rekl = pd.read_sql(text("""
        SELECT
            YEAR(datum_prejema)  AS leto,
            MONTH(datum_prejema) AS mesec,
            COUNT(DISTINCT reklamacija_id) AS reklamacije
        FROM prejem_reklamacije
        WHERE datum_prejema BETWEEN :od AND :do
        GROUP BY leto, mesec
        ORDER BY leto, mesec
    """), conn, params={'od': OBDOBJE_OD, 'do': OBDOBJE_DO})

    # Mesečni servisni posegi (po datumu prevzema)
    df_svc = pd.read_sql(text("""
        SELECT
            YEAR(datum_prevzema)  AS leto,
            MONTH(datum_prevzema) AS mesec,
            COUNT(*) AS posegi
        FROM servisni_poseg
        WHERE datum_prevzema BETWEEN :od AND :do
        GROUP BY leto, mesec
        ORDER BY leto, mesec
    """), conn, params={'od': OBDOBJE_OD, 'do': OBDOBJE_DO})

def z_datumom(df):
    df = df.copy()
    df['datum'] = pd.to_datetime(df['leto'].astype(str) + '-' +
                                 df['mesec'].astype(str).str.zfill(2) + '-01')
    return df

df_rekl = z_datumom(df_rekl)
df_svc  = z_datumom(df_svc)

# Polna mesečna mreža (manjkajoči meseci = 0)
vsi_meseci = pd.DataFrame({'datum': pd.date_range(OBDOBJE_OD, OBDOBJE_DO, freq='MS')})
df = (vsi_meseci
      .merge(df_rekl[['datum', 'reklamacije']], on='datum', how='left')
      .merge(df_svc[['datum', 'posegi']], on='datum', how='left')
      .fillna(0))
df[['reklamacije', 'posegi']] = df[['reklamacije', 'posegi']].astype(int)

print(f"Naloženo: {len(df)} mesecev "
      f"({df['datum'].min():%Y-%m} – {df['datum'].max():%Y-%m})")
print(f"Reklamacije: povprečje {df['reklamacije'].mean():.1f}/mesec, "
      f"posegi: {df['posegi'].mean():.1f}/mesec")

# ── 2. KORELACIJSKA ANALIZA (lag 0–3) ────────────────────────────────────────

print("\n── Pearsonova korelacija: reklamacije(t) vs posegi(t-lag) ──")
for lag in range(4):
    if lag == 0:
        r, p = stats.pearsonr(df['reklamacije'], df['posegi'])
    else:
        r, p = stats.pearsonr(df['reklamacije'][lag:], df['posegi'][:-lag])
    znak = ' *' if p < 0.05 else ''
    print(f"  lag {lag}:  r={r:+.3f}  p={p:.4f}{znak}")

# ── 3. FEATURE ENGINEERING (lagi s .shift, brez uhajanja) ────────────────────

df['rekl_lag1']  = df['reklamacije'].shift(1)
df['rekl_lag12'] = df['reklamacije'].shift(12)
df['svc_lag1']   = df['posegi'].shift(1)
df['svc_lag2']   = df['posegi'].shift(2)
df['svc_lag3']   = df['posegi'].shift(3)

# ── 4. WALK-FORWARD BACKTEST ─────────────────────────────────────────────────

MODELI = {
    'Naivni':          {'feat': None,                                'est': None},
    'Sezonski naivni': {'feat': None,                                'est': None},
    'AR(1)':           {'feat': ['rekl_lag1'],                       'est': LinearRegression()},
    'SVC(1..3)':       {'feat': ['svc_lag1', 'svc_lag2', 'svc_lag3'],'est': LinearRegression()},
    'AR+SVC':          {'feat': ['rekl_lag1', 'svc_lag1'],           'est': LinearRegression()},
    'Ridge(AR+SVC)':   {'feat': ['rekl_lag1', 'svc_lag1'],           'est': Ridge(alpha=1.0)},
}

rezultati = []
for i in range(MIN_TRAIN, len(df)):
    train = df.iloc[:i]
    test  = df.iloc[i:i+1]
    vrstica = {
        'datum':    test['datum'].values[0],
        'dejanske': int(test['reklamacije'].values[0]),
    }

    for ime, m in MODELI.items():
        if ime == 'Naivni':
            pred = float(train['reklamacije'].iloc[-1])
        elif ime == 'Sezonski naivni':
            v = test['rekl_lag12'].values[0]
            pred = float(v) if not np.isnan(v) else None
        else:
            tr = train.dropna(subset=m['feat'])
            te_vals = test[m['feat']].values
            if len(tr) >= 12 and not np.any(np.isnan(te_vals.astype(float))):
                m['est'].fit(tr[m['feat']].values, tr['reklamacije'].values)
                pred = max(0.0, float(m['est'].predict(te_vals)[0]))
            else:
                pred = None
        vrstica[ime] = pred

    rezultati.append(vrstica)

df_bt = pd.DataFrame(rezultati)
print(f"\nWalk-forward: {len(df_bt)} testnih mesecev "
      f"({pd.Timestamp(df_bt['datum'].min()):%Y-%m} – "
      f"{pd.Timestamp(df_bt['datum'].max()):%Y-%m}), MIN_TRAIN={MIN_TRAIN}")

# ── 5. METRIKE ───────────────────────────────────────────────────────────────

def metrike(col):
    v = df_bt[df_bt[col].notna()]
    if len(v) < 2:
        return np.nan, np.nan, np.nan, 0
    d, n = v['dejanske'].values.astype(float), v[col].values.astype(float)
    return (mean_absolute_error(d, n),
            np.sqrt(mean_squared_error(d, n)),
            r2_score(d, n),
            len(v))

mae_naivni = metrike('Naivni')[0]

print(f"\n{'='*72}")
print("── PRIMERJAVA MODELOV (mesečno, skupne reklamacije) ──")
print(f"{'='*72}")
print(f"{'Model':<18} {'N':>4} {'MAE':>8} {'RMSE':>8} {'R²':>7} {'vs Naivni':>10} {'Zmaga?':>7}")
print("-" * 68)

povzetek = {}
for ime in MODELI:
    mae, rmse, r2, n = metrike(ime)
    povzetek[ime] = mae
    if np.isnan(mae):
        print(f"{ime:<18} {'N/A':>4}")
        continue
    diff = mae_naivni - mae
    pct  = diff / mae_naivni * 100
    znak = '✓ DA' if diff > 0 else '✗ NE'
    print(f"{ime:<18} {n:>4} {mae:>8.1f} {rmse:>8.1f} {r2:>7.3f} "
          f"{pct:>+9.1f}% {znak:>7}")

# ── 6. IZVOZ ─────────────────────────────────────────────────────────────────

df_bt_out = df_bt.copy()
df_bt_out['datum'] = pd.to_datetime(df_bt_out['datum']).dt.strftime('%Y-%m')
df_bt_out.to_csv('fotona_posegi_reklamacije_mesecno.csv',
                 index=False, encoding='utf-8-sig')
print("\nIzvoženo: fotona_posegi_reklamacije_mesecno.csv")

# ── 7. VIZUALIZACIJA ─────────────────────────────────────────────────────────

fig = plt.figure(figsize=(14, 10))
gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.3)
fig.suptitle('Mesečna analiza: servisni posegi kot prediktor reklamacij (2020–2024)',
             fontsize=13, fontweight='bold')

# Graf 1: časovna vrsta dejanske vs najboljši model
najboljsi = min((k for k in povzetek if not np.isnan(povzetek[k])),
                key=lambda k: povzetek[k])
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(df['datum'], df['reklamacije'], 'o-', color='#534AB7',
         linewidth=1.6, markersize=3.5, label='Dejanske', zorder=3)
sub = df_bt[df_bt[najboljsi].notna()]
ax1.plot(pd.to_datetime(sub['datum']), sub[najboljsi], 's--', color='#D85A30',
         linewidth=1.4, markersize=3.5, alpha=0.85, label=f'Napoved ({najboljsi})')
ax1.axvline(x=df['datum'].iloc[MIN_TRAIN], color='gray', linestyle=':',
            linewidth=1, alpha=0.7)
ax1.text(df['datum'].iloc[MIN_TRAIN], ax1.get_ylim()[1]*0.95,
         ' test →', fontsize=8, color='gray')
ax1.set_ylabel('Reklamacije / mesec')
ax1.set_title(f'Dejanske vs. napoved — najboljši model: {najboljsi} '
              f'(MAE={povzetek[najboljsi]:.1f}, naivni={mae_naivni:.1f})')
ax1.legend(fontsize=9)
ax1.grid(axis='y', alpha=0.2)

# Graf 2: MAE primerjava
ax2 = fig.add_subplot(gs[1, 0])
imena = [k for k in MODELI if not np.isnan(povzetek.get(k, np.nan))]
maes  = [povzetek[k] for k in imena]
barve = ['#27ae60' if k == 'Naivni' else
         '#e74c3c' if povzetek[k] == min(maes) else '#b0b0b0' for k in imena]
bars = ax2.bar(imena, maes, color=barve, alpha=0.85)
ax2.axhline(y=mae_naivni, color='#27ae60', linestyle='--', linewidth=1.2)
for bar, mae in zip(bars, maes):
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.2,
             f'{mae:.1f}', ha='center', fontsize=8, fontweight='bold')
ax2.set_ylabel('MAE')
ax2.set_title('MAE po modelih (zelena = naivni)')
ax2.tick_params(axis='x', rotation=30, labelsize=8)
ax2.grid(axis='y', alpha=0.2)

# Graf 3: scatter posegi(t-1) vs reklamacije(t)
ax3 = fig.add_subplot(gs[1, 1])
maska = df['svc_lag1'].notna()
ax3.scatter(df.loc[maska, 'svc_lag1'], df.loc[maska, 'reklamacije'],
            color='#534AB7', alpha=0.6, s=30)
r1, p1 = stats.pearsonr(df.loc[maska, 'svc_lag1'], df.loc[maska, 'reklamacije'])
z = np.polyfit(df.loc[maska, 'svc_lag1'], df.loc[maska, 'reklamacije'], 1)
xs = np.linspace(df.loc[maska, 'svc_lag1'].min(), df.loc[maska, 'svc_lag1'].max(), 50)
ax3.plot(xs, np.poly1d(z)(xs), '--', color='gray', linewidth=1.3)
ax3.set_xlabel('Servisni posegi (t-1)')
ax3.set_ylabel('Reklamacije (t)')
ax3.set_title(f'Posegi(t-1) vs. reklamacije(t)\nr={r1:.3f}, p={p1:.4f}')
ax3.grid(alpha=0.2)

plt.savefig('fotona_posegi_reklamacije_mesecno.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_posegi_reklamacije_mesecno.png")

# ── 8. SKLEP ─────────────────────────────────────────────────────────────────

print(f"\n{'='*72}")
print("── SKLEP ──")
print(f"{'='*72}")
print(f"Naivni baseline MAE = {mae_naivni:.1f} (n={metrike('Naivni')[3]} testnih mesecev)")
for ime in MODELI:
    if ime == 'Naivni':
        continue
    mae, _, _, n = metrike(ime)
    if np.isnan(mae):
        continue
    pct = (mae_naivni - mae) / mae_naivni * 100
    if pct > 0:
        print(f"✓ {ime} premaga naivnega za {pct:.1f} % (MAE {mae:.1f}, n={n})")
    else:
        print(f"✗ {ime} ne premaga naivnega (MAE {mae:.1f} vs {mae_naivni:.1f}, n={n})")
