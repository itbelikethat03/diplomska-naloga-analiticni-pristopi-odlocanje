# -*- coding: utf-8 -*-
"""
A2: opisna statistika in trendi; A3: sezonskost (N-RV2).

Izhodi:
- rezultati/a2_opisna_statistika.csv (izbrane storitve + agregat)
- rezultati/a2_trendi.csv (linearni trend z IZ, celotno obdobje)
- rezultati/a2_top_rast_padec.csv (vse popolne vrste)
- visualizations/a2_agregat.png, a2_storitve.png, a2_nujnost.png
- visualizations/a3_sezonskost_agregat.png, a3_stl_agregat.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.seasonal import STL

import izbor_storitev as iz

BASE = Path(__file__).resolve().parents[1]
REZ, VIZ = BASE / "rezultati", BASE / "visualizations"

panel = iz.nalozi_panel()
vrste = {s: iz.tedenska_vrsta(panel, s) for s in list(iz.IZBRANE) + [iz.AGREGAT]}
imena = dict(iz.IZBRANE, **{iz.AGREGAT: "Agregat (282 VZS s popolnimi vrstami)"})

# ------------------------------------------------------- A2 opisna statistika
rows = []
for s, df in vrste.items():
    for kaz in ("cak_skupaj", "cd_redno"):
        y = df[kaz].dropna()
        rows.append({
            "vzs": s, "naziv": imena[s], "kazalnik": kaz, "n": len(y),
            "povprecje": y.mean(), "mediana": y.median(), "std": y.std(),
            "min": y.min(), "max": y.max(),
            "zacetek": y.iloc[0], "konec": y.iloc[-1],
            "sprememba_pct": 100 * (y.iloc[-1] / y.iloc[0] - 1),
        })
opisna = pd.DataFrame(rows).round(1)
opisna.to_csv(REZ / "a2_opisna_statistika.csv", index=False, encoding="utf-8-sig")
print("A2 opisna statistika (cak_skupaj):")
print(opisna[opisna.kazalnik == "cak_skupaj"]
      [["naziv", "povprecje", "min", "max", "sprememba_pct"]].to_string(index=False))

# ------------------------------------------------------------- A2 lin. trend
trendi = []
for s, df in vrste.items():
    for kaz in ("cak_skupaj", "cd_redno"):
        y = df[kaz].dropna()
        t = np.arange(len(y))
        ols = sm.OLS(y.values, sm.add_constant(t)).fit()
        ci = ols.conf_int()[1]
        trendi.append({
            "vzs": s, "naziv": imena[s], "kazalnik": kaz,
            "naklon_teden": ols.params[1], "ci_spodnja": ci[0], "ci_zgornja": ci[1],
            "p": ols.pvalues[1], "r2": ols.rsquared,
        })
pd.DataFrame(trendi).round(4).to_csv(REZ / "a2_trendi.csv", index=False,
                                     encoding="utf-8-sig")

# ------------------------------------- A2 najvecja rast/padec (vse popolne)
pop = iz.popolne_sifre(panel)
sub = panel[panel["vzs_sifra"].isin(pop)]
prva = sub[sub["datum"] == sub["datum"].min()].set_index("vzs_sifra")
zadnja = sub[sub["datum"] == sub["datum"].max()].set_index("vzs_sifra")
rast = pd.DataFrame({
    "vzs_naziv": zadnja["vzs_naziv"],
    "cak_zacetek": prva["cak_skupaj"], "cak_konec": zadnja["cak_skupaj"],
})
rast["sprememba"] = rast["cak_konec"] - rast["cak_zacetek"]
rast["sprememba_pct"] = 100 * rast["sprememba"] / rast["cak_zacetek"].clip(lower=1)
rast = rast.sort_values("sprememba", ascending=False)
rast.round(1).to_csv(REZ / "a2_top_rast_padec.csv", encoding="utf-8-sig")
print("\nNajvecja rast stevila cakajocih (absolutno):")
print(rast.head(5)[["vzs_naziv", "cak_zacetek", "cak_konec"]].to_string())
print("\nNajvecji padec:")
print(rast.tail(5)[["vzs_naziv", "cak_zacetek", "cak_konec"]].to_string())

# ------------------------------------------------------------------- grafi
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})

ag = vrste[iz.AGREGAT]
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(ag.index, ag["cak_skupaj"], lw=1.2, color="#1f4e79")
for pr in iz.PRAZNIKI:
    ax.axvline(pr, color="grey", alpha=0.25, lw=0.7)
ax.set_title("Skupno število čakajočih (282 VZS s popolnimi vrstami); "
             "sive črte = prazniki")
ax.set_ylabel("Število čakajočih")
fig.tight_layout()
fig.savefig(VIZ / "a2_agregat.png", dpi=150)
plt.close(fig)

fig, axes = plt.subplots(3, 2, figsize=(11, 8), sharex=True)
for ax, (s, naziv) in zip(axes.ravel(), iz.IZBRANE.items()):
    df = vrste[s]
    ax.plot(df.index, df["cak_skupaj"], lw=1.1, color="#1f4e79")
    ax.set_title(f"{naziv} ({s})", fontsize=9)
fig.suptitle("Število čakajočih — izbrane storitve", y=0.995)
fig.tight_layout()
fig.savefig(VIZ / "a2_storitve.png", dpi=150)
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 4.5))
for kaz, lab, c in (("cak_zelo_hitro", "Zelo hitro", "#c00000"),
                    ("cak_hitro", "Hitro", "#e69f00"),
                    ("cak_redno", "Redno", "#1f4e79")):
    ax.plot(ag.index, ag[kaz], lw=1.1, label=lab, color=c)
ax.legend()
ax.set_title("Število čakajočih po stopnji nujnosti (agregat)")
fig.tight_layout()
fig.savefig(VIZ / "a2_nujnost.png", dpi=150)
plt.close(fig)

# ------------------------------------------------------------- A3 sezonskost
r = iz.redna_tedenska(ag["cak_skupaj"])
r["leto"] = r.index.isocalendar().year
r["iso_teden"] = r.index.isocalendar().week

fig, ax = plt.subplots(figsize=(10, 4.5))
for leto, g in r.groupby("leto"):
    ax.plot(g["iso_teden"], g["y"], lw=1.2, label=str(leto))
ax.set_xlabel("ISO teden v letu")
ax.set_ylabel("Skupno število čakajočih")
ax.set_title("Primerjava istoležnih tednov med leti (agregat)")
ax.legend(title="Leto")
fig.tight_layout()
fig.savefig(VIZ / "a3_sezonskost_agregat.png", dpi=150)
plt.close(fig)

stl = STL(r["y"], period=52, robust=True).fit()
fig = stl.plot()
fig.set_size_inches(10, 7)
fig.suptitle("STL-razgradnja agregata (opisno; le 2 polna letna cikla)", y=1.0)
fig.tight_layout()
fig.savefig(VIZ / "a3_stl_agregat.png", dpi=150)
plt.close(fig)

sez_moc = stl.seasonal.std() / r["y"].std()
print(f"\nA3: std sezonske komponente / std vrste = {sez_moc:.3f} (opisno)")

# medletna primerjava povprecij po sezonah (poletje w26-35, zima w48-8)
r["sezona"] = np.select(
    [r["iso_teden"].between(26, 35), (r["iso_teden"] >= 48) | (r["iso_teden"] <= 8)],
    ["poletje", "zima"], default="drugo")
print("\nPovprecje agregata po sezonah in letih:")
print(r.groupby(["leto", "sezona"])["y"].mean().round(0).unstack().to_string())
