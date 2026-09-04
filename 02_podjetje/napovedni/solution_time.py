import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings
from sqlalchemy import text
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import (RandomForestRegressor, GradientBoostingRegressor,
                              HistGradientBoostingRegressor)
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import TimeSeriesSplit
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
    df = pd.read_sql(text(f"""
        SELECT
            DATEDIFF(z.datum_zakljucka_rekl, pr.datum_prejema) AS casi_resevanja_dni,
            ar.kategorija,
            YEAR(pr.datum_prejema)                             AS leto,
            MONTH(pr.datum_prejema)                            AS mesec,
            COALESCE(r.garancija, 0)                           AS garancija
        FROM zakljucek_reklamacije z
        JOIN prejem_reklamacije pr  ON pr.reklamacija_id = z.reklamacija_id
        JOIN {ANALIZA_REKLAMACIJE_KAT} ar ON ar.reklamacija_id = z.reklamacija_id
        JOIN reklamacija r          ON r.stevilka_reklamacije = z.reklamacija_id
        WHERE z.datum_zakljucka_rekl IS NOT NULL
          AND pr.datum_prejema IS NOT NULL
          AND ar.kategorija IS NOT NULL
          AND ar.kategorija != 'Nerazporejeno'
          AND DATEDIFF(z.datum_zakljucka_rekl, pr.datum_prejema) BETWEEN 1 AND 730
        ORDER BY pr.datum_prejema
    """), conn)

print(f"Naloženo: {len(df)} reklamacij")
print(f"Kategorije: {df['kategorija'].nunique()}")
print(f"Leta: {df['leto'].min()}–{df['leto'].max()}")
print(f"Garancija: {df['garancija'].value_counts().to_dict()}")
print(f"\nPovprečen čas reševanja: {df['casi_resevanja_dni'].mean():.1f} dni")
print(f"Mediana: {df['casi_resevanja_dni'].median():.1f} dni")
print(f"Std: {df['casi_resevanja_dni'].std():.1f} dni")

# ── 2. OPISNA ANALIZA ────────────────────────────────────────────────────────

print("\n── Povprečen čas reševanja po kategoriji ──")
kat_stats = (df.groupby('kategorija')['casi_resevanja_dni']
             .agg(['mean','median','std','count'])
             .round(1)
             .sort_values('mean', ascending=False))
kat_stats.columns = ['povprecje', 'mediana', 'std', 'n']
print(kat_stats.to_string())

print("\n── Povprečen čas reševanja: garancija vs. negarancija ──")
gar_stats = (df.groupby('garancija')['casi_resevanja_dni']
             .agg(['mean','median','count'])
             .round(1))
gar_stats.index = ['Negarancija (0)', 'Garancija (1)']
print(gar_stats.to_string())

print("\n── Trend časa reševanja po letu ──")
leto_stats = (df.groupby('leto')['casi_resevanja_dni']
              .agg(['mean','median','count'])
              .round(1))
print(leto_stats.to_string())

# ── 3. FEATURE ENGINEERING ───────────────────────────────────────────────────

# Enkodiranje kategorij
le = LabelEncoder()
df['kategorija_enc'] = le.fit_transform(df['kategorija'])

# Sezonska komponenta
df['je_Q1'] = (df['mesec'].isin([1,2,3])).astype(int)
df['je_Q2'] = (df['mesec'].isin([4,5,6])).astype(int)
df['je_Q3'] = (df['mesec'].isin([7,8,9])).astype(int)
df['je_Q4'] = (df['mesec'].isin([10,11,12])).astype(int)

# Trend leto (normaliziran)
df['leto_norm'] = (df['leto'] - df['leto'].min()) / (df['leto'].max() - df['leto'].min())

# Feature matrika
feature_cols = ['kategorija_enc', 'garancija', 'leto_norm',
                'je_Q1', 'je_Q2', 'je_Q3']
X = df[feature_cols].values
y = df['casi_resevanja_dni'].values

print(f"\nFeaturi: {feature_cols}")
print(f"Vzorec: {len(X)} reklamacij")

