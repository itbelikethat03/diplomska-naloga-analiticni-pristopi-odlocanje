import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
from sqlalchemy import text
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from scipy import stats

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
from db_common import get_engine, ANALIZA_REKLAMACIJE_KAT

warnings.filterwarnings('ignore')

# ── 0. MySQL POVEZAVA ────────────────────────────────────────────────────────
# Nastavitve so v .env; stolpec kategorija je rekonstruiran iz vrsta_napake
# (glej db_common.py).

engine = get_engine()

# ── 1. NALOŽI PODATKE — mesečne reklamacije ──────────────────────────────────

with engine.connect() as conn:
    df_raw = pd.read_sql(text(f"""
        SELECT
            YEAR(pr.datum_prejema)  AS leto,
            MONTH(pr.datum_prejema) AS mesec,
            COUNT(*)                AS stevilo_reklamacij
        FROM prejem_reklamacije pr
        JOIN {ANALIZA_REKLAMACIJE_KAT} ar ON ar.reklamacija_id = pr.reklamacija_id
        WHERE pr.datum_prejema IS NOT NULL
          AND ar.kategorija IS NOT NULL
          AND ar.kategorija != 'Nerazporejeno'
          AND YEAR(pr.datum_prejema) BETWEEN 2013 AND 2024
        GROUP BY
            YEAR(pr.datum_prejema),
            MONTH(pr.datum_prejema)
        ORDER BY leto, mesec
    """), conn)

# Ustvari datetime indeks
df_raw['datum'] = pd.to_datetime(
    df_raw['leto'].astype(str) + '-' +
    df_raw['mesec'].astype(str).str.zfill(2) + '-01'
)
df_raw = df_raw.sort_values('datum').reset_index(drop=True)

print(f"Naloženo: {len(df_raw)} mesečnih točk "
      f"({df_raw['datum'].min().strftime('%Y-%m')} – "
      f"{df_raw['datum'].max().strftime('%Y-%m')})")
print(df_raw[['datum', 'stevilo_reklamacij']].to_string(index=False))

# ── 2. FEATURE ENGINEERING ───────────────────────────────────────────────────
# Featurji za anomaly detection:
#   - stevilo_reklamacij       (absolutna vrednost)
#   - rolling_mean_3m          (povprečje zadnjih 3 mesecev)
#   - rolling_std_3m           (standardni odklon zadnjih 3 mesecev)
#   - mesecni_indeks           (sezonski vzorec — kateri mesec)
#   - yoy_sprememba            (year-over-year sprememba v %)

df = df_raw.copy()
df['rolling_mean_3m'] = df['stevilo_reklamacij'].rolling(3, min_periods=1).mean()
df['rolling_std_3m']  = df['stevilo_reklamacij'].rolling(3, min_periods=2).std().fillna(0)
df['yoy_sprememba']   = df['stevilo_reklamacij'].pct_change(12) * 100

# Sezonski indeks (povprečje tega meseca skozi vsa leta)
mesecno_povp = df.groupby('mesec')['stevilo_reklamacij'].transform('mean')
df['sezonski_indeks'] = df['stevilo_reklamacij'] / mesecno_povp

df = df.dropna(subset=['yoy_sprememba']).reset_index(drop=True)

print(f"\nFeaturi za anomaly detection ({len(df)} točk po odstranitvi NaN):")
print(df[['datum','stevilo_reklamacij','rolling_mean_3m',
          'yoy_sprememba','sezonski_indeks']].round(1).to_string(index=False))

# ── 3. METODA 1: Z-SCORE ─────────────────────────────────────────────────────

df['z_score'] = stats.zscore(df['stevilo_reklamacij'])
Z_THRESHOLD = 2.0  # |z| > 2 = anomalija

df['anomalija_zscore'] = df['z_score'].abs() > Z_THRESHOLD
df['tip_zscore'] = np.where(
    df['z_score'] > Z_THRESHOLD,  'pozitivna (spike)',
    np.where(df['z_score'] < -Z_THRESHOLD, 'negativna (drop)', 'normalno')
)

print(f"\n── Z-Score anomalije (prag |z| > {Z_THRESHOLD}) ──")
zscore_anom = df[df['anomalija_zscore']].sort_values('z_score')
print(f"{'Datum':<12} {'Reklamacije':>12} {'Z-score':>8} {'Tip':>20}")
print("-" * 56)
for _, r in zscore_anom.iterrows():
    print(f"{r['datum'].strftime('%Y-%m'):<12} {r['stevilo_reklamacij']:>12.0f} "
          f"{r['z_score']:>8.2f} {r['tip_zscore']:>20}")

