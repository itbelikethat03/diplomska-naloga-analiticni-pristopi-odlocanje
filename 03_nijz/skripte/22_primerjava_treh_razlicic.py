# -*- coding: utf-8 -*-
"""
POMOZNA/PRESEZENA skripta — enak izracun (in vec) zdaj proizvaja
20_analiza_5_4.py z uradnim poimenovanjem 'izhodiscna' / 'delno_ocisceno' /
'ocisceno' (glej 5_4_D_metrike.csv, filter horizont == 1). Ta skripta ostane
kot ozek, hitro berljiv izsek samo za h = 1, z istim poimenovanjem in ISTIM
naborom VZS (292, brez izlocitve 2395P/1264 — glej 11_panel_kakovost.py).

Namen primerjave: locevati ucinek (a) izlocitve tedna 11. 6. 2025, ki je bil
znan ze pred diagnostiko A3, od (b) dodatne ugotovitve A3 (drugi prizadeti
teden 20. 8. 2025).

Izhod: rezultati/5_4_D_tri_razlicice_h1.csv
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg

import vrste as vr

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REZ = vr.REZ
MIN_TRAIN = 52
H = 1

panel = vr.nalozi()   # data/panel_kakovost.parquet, ima stolpec 'zanesljiv'


def serija(sifra: str, razlicica: str, stolpec: str = vr.KANON) -> pd.Series:
    if razlicica == "izhodiscna":
        izloci = set()
    elif razlicica == "delno_ocisceno":
        izloci = {pd.Timestamp("2025-06-11")}
    elif razlicica == "ocisceno":
        izloci = {pd.Timestamp("2025-06-11"), pd.Timestamp("2025-08-20")}
    else:
        raise ValueError(razlicica)

    p = panel[~panel["datum"].isin(izloci)]
    if sifra == vr.AGREGAT:
        n = p["datum"].nunique()
        cnt = p.groupby("vzs_sifra")[vr.KANON].count()
        pop = cnt[cnt == n].index
        sub = p[p["vzs_sifra"].isin(pop)].groupby("datum")
        s = (sub[stolpec].sum() if stolpec.startswith("cak")
             else sub[stolpec].median())
    else:
        s = p[p["vzs_sifra"] == sifra].set_index("datum")[stolpec].sort_index()
    return s.dropna()


def napovej(v: np.ndarray, model: str) -> float | None:
    if model == "naivni":
        return float(v[-1])
    if model == "lin":
        t = np.arange(len(v))
        A = np.vstack([np.ones(len(v)), t]).T
        coef, *_ = np.linalg.lstsq(A, v, rcond=None)
        return float(coef[0] + coef[1] * len(v))
    if model == "ar1":
        try:
            return float(AutoReg(v, lags=1, old_names=False).fit().forecast(1)[-1])
        except Exception:
            return None
    raise ValueError(model)


RAZLICICE = ("izhodiscna", "delno_ocisceno", "ocisceno")
rows = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        y = serija(s, razl)
        for i in range(MIN_TRAIN - 1, len(y) - H):
            y_tr = y.iloc[: i + 1].values
            for m in ("naivni", "ar1", "lin"):
                pred = napovej(y_tr, m)
                if pred is None:
                    continue
                rows.append({"razlicica": razl, "vzs": s, "naziv": vr.IMENA[s],
                            "model": m, "cilj": y.index[i + H],
                            "y_true": y.iloc[i + H], "y_pred": pred})

d = pd.DataFrame(rows)
d["ae"] = (d.y_true - d.y_pred).abs()

met = (d.groupby(["razlicica", "vzs", "naziv", "model"])
       .agg(n=("ae", "size"), MAE=("ae", "mean")).reset_index())
naiv = met[met.model == "naivni"].set_index(["razlicica", "vzs"])["MAE"]
met["MAE_vs_naivni_pct"] = met.apply(
    lambda r: 100 * (1 - r.MAE / naiv.loc[(r.razlicica, r.vzs)]), axis=1)

met.round(3).to_csv(REZ / "5_4_D_tri_razlicice_h1.csv", index=False,
                    encoding="utf-8-sig")

print("Stevilo testnih tock (h = 1), tri razlicice:")
print(met[met.model == "naivni"].pivot(index="naziv", columns="razlicica",
                                       values="n").to_string())

print("\nMAE naivnega modela (h = 1):")
print(met[met.model == "naivni"].pivot(index="naziv", columns="razlicica",
                                       values="MAE").round(1)
      .reindex(columns=list(RAZLICICE)).to_string())

for model in ("ar1", "lin"):
    print(f"\n=== {model.upper()} proti naivnemu (%), h = 1, tri razlicice ===")
    piv = (met[met.model == model].pivot(index="naziv", columns="razlicica",
                                         values="MAE_vs_naivni_pct")
           .reindex(columns=list(RAZLICICE)).round(1))
    piv["korak1_izhodiscna_do_delno"] = (
        piv["delno_ocisceno"] - piv["izhodiscna"]).round(1)
    piv["korak2_delno_do_ocisceno"] = (
        piv["ocisceno"] - piv["delno_ocisceno"]).round(1)
    print(piv.to_string())

print(f"\nZapisano: rezultati/5_4_D_tri_razlicice_h1.csv")