# ── 4. MODELI ────────────────────────────────────────────────────────────────
#
# Tarča je izrazito asimetrična (mediana 43 dni, rep do 730 dni), zato modele
# učimo na log-transformirani tarči in metrike računamo nazaj v dnevih.
# Validacija: TimeSeriesSplit — podatki so urejeni po datumu prejema in
# porazdelitev časov se s časom spreminja, zato navadni k-fold ni primeren
# (vsak fold bi bil drugo časovno obdobje oz. bi mešal prihodnost v trening).

y_log = np.log1p(y)

modeli = {
    'Linearna regresija':     LinearRegression(),
    'Ridge regresija':        Ridge(alpha=1.0),
    'Random Forest':          RandomForestRegressor(n_estimators=100, random_state=42),
    'Gradient Boosting':      GradientBoostingRegressor(n_estimators=100, random_state=42),
    'HistGB (mediana)':       HistGradientBoostingRegressor(loss='quantile', quantile=0.5,
                                                            random_state=42),
}

tscv = TimeSeriesSplit(n_splits=5)

print("\n── TimeSeriesSplit validacija (5 foldov, log-tarča, metrike v dnevih) ──")
print(f"{'Model':<25} {'MAE':>8} {'RMSE':>8} {'R²':>7}")
print("-" * 52)

cv_results = {}
for name, model in modeli.items():
    maes, rmses, r2s = [], [], []
    for tr_idx, te_idx in tscv.split(X):
        model.fit(X[tr_idx], y_log[tr_idx])
        pred = np.expm1(model.predict(X[te_idx]))
        maes.append(mean_absolute_error(y[te_idx], pred))
        rmses.append(np.sqrt(mean_squared_error(y[te_idx], pred)))
        r2s.append(r2_score(y[te_idx], pred))
    cv_results[name] = {'MAE': np.mean(maes), 'RMSE': np.mean(rmses), 'R2': np.mean(r2s)}
    print(f"{name:<25} {cv_results[name]['MAE']:>8.1f} "
          f"{cv_results[name]['RMSE']:>8.1f} {cv_results[name]['R2']:>7.3f}")

# Baseline: napoved z mediano trening obdobja (model mora premagati vsaj to)
maes_baseline = []
for tr_idx, te_idx in tscv.split(X):
    napoved_mediana = np.full(len(te_idx), np.median(y[tr_idx]))
    maes_baseline.append(mean_absolute_error(y[te_idx], napoved_mediana))
mae_baseline = np.mean(maes_baseline)
print(f"{'Baseline (mediana)':<25} {mae_baseline:>8.1f}")

# Najboljši model
best_name = min(cv_results, key=lambda k: cv_results[k]['MAE'])
print(f"\nNajboljši model: {best_name} (MAE={cv_results[best_name]['MAE']:.1f}, "
      f"baseline mediana MAE={mae_baseline:.1f})")

# ── 5. POMEMBNOST ZNAČILK ────────────────────────────────────────────────────

rf_imp = RandomForestRegressor(n_estimators=100, random_state=42).fit(X, y_log)
importance = (pd.DataFrame({'feature': feature_cols,
                            'importance': rf_imp.feature_importances_})
              .sort_values('importance', ascending=False)
              .reset_index(drop=True))

print("\n── Pomembnost značilk (Random Forest) ──")
print(importance.round(3).to_string(index=False))


# ── 6. NAPOVEDI PO KATEGORIJI IN GARANCIJI ───────────────────────────────────

print("\n── Napoved časa reševanja za 2025 (kvantilni model, mediana + [P10–P90]) ──")

# Kvantilni modeli na log-tarči: kvantili so invariantni na monotono
# transformacijo, zato je expm1(kvantil na log skali) = kvantil v dnevih.
# Interval [P10, P90] pove: 80 % reklamacij se reši znotraj tega razpona.
q_modeli = {
    q: HistGradientBoostingRegressor(loss='quantile', quantile=q,
                                     random_state=42).fit(X, y_log)
    for q in (0.1, 0.5, 0.9)
}

