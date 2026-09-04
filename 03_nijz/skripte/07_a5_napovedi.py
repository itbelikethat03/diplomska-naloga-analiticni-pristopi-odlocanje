# -*- coding: utf-8 -*-
"""
A5: walk-forward primerjava napovednih modelov (N-RV3).

Ciljna spremenljivka: stevilo cakajocih (cak_skupaj) na redni tedenski mrezi.
Za konsistentnost s Fotono (poglavje 5.3) se primerjajo trije modeli:
naivni (t-1) kot obvezno izhodisce, linearna regresija (linearni trend cez
tedenski indeks) in AR(1) (napoved iz pretekle vrednosti same vrste).

Validacija: walk-forward z rastocim oknom, min. 52 tednov treninga,
horizonta h = 1 in h = 4 tedne. Metrike (MAE, RMSE, MASE) se racunajo
samo na dejansko opazovanih tednih (interpolirani tedni so izloceni iz
ocenjevanja); MASE je skaliran z in-sample MAE naivne napovedi na treningu.

Izhodi: rezultati/a5_napovedi_dolge.csv, a5_metrike.csv,
        visualizations/a5_mae_primerjava.png, a5_agregat_h1.png
"""

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg

import izbor_storitev as iz

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parents[1]
REZ, VIZ = BASE / "rezultati", BASE / "visualizations"

MIN_TRAIN = 52
HORIZONTI = (1, 4)


def napovej(y_tr: pd.Series, h: int, model: str) -> float | None:
    """Napoved y na h korakov naprej od konca y_tr."""
    v = y_tr.values
    if model == "naivni":
        return v[-1]
    if model == "lin":
        # linearni trend cez celoten (rastoci) trening: OLS y ~ const + t
        t = np.arange(len(v))
        A = np.vstack([np.ones(len(v)), t]).T
        coef, *_ = np.linalg.lstsq(A, v, rcond=None)
        return float(coef[0] + coef[1] * (len(v) - 1 + h))
    if model == "ar1":
        try:
            fit = AutoReg(v, lags=1, old_names=False).fit()
            return float(fit.forecast(h)[-1])
        except Exception:
            return None
    raise ValueError(model)


MODELI = ["naivni", "lin", "ar1"]

panel = iz.nalozi_panel()
imena = dict(iz.IZBRANE, **{iz.AGREGAT: "Agregat"})

zapisi = []
for s in list(iz.IZBRANE) + [iz.AGREGAT]:
    df = iz.redna_tedenska(iz.tedenska_vrsta(panel, s)["cak_skupaj"])
    y, opaz = df["y"], df["opazovan"]
    for h in HORIZONTI:
        for i in range(MIN_TRAIN - 1, len(y) - h):
            tgt = y.index[i + h]
            y_tr = y.iloc[: i + 1]
            for m in MODELI:
                pred = napovej(y_tr, h, m)
                if pred is None:
                    continue
                zapisi.append({
                    "vzs": s, "naziv": imena[s], "horizont": h, "model": m,
                    "izvor": y.index[i], "cilj": tgt,
                    "y_true": y.loc[tgt], "y_pred": pred,
                    "opazovan": bool(opaz.loc[tgt]),
                    # in-sample naivni MAE za MASE (samo trening!)
                    "mase_scale": np.abs(np.diff(y_tr.values)).mean(),
                })
    print(f"  {s} koncano")

dolge = pd.DataFrame(zapisi)
dolge.to_csv(REZ / "a5_napovedi_dolge.csv", index=False, encoding="utf-8-sig")

# ------------------------------------------------------------------ metrike
ocena = dolge[dolge["opazovan"]].copy()
ocena["ae"] = (ocena.y_true - ocena.y_pred).abs()
ocena["se"] = (ocena.y_true - ocena.y_pred) ** 2
ocena["ase"] = ocena["ae"] / ocena["mase_scale"]

met = (ocena.groupby(["vzs", "naziv", "horizont", "model"])
       .agg(n=("ae", "size"), MAE=("ae", "mean"),
            RMSE=("se", lambda x: np.sqrt(x.mean())), MASE=("ase", "mean"))
       .reset_index())
naiv = met[met.model == "naivni"].set_index(["vzs", "horizont"])["MAE"]
met["MAE_vs_naivni_pct"] = met.apply(
    lambda r: 100 * (1 - r.MAE / naiv.loc[(r.vzs, r.horizont)]), axis=1)
met = met.sort_values(["vzs", "horizont", "MAE"])
met.round(3).to_csv(REZ / "a5_metrike.csv", index=False, encoding="utf-8-sig")

for h in HORIZONTI:
    print(f"\n=== Horizont {h} teden(a) — MAE in izboljsava proti naivnemu ===")
    piv = met[met.horizont == h].pivot(index="naziv", columns="model",
                                       values="MAE_vs_naivni_pct").round(1)
    print(piv.to_string())

# ------------------------------------------------------------------- grafa
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})
fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
for ax, h in zip(axes, HORIZONTI):
    piv = (met[(met.horizont == h) & (met.model != "naivni")]
           .pivot(index="naziv", columns="model", values="MAE_vs_naivni_pct"))
    piv.plot.barh(ax=ax, width=0.8)
    ax.axvline(0, color="black", lw=1)
    ax.set_title(f"Horizont {h} t.")
    ax.set_xlabel("Izboljšava MAE proti naivnemu (%)")
fig.suptitle("A5: relativna izboljšava proti naivni napovedi (pozitivno = boljše)")
fig.tight_layout()
fig.savefig(VIZ / "a5_mae_primerjava.png", dpi=150)
plt.close(fig)

ag = ocena[(ocena.vzs == iz.AGREGAT) & (ocena.horizont == 1)
           & (ocena.model.isin(["naivni", "lin", "ar1"]))]
fig, ax = plt.subplots(figsize=(10, 4.5))
res = ag[ag.model == "naivni"]
ax.plot(res["cilj"], res["y_true"], color="black", lw=1.4, label="dejansko")
for m, c in (("naivni", "#999999"), ("lin", "#c00000"), ("ar1", "#1f4e79")):
    r = ag[ag.model == m]
    ax.plot(r["cilj"], r["y_pred"], lw=1, alpha=0.9, label=m)
ax.legend()
ax.set_title("Agregat, h = 1: dejanske vrednosti in napovedi (testno obdobje)")
fig.tight_layout()
fig.savefig(VIZ / "a5_agregat_h1.png", dpi=150)
plt.close(fig)
