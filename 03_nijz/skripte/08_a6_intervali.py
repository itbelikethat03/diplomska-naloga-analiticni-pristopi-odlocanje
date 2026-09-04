# -*- coding: utf-8 -*-
"""
A6: intervalne napovedi in analiza negotovosti (N-RV3/RV4).

Dva pristopa, oba brez uhajanja podatkov:
1) empiricni intervali P10-P90 iz ostankov walk-forward napovedi AR(1)
   (za stevilo cakajocih): za vsako testno tocko se kvantili ostankov
   ocenijo SAMO iz ostankov prejsnjih testnih tock (rastoci nabor,
   najmanj 20 ostankov), nato se preveri pokritost;
2) kvantilni Gradient Boosting (P10/P50/P90) za cakalno dobo (cd_redno)
   kot sekundarno spremenljivko — vzporednica kvantilnemu modelu casov
   resevanja pri Fotoni.

Izhodi: rezultati/a6_pokritost.csv, visualizations/a6_intervali_agregat.png,
        a6_kvantilni_cd.png
"""

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

import izbor_storitev as iz

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parents[1]
REZ, VIZ = BASE / "rezultati", BASE / "visualizations"

MIN_OSTANKOV = 20

# ------------------------------------------------ 1) empiricni intervali AR(1)
dolge = pd.read_csv(REZ / "a5_napovedi_dolge.csv", parse_dates=["izvor", "cilj"])
imena = dict(iz.IZBRANE, **{iz.AGREGAT: "Agregat"})

rows, band_ag = [], None
for (s, h), g in dolge[(dolge.model == "ar1") & dolge.opazovan].groupby(["vzs", "horizont"]):
    g = g.sort_values("cilj").reset_index(drop=True)
    g["ost"] = g.y_true - g.y_pred
    lo, hi, pokrit = [], [], []
    for i in range(len(g)):
        pret = g["ost"].iloc[:i]  # samo pretekli ostanki
        if len(pret) < MIN_OSTANKOV:
            lo.append(np.nan); hi.append(np.nan); pokrit.append(np.nan)
            continue
        q10, q90 = pret.quantile(0.1), pret.quantile(0.9)
        l, zg = g.y_pred[i] + q10, g.y_pred[i] + q90
        lo.append(l); hi.append(zg)
        pokrit.append(int(l <= g.y_true[i] <= zg))
    g["lo"], g["hi"], g["pokrit"] = lo, hi, pokrit
    veljavne = g.dropna(subset=["pokrit"])
    rows.append({
        "vzs": s, "naziv": imena.get(s, s), "spremenljivka": "cak_skupaj",
        "metoda": "empiricni AR(1)", "horizont": h, "n": len(veljavne),
        "pokritost": veljavne["pokrit"].mean(),
        "sirina_povp": (veljavne["hi"] - veljavne["lo"]).mean(),
    })
    if s == iz.AGREGAT and h == 1:
        band_ag = g

# graf za agregat
if band_ag is not None:
    v = band_ag.dropna(subset=["lo"])
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(band_ag["cilj"], band_ag["y_true"], color="black", lw=1.3,
            label="dejansko")
    ax.plot(v["cilj"], v["y_pred"], color="#1f4e79", lw=1, label="AR(1) napoved")
    ax.fill_between(v["cilj"], v["lo"], v["hi"], color="#1f4e79", alpha=0.2,
                    label="empirični interval P10–P90")
    ax.legend()
    ax.set_title("A6: agregat, h = 1 — empirični intervali iz preteklih ostankov")
    fig.tight_layout()
    fig.savefig(VIZ / "a6_intervali_agregat.png", dpi=150)
    plt.close(fig)

# ------------------------------------- 2) kvantilni GB za cakalno dobo (h=1)
panel = iz.nalozi_panel()
MIN_TRAIN = 52


def feats_cd(y: pd.Series) -> pd.DataFrame:
    f = pd.DataFrame(index=y.index)
    for l in (1, 2, 3, 4):
        f[f"lag{l}"] = y.shift(l)
    t = y.index.isocalendar().week.astype(float)
    f["sin_w"] = np.sin(2 * np.pi * t / 52)
    f["cos_w"] = np.cos(2 * np.pi * t / 52)
    return f


primer_ag = None
for s in list(iz.IZBRANE):
    df = iz.redna_tedenska(iz.tedenska_vrsta(panel, s)["cd_redno"])
    y, opaz = df["y"], df["opazovan"]
    F = feats_cd(y)
    preds = []
    for i in range(MIN_TRAIN - 1, len(y) - 1):
        tgt = y.index[i + 1]
        X_tr = F.iloc[:i + 1].dropna()
        y_tr = y.shift(-1).loc[X_tr.index].dropna()
        X_tr = X_tr.loc[y_tr.index]
        x_now = F.loc[[y.index[i]]]
        if x_now.isna().any(axis=None) or len(X_tr) < 30:
            continue
        row = {"cilj": tgt, "y_true": y.loc[tgt], "opazovan": bool(opaz.loc[tgt])}
        for q, nq in ((0.1, "P10"), (0.5, "P50"), (0.9, "P90")):
            gb = GradientBoostingRegressor(loss="quantile", alpha=q,
                                           n_estimators=150, max_depth=2,
                                           learning_rate=0.05, random_state=42)
            gb.fit(X_tr, y_tr)
            row[nq] = float(gb.predict(x_now)[0])
        preds.append(row)
    pr = pd.DataFrame(preds)
    pr = pr[pr.opazovan]
    pokr = ((pr.y_true >= pr.P10) & (pr.y_true <= pr.P90)).mean()
    rows.append({
        "vzs": s, "naziv": imena[s], "spremenljivka": "cd_redno",
        "metoda": "kvantilni GB", "horizont": 1, "n": len(pr),
        "pokritost": pokr, "sirina_povp": (pr.P90 - pr.P10).mean(),
    })
    if s == "1010P":
        primer_ag = pr

pok = pd.DataFrame(rows).round(3)
pok.to_csv(REZ / "a6_pokritost.csv", index=False, encoding="utf-8-sig")
print(pok.to_string(index=False))

if primer_ag is not None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(primer_ag["cilj"], primer_ag["y_true"], color="black", lw=1.3,
            label="dejanska ČD (redno)")
    ax.plot(primer_ag["cilj"], primer_ag["P50"], color="#c00000", lw=1,
            label="kvantilni GB P50")
    ax.fill_between(primer_ag["cilj"], primer_ag["P10"], primer_ag["P90"],
                    color="#c00000", alpha=0.15, label="P10–P90")
    ax.legend()
    ax.set_title("A6: Dermatološki pregled — kvantilna napoved čakalne dobe (h = 1)")
    ax.set_ylabel("ČD na prvi prosti termin (dni)")
    fig.tight_layout()
    fig.savefig(VIZ / "a6_kvantilni_cd.png", dpi=150)
    plt.close(fig)