def napovej_kvantile(x_pred):
    """Vrne (P10, mediana, P90) v dnevih, vsaj 1 dan."""
    p10, p50, p90 = (max(1.0, float(np.expm1(q_modeli[q].predict(x_pred)[0])))
                     for q in (0.1, 0.5, 0.9))
    return p10, p50, p90

kategorije_list = le.classes_
print(f"\n{'Kategorija':<35} {'Gar.':>5} {'Mediana (dni)':>14} {'[P10–P90]':>15}")
print("-" * 72)

for kat in sorted(kategorije_list):
    kat_enc = le.transform([kat])[0]
    for gar in [0, 1]:
        # leto_norm za 2025
        leto_norm_2025 = (2025 - df['leto'].min()) / (df['leto'].max() - df['leto'].min())
        x_pred = np.array([[kat_enc, gar, leto_norm_2025, 0, 1, 0]])  # Q2 kot povprečje
        p10, p50, p90 = napovej_kvantile(x_pred)

        kat_s = kat.replace('Neskladnost ', '').replace(' komponent', '')
        gar_s = 'DA' if gar else 'NE'
        print(f"{kat_s:<35} {gar_s:>5} {p50:>14.0f} "
              f"  [{p10:.0f}–{p90:.0f}]")

# ── 7. IZVOZI CSV ────────────────────────────────────────────────────────────

# Napovedi za vse kombinacije kategorija × garancija × leto
rows = []
for kat in sorted(kategorije_list):
    kat_enc = le.transform([kat])[0]
    for gar in [0, 1]:
        for leto in [2023, 2024, 2025]:
            leto_norm = (leto - df['leto'].min()) / (df['leto'].max() - df['leto'].min())
            x_pred = np.array([[kat_enc, gar, leto_norm, 0, 1, 0]])
            p10, p50, p90 = napovej_kvantile(x_pred)
            rows.append({
                'kategorija': kat,
                'garancija': 'DA' if gar else 'NE',
                'leto': leto,
                'napoved_dni': round(p50),
                'p10_dni': round(p10),
                'p90_dni': round(p90),
            })

df_napovedi = pd.DataFrame(rows)
df_napovedi.to_csv('fotona_napoved_casi.csv', index=False, encoding='utf-8-sig')
print("\nIzvoženo: fotona_napoved_casi.csv")

# ── 8. VIZUALIZACIJA ─────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 14))
gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.5, wspace=0.35)
fig.suptitle('Regresijski model: napoved časa reševanja reklamacij',
             fontsize=14, fontweight='bold')

colors_kat = {
    'Neskladnost optičnih komponent':     '#534AB7',
    'Neskladnost elektronskih komponent': '#0F6E56',
    'Neskladnost mehanskih komponent':    '#D85A30',
    'Ni tehnična napaka':                 '#888780',
    'Neskladnost enote za sprej':         '#BA7517',
    'Neskladnost hladilnega sistema':     '#185FA5',
}

# Graf 1: Povprečen čas po kategoriji (boxplot)
ax1 = fig.add_subplot(gs[0, :])
kat_order = (df.groupby('kategorija')['casi_resevanja_dni']
             .mean().sort_values(ascending=True).index.tolist())
data_box = [df[df['kategorija']==k]['casi_resevanja_dni'].values for k in kat_order]
labels_box = [k.replace('Neskladnost ','').replace(' komponent','') for k in kat_order]
bp = ax1.boxplot(data_box, vert=False, patch_artist=True,
                 medianprops=dict(color='white', linewidth=2))
for patch, kat in zip(bp['boxes'], kat_order):
    patch.set_facecolor(colors_kat.get(kat, '#333'))
    patch.set_alpha(0.75)
ax1.set_yticklabels(labels_box, fontsize=9)
ax1.set_xlabel('Čas reševanja (dni)')
ax1.set_title('Porazdelitev časa reševanja po kategoriji napake')
ax1.grid(axis='x', alpha=0.2)