# ── 4. METODA 2: ISOLATION FOREST ───────────────────────────────────────────

features = ['stevilo_reklamacij', 'rolling_mean_3m',
            'rolling_std_3m', 'sezonski_indeks']

scaler  = StandardScaler()
X_scaled = scaler.fit_transform(df[features])

# contamination = pričakovani delež anomalij (~10%)
iso_forest = IsolationForest(
    n_estimators=200,
    contamination=0.10,
    random_state=42,
    max_samples='auto'
)
df['if_score']    = iso_forest.fit_predict(X_scaled)          # -1 = anomalija
df['if_anom_score'] = iso_forest.score_samples(X_scaled)      # nižji = bolj anomalen
df['anomalija_if']  = df['if_score'] == -1

print(f"\n── Isolation Forest anomalije ──")
if_anom = df[df['anomalija_if']].sort_values('if_anom_score')
print(f"{'Datum':<12} {'Reklamacije':>12} {'IF score':>10} {'Z-score':>8}")
print("-" * 46)
for _, r in if_anom.iterrows():
    print(f"{r['datum'].strftime('%Y-%m'):<12} {r['stevilo_reklamacij']:>12.0f} "
          f"{r['if_anom_score']:>10.3f} {r['z_score']:>8.2f}")

# ── 5. KOMBINIRANE ANOMALIJE (obe metodi se strinjata) ───────────────────────

df['anomalija_obe'] = df['anomalija_zscore'] & df['anomalija_if']

print(f"\n── Anomalije potrjene z OBEMA metodama ──")
obe_anom = df[df['anomalija_obe']].sort_values('z_score')
if len(obe_anom) == 0:
    print("Nobena anomalija potrjena z obema metodama — zmanjšaj prag Z ali contamination")
else:
    for _, r in obe_anom.iterrows():
        print(f"{r['datum'].strftime('%Y-%m')}  |  {r['stevilo_reklamacij']:.0f} reklamacij  "
              f"|  z={r['z_score']:.2f}  |  IF={r['if_anom_score']:.3f}")

# ── 6. POVZETEK ZA NALOGO ────────────────────────────────────────────────────

print(f"\n── Povzetek za diplomsko nalogo ──")
print(f"Skupaj mesečnih točk:        {len(df)}")
print(f"Z-Score anomalije (|z|>2):   {df['anomalija_zscore'].sum()} "
      f"({df['anomalija_zscore'].sum()/len(df)*100:.1f}%)")
print(f"Isolation Forest anomalije:  {df['anomalija_if'].sum()} "
      f"({df['anomalija_if'].sum()/len(df)*100:.1f}%)")
print(f"Potrjene z obema:            {df['anomalija_obe'].sum()}")

# ── 7. VIZUALIZACIJA ─────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 14))
gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.5, wspace=0.35)
fig.suptitle('Detekcija anomalij v mesečnih reklamacijah Fotone (2013–2024)',
             fontsize=14, fontweight='bold')

# ── Graf 1: Časovna vrsta z anomalijami ──────────────────────────────────────
ax1 = fig.add_subplot(gs[0, :])

ax1.plot(df['datum'], df['stevilo_reklamacij'],
         'o-', color='#534AB7', linewidth=1.8, markersize=4,
         label='Mesečne reklamacije', zorder=3)
ax1.plot(df['datum'], df['rolling_mean_3m'],
         '--', color='gray', linewidth=1.2, alpha=0.6,
         label='Drseče povprečje (3M)')

# Z-Score anomalije
z_anom = df[df['anomalija_zscore']]
ax1.scatter(z_anom['datum'], z_anom['stevilo_reklamacij'],
            color='#e74c3c', s=80, zorder=5, label='Z-Score anomalija', marker='o')

# IF anomalije ki niso z-score
if_only = df[df['anomalija_if'] & ~df['anomalija_zscore']]
ax1.scatter(if_only['datum'], if_only['stevilo_reklamacij'],
            color='#e67e22', s=80, zorder=5,
            label='Isolation Forest anomalija', marker='D')

