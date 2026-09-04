# -*- coding: utf-8 -*-
"""
A4: detekcija anomalij (N-RV2) — enaka metoda kot pri Fotoni:
konsenz Z-score in Isolation Forest.

Z-score se racuna na tedenskih razlikah (ne na surovi nestacionarni vrsti);
Isolation Forest na znacilkah [razlika, drseci std 4 tedne, odmik od
drsecega povprecja]. Anomalija = konsenz obeh metod. Vsaka zaznana
anomalija se poskusi domensko pojasniti (praznik, izpad porocanja,
sprememba nabora VZS).

Izhodi: rezultati/a4_anomalije.csv, visualizations/a4_anomalije.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

import izbor_storitev as iz

BASE = Path(__file__).resolve().parents[1]
REZ, VIZ = BASE / "rezultati", BASE / "visualizations"

panel = iz.nalozi_panel()
imena = dict(iz.IZBRANE, **{iz.AGREGAT: "Agregat"})

vse = []
for s in list(iz.IZBRANE) + [iz.AGREGAT]:
    df = iz.tedenska_vrsta(panel, s)
    y = df["cak_skupaj"].dropna()
    d = y.diff().dropna()

    z = (d - d.mean()) / d.std()

    feat = pd.DataFrame({
        "razlika": d,
        "drseci_std4": d.rolling(4, min_periods=2).std(),
        "odmik_ma4": y - y.rolling(4, min_periods=2).mean(),
    }).dropna()
    X = StandardScaler().fit_transform(feat)
    iforest = IsolationForest(n_estimators=200, contamination=0.05,
                              random_state=42)
    if_flag = pd.Series(iforest.fit_predict(X) == -1, index=feat.index)

    rez = pd.DataFrame({
        "vzs": s, "naziv": imena[s],
        "datum": d.index, "razlika": d.values,
        "z": z.values,
        "z_flag": (z.abs() > 2).values,
        "if_flag": if_flag.reindex(d.index, fill_value=False).values,
    })
    rez["konsenz"] = rez["z_flag"] & rez["if_flag"]
    vse.append(rez)

anom = pd.concat(vse, ignore_index=True)
kons = anom[anom["konsenz"]].copy()

# domenska razlaga: blizina praznika (+/- 10 dni) ali soseščina manjkajočega tedna
prazniki = iz.PRAZNIKI


def razlaga(dat: pd.Timestamp) -> str:
    if any(abs((dat - p).days) <= 10 for p in prazniki):
        return "praznik +/-10 dni"
    return "brez ocitne domenske razlage"


kons["razlaga"] = kons["datum"].apply(razlaga)
anom.round(3).to_csv(REZ / "a4_anomalije_vse.csv", index=False, encoding="utf-8-sig")
kons.round(3).to_csv(REZ / "a4_anomalije.csv", index=False, encoding="utf-8-sig")

print(f"Vseh testiranih tock: {len(anom)}; Z-flag: {int(anom.z_flag.sum())}, "
      f"IF-flag: {int(anom.if_flag.sum())}, konsenz: {len(kons)}")
print("\nKonsenzne anomalije:")
print(kons[["naziv", "datum", "razlika", "z", "razlaga"]].to_string(index=False))

# graf: agregat z oznacenimi konsenznimi anomalijami
ag = iz.tedenska_vrsta(panel, iz.AGREGAT)["cak_skupaj"]
ka = kons[kons["vzs"] == iz.AGREGAT]
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(ag.index, ag.values, lw=1.2, color="#1f4e79", label="agregat")
ax.scatter(ka["datum"], ag.reindex(ka["datum"]).values, color="#c00000",
           zorder=5, label="konsenzna anomalija")
for pr in prazniki:
    ax.axvline(pr, color="grey", alpha=0.2, lw=0.7)
ax.set_title("Detekcija anomalij v agregatu (konsenz Z-score + Isolation Forest)")
ax.set_ylabel("Skupno število čakajočih")
ax.legend()
fig.tight_layout()
fig.savefig(VIZ / "a4_anomalije.png", dpi=150)
plt.close(fig)