# Graf 2: Garancija vs negarancija
ax2 = fig.add_subplot(gs[1, 0])
gar_data = [df[df['garancija']==0]['casi_resevanja_dni'].values,
            df[df['garancija']==1]['casi_resevanja_dni'].values]
bp2 = ax2.boxplot(gar_data, patch_artist=True,
                  medianprops=dict(color='white', linewidth=2))
bp2['boxes'][0].set_facecolor('#D85A30'); bp2['boxes'][0].set_alpha(0.75)
bp2['boxes'][1].set_facecolor('#0F6E56'); bp2['boxes'][1].set_alpha(0.75)
ax2.set_xticklabels(['Negarancija', 'Garancija'])
ax2.set_ylabel('Čas reševanja (dni)')
ax2.set_title('Čas reševanja: garancija vs. negarancija')
ax2.grid(axis='y', alpha=0.2)

# Graf 3: Trend po letu
ax3 = fig.add_subplot(gs[1, 1])
leto_mean = df.groupby('leto')['casi_resevanja_dni'].mean()
ax3.plot(leto_mean.index, leto_mean.values, 'o-',
         color='#534AB7', linewidth=2, markersize=6)
ax3.set_xlabel('Leto')
ax3.set_ylabel('Povprečen čas reševanja (dni)')
ax3.set_title('Trend časa reševanja po letu')
ax3.grid(alpha=0.2)
ax3.tick_params(axis='x', rotation=45)

# Graf 4: Feature importance
ax4 = fig.add_subplot(gs[2, 0])
feat_labels = [f.replace('kategorija_enc', 'kategorija')
               .replace('leto_norm', 'leto')
               .replace('garancija', 'garancija')
               .replace('je_Q', 'Q') for f in importance['feature']]
ax4.barh(feat_labels, importance['importance'],
         color='#534AB7', alpha=0.8)
ax4.set_xlabel('Pomembnost (Random Forest)')
ax4.set_title('Vpliv spremenljivk na čas reševanja')
ax4.grid(axis='x', alpha=0.2)

# Graf 5: MAE primerjava modelov
ax5 = fig.add_subplot(gs[2, 1])
model_names = list(cv_results.keys())
mae_vals    = [cv_results[m]['MAE'] for m in model_names]
bar_colors  = ['#e74c3c' if n == best_name else '#b0b0b0' for n in model_names]
bars = ax5.bar([m.replace(' regresija','').replace(' ','  ') for m in model_names],
               mae_vals, color=bar_colors, alpha=0.85)
for bar, mae in zip(bars, mae_vals):
    ax5.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
             f'{mae:.1f}', ha='center', fontsize=9, fontweight='bold')
ax5.set_ylabel('MAE (TimeSeriesSplit CV)')
ax5.set_title('Primerjava modelov\n(rdeča = najboljši)')
ax5.grid(axis='y', alpha=0.2)
ax5.tick_params(axis='x', rotation=15)