# Potrjene z obema
obe = df[df['anomalija_obe']]
ax1.scatter(obe['datum'], obe['stevilo_reklamacij'],
            color='#c0392b', s=150, zorder=6,
            label='Potrjeno z obema ★', marker='*')


ax1.set_xlabel('Datum')
ax1.set_ylabel('Število reklamacij')
ax1.set_title('Mesečne reklamacije z označenimi anomalijami')
ax1.legend(fontsize=8, ncol=3, framealpha=0.8)
ax1.grid(axis='y', alpha=0.2)

# ── Graf 2: Z-Score skozi čas ────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, :])

ax2.bar(df['datum'], df['z_score'],
        color=np.where(df['z_score'].abs() > Z_THRESHOLD, '#e74c3c', '#534AB7'),
        alpha=0.75, width=25)
ax2.axhline(y= Z_THRESHOLD, color='red', linestyle='--',
            linewidth=1.2, alpha=0.7, label=f'+{Z_THRESHOLD} prag')
ax2.axhline(y=-Z_THRESHOLD, color='red', linestyle='--',
            linewidth=1.2, alpha=0.7, label=f'-{Z_THRESHOLD} prag')
ax2.axhline(y=0, color='black', linewidth=0.8)

for _, r in z_anom.iterrows():
    offset = 0.1 if r['z_score'] > 0 else -0.3
    ax2.annotate(r['datum'].strftime('%Y-%m'),
                 (r['datum'], r['z_score'] + offset),
                 fontsize=7, ha='center', color='#c0392b', fontweight='bold')

ax2.set_xlabel('Datum')
ax2.set_ylabel('Z-Score')
ax2.set_title('Z-Score po mesecih (rdeče = anomalija)')
ax2.legend(fontsize=9)
ax2.grid(axis='y', alpha=0.2)

# ── Graf 3: Isolation Forest score ───────────────────────────────────────────
ax3 = fig.add_subplot(gs[2, 0])

scatter_colors = np.where(df['anomalija_if'], '#e74c3c', '#534AB7')
ax3.scatter(df['datum'], df['if_anom_score'],
            c=scatter_colors, alpha=0.75, s=40)

# Prag med normalnimi in anomalijami
threshold_if = df[df['anomalija_if']]['if_anom_score'].max()
ax3.axhline(y=threshold_if, color='red', linestyle='--',
            linewidth=1.2, alpha=0.7, label=f'Prag ({threshold_if:.3f})')

ax3.set_xlabel('Datum')
ax3.set_ylabel('Anomaly score (nižji = bolj anomalen)')
ax3.set_title('Isolation Forest anomaly score\n(rdeče = anomalija)')
ax3.legend(fontsize=9)
ax3.grid(alpha=0.2)

# ── Graf 4: Sezonski vzorec ───────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[2, 1])

mesec_labels = ['Jan','Feb','Mar','Apr','Maj','Jun',
                'Jul','Avg','Sep','Okt','Nov','Dec']
mesecno = df.groupby('mesec')['stevilo_reklamacij'].agg(['mean','std']).reset_index()

ax4.bar(mesec_labels, mesecno['mean'],
        color='#534AB7', alpha=0.75, label='Povprečje')
ax4.errorbar(mesec_labels, mesecno['mean'], yerr=mesecno['std'],
             fmt='none', color='gray', capsize=4, linewidth=1.2)

ax4.set_xlabel('Mesec')
ax4.set_ylabel('Povprečno število reklamacij')
ax4.set_title('Sezonski vzorec reklamacij\n(2013–2024)')
ax4.legend(fontsize=9)
ax4.grid(axis='y', alpha=0.2)

plt.savefig('fotona_anomaly_detection.png', dpi=150, bbox_inches='tight')
plt.show()
print("\nGraf shranjen: fotona_anomaly_detection.png")

# ── 8. IZVOZI CSV ZA POWER BI ────────────────────────────────────────────────

df_export = df[['datum', 'leto', 'mesec', 'stevilo_reklamacij',
                'z_score', 'anomalija_zscore', 'tip_zscore',
                'if_anom_score', 'anomalija_if', 'anomalija_obe']].copy()
df_export['datum'] = df_export['datum'].dt.strftime('%Y-%m-%d')
df_export.to_csv('fotona_anomalije.csv', index=False, encoding='utf-8-sig')
print("Izvoženo: fotona_anomalije.csv")