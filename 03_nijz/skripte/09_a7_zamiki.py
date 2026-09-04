# -*- coding: utf-8 -*-
"""
A7: korelacijska analiza in analiza casovnih zamikov (N-RV2/N-RV3).

Hipoteza: rast stevila cakajocih danes -> daljsa cakalna doba cez k tednov
(analogno hipotezi posegi -> reklamacije pri Fotoni). Krizne korelacije se
racunajo na tedenskih RAZLIKAH (na nivojih skupni trend ustvarja navidezne
korelacije). Ce signal obstaja, se preveri, ali zakasnitvena znacilka
stevila cakajocih izboljsa napoved cakalne dobe nad cisti AR model
(walk-forward, h = 1, samo opazovani tedni).

Izhodi: rezultati/a7_ccf.csv, a7_arx_primerjava.csv,
        visualizations/a7_ccf.png
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

import izbor_storitev as iz

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parents[1]
REZ, VIZ = BASE / "rezultati", BASE / "visualizations"

panel = iz.nalozi_panel()
imena = dict(iz.IZBRANE, **{iz.AGREGAT: "Agregat"})
MAX_LAG = 8
MIN_TRAIN = 52

ccf_rows = []
serije = {}
for s in list(iz.IZBRANE) + [iz.AGREGAT]:
    v = iz.tedenska_vrsta(panel, s)
    cak = iz.redna_tedenska(v["cak_skupaj"])["y"]
    cd = iz.redna_tedenska(v["cd_redno"])["y"]
    idx = cak.index.intersection(cd.index)
    d_cak, d_cd = cak.loc[idx].diff().dropna(), cd.loc[idx].diff().dropna()
    idx2 = d_cak.index.intersection(d_cd.index)
    d_cak, d_cd = d_cak.loc[idx2], d_cd.loc[idx2]
    serije[s] = (cak, cd)
    n = len(idx2)
    meja = 2 / np.sqrt(n)
    for lag in range(0, MAX_LAG + 1):
        # korelacija med d_cak(t-lag) in d_cd(t)
        r = d_cd.corr(d_cak.shift(lag))
        ccf_rows.append({"vzs": s, "naziv": imena[s], "zamik_tednov": lag,
                         "r": r, "znacilna": abs(r) > meja, "n": n,
                         "meja_znacilnosti": meja})

ccf = pd.DataFrame(ccf_rows).round(4)
ccf.to_csv(REZ / "a7_ccf.csv", index=False, encoding="utf-8-sig")
print("Znacilne korelacije (|r| > 2/sqrt(n)):")
print(ccf[ccf.znacilna].to_string(index=False))

print("\nPearsonova korelacija na razlikah (scipy.stats.pearsonr), po VZS:")
for s in list(iz.IZBRANE) + [iz.AGREGAT]:
    cakajoci, cd_s = serije[s]
    print(f"\n{imena[s]} ({s}):")
    d_cak = cakajoci.diff()
    d_cd = cd_s.diff()
    for k in range(9):
        par = pd.concat([d_cak.shift(k), d_cd], axis=1).dropna()
        r, p = stats.pearsonr(par.iloc[:, 0], par.iloc[:, 1])
        print(f"  zamik {k}: r = {r:.3f}, p = {p:.3f}, n = {len(par)}")

# graf CCF
fig, axes = plt.subplots(2, 4, figsize=(13, 6), sharey=True)
for ax, s in zip(axes.ravel(), list(iz.IZBRANE) + [iz.AGREGAT]):
    g = ccf[ccf.vzs == s]
    ax.bar(g["zamik_tednov"], g["r"], color="#1f4e79")
    m = g["meja_znacilnosti"].iloc[0]
    ax.axhline(m, color="#c00000", ls="--", lw=0.8)
    ax.axhline(-m, color="#c00000", ls="--", lw=0.8)
    ax.set_title(imena[s], fontsize=8)
    ax.set_xlabel("zamik (tedni)")
axes.ravel()[-1].axis("off") if len(iz.IZBRANE) + 1 < 8 else None
fig.suptitle("A7: križna korelacija Δčakajoči(t−k) ↔ ΔČD(t); "
             "rdeča črta = meja značilnosti")
fig.tight_layout()
fig.savefig(VIZ / "a7_ccf.png", dpi=150)
plt.close(fig)

# ---------------------- AR proti AR-X (zakasnjeni cakajoci) za cd_redno, h=1
def wf_ar(cd: pd.Series, cak: pd.Series | None, opaz: pd.Series) -> float:
    """Walk-forward MAE; ce je cak podan, AR-X z Δcak(t-1) in Δcak(t-2)."""
    df = pd.DataFrame({"y": cd})
    df["lag1"] = df["y"].shift(1)
    if cak is not None:
        df["x1"] = cak.diff().shift(1)
        df["x2"] = cak.diff().shift(2)
    df = df.dropna()
    errs = []
    for i in range(MIN_TRAIN, len(df) - 1):
        tr = df.iloc[:i]
        cilj = df.index[i]
        if not opaz.reindex([cilj], fill_value=False).iloc[0]:
            continue
        X = sm.add_constant(tr.drop(columns="y"))
        fit = sm.OLS(tr["y"], X).fit()
        x_now = sm.add_constant(df.drop(columns="y"), has_constant="add").loc[[cilj]]
        errs.append(abs(df.loc[cilj, "y"] - fit.predict(x_now).iloc[0]))
    return float(np.mean(errs)) if errs else np.nan


arx_rows = []
for s in list(iz.IZBRANE) + [iz.AGREGAT]:
    cak, cd = serije[s]
    opaz = iz.redna_tedenska(iz.tedenska_vrsta(panel, s)["cd_redno"])["opazovan"]
    mae_ar = wf_ar(cd, None, opaz)
    mae_arx = wf_ar(cd, cak, opaz)
    arx_rows.append({"vzs": s, "naziv": imena[s], "MAE_AR": mae_ar,
                     "MAE_ARX": mae_arx,
                     "izboljsava_pct": 100 * (1 - mae_arx / mae_ar)})
arx = pd.DataFrame(arx_rows).round(3)
arx.to_csv(REZ / "a7_arx_primerjava.csv", index=False, encoding="utf-8-sig")
print("\nAR proti AR-X (cakalna doba, h = 1):")
print(arx.to_string(index=False))