plt.savefig('fotona_casi_model.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_casi_model.png")

# ── 9. SKLEP ─────────────────────────────────────────────────────────────────

print(f"\n── Sklep za diplomsko nalogo ──")
print(f"Najboljši model: {best_name}")
print(f"MAE: {cv_results[best_name]['MAE']:.1f} dni (povprečna napaka napovedi)")
print(f"Baseline (mediana treninga): MAE {mae_baseline:.1f} dni")
print(f"R²:  {cv_results[best_name]['R2']:.3f}")

izboljsava_pct = (mae_baseline - cv_results[best_name]['MAE']) / mae_baseline * 100
if izboljsava_pct > 5:
    print(f"Model premaga baseline za {izboljsava_pct:.1f} % — featurji nosijo napovedno moč.")
else:
    print(f"Model premaga baseline le za {izboljsava_pct:.1f} % — razpoložljivi featurji")
    print("(kategorija, garancija, leto, sezona) ne pojasnijo variance časov reševanja.")
if cv_results[best_name]['R2'] <= 0.3:
    print("Nizek R² — čas reševanja je visoko variabilen; smiselno je poročati")
    print("kvantilne intervale [P10–P90] namesto točkovnih napovedi.")
print(f"\nNajpomembnejši prediktor: {importance.iloc[0]['feature']}")
print(f"Garancijske reklamacije trajajo v povprečju "
      f"{df[df['garancija']==1]['casi_resevanja_dni'].mean():.1f} dni, "
      f"negarancijske pa {df[df['garancija']==0]['casi_resevanja_dni'].mean():.1f} dni.")

# ── 10. INTERVALNI GRAF KVANTILNIH NAPOVEDI ZA 2025 ──────────────────────────
# Napovedi (P10, P50, P90) za 2025 so že zbrane v df_napovedi (razdelek 7),
# zato modelov ne učimo ponovno.

from matplotlib.lines import Line2D

df_int = df_napovedi[df_napovedi['leto'] == 2025].copy()

# Pri več kot 12 kombinacijah obdrži le kategorije z vsaj 100 reklamacijami
if len(df_int) > 12:
    n_po_kat = df['kategorija'].value_counts()
    df_int = df_int[df_int['kategorija'].isin(n_po_kat[n_po_kat >= 100].index)]

imenovalnik = {
    'Neskladnost optičnih komponent':     'Optične komponente',
    'Neskladnost elektronskih komponent': 'Elektronske komponente',
    'Neskladnost mehanskih komponent':    'Mehanske komponente',
    'Neskladnost hladilnega sistema':     'Hladilni sistem',
    'Neskladnost enote za sprej':         'Enota za sprej',
    'Ni tehnična napaka':                 'Ni tehnična napaka',
}
gar_pripona = {'DA': 'z garancijo', 'NE': 'brez garancije'}
df_int['oznaka'] = (df_int['kategorija'].map(imenovalnik).fillna(df_int['kategorija'])
                    + ', ' + df_int['garancija'].map(gar_pripona))

# P50 padajoče: vrstice z najdaljšimi časi zgoraj (najvišji y)
df_int = df_int.sort_values('napoved_dni', ascending=True).reset_index(drop=True)

barve_gar = {'NE': '#185FA5', 'DA': '#8FBCE0'}  # temnejša = brez garancije

fig_i, ax_i = plt.subplots(figsize=(10, 6))
odmik = df_int['p90_dni'].max() * 0.02
for i, vrstica in df_int.iterrows():
    barva = barve_gar[vrstica['garancija']]
    ax_i.hlines(i, vrstica['p10_dni'], vrstica['p90_dni'],
                color=barva, linewidth=2.5)
    ax_i.plot(vrstica['napoved_dni'], i, 'o', color=barva, markersize=8)
    ax_i.text(vrstica['p90_dni'] + odmik, i,
              f"{vrstica['napoved_dni']:.0f} "
              f"({vrstica['p10_dni']:.0f}–{vrstica['p90_dni']:.0f})",
              va='center', fontsize=11)

ax_i.set_yticks(range(len(df_int)))
ax_i.set_yticklabels(df_int['oznaka'], fontsize=11)
ax_i.set_xlabel('Napovedan čas reševanja (dni)', fontsize=12)
ax_i.tick_params(axis='x', labelsize=11)
ax_i.set_xlim(0, df_int['p90_dni'].max() * 1.25)
ax_i.grid(axis='x', alpha=0.3)
ax_i.set_axisbelow(True)

legenda = [Line2D([0], [0], color=barve_gar['DA'], marker='o', markersize=8,
                  linewidth=2.5, label='Z garancijo'),
           Line2D([0], [0], color=barve_gar['NE'], marker='o', markersize=8,
                  linewidth=2.5, label='Brez garancije')]
ax_i.legend(handles=legenda, fontsize=11, loc='lower right')

plt.tight_layout()
plt.savefig('fotona_casi_intervali_2025.png', dpi=150, bbox_inches='tight')
plt.show()
print("Graf shranjen: fotona_casi_intervali_2025.png")