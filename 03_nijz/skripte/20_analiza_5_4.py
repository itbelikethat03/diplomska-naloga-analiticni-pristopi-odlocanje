# -*- coding: utf-8 -*-
"""
Ena skripta, ki generira VSE stevilke poglavja 5.4 (korak G1).

Zajema korake B (opisna analiza), C (detekcija anomalij), D (drsece
preverjanje in napovedni modeli), E (korelacije in AR-X) in F (sezonskost)
iz seznama popravkov. Vsak izracun se izvede v TREH poimenovanih razlicicah,
narascajocih po obsegu popravka (imena so zavezujoca za celotno besedilo
poglavja 5.4, glej dogovor iz kroga popravkov):

    'izhodiscna'      — 112 tednov, brez izlocitev, agregat cez 282 VZS
                        (popolna vrsta cez vseh 112 tednov). Nadomesca
                        prvotno 120-tedensko interpolirano razlicico iz
                        07_a5_napovedi.py, ki je zdaj presezena (A4:
                        brez interpolacije).
    'delno_ocisceno'  — 111 tednov (izlocen le 11. 6. 2025 — prvotno znani
                        prizadeti teden), agregat cez 292 VZS (popolna
                        vrsta cez teh 111 tednov).
    'ocisceno'        — 110 tednov (izlocena oba nezanesljiva tedna, 11. 6.
                        in 20. 8. 2025 — glej A3), agregat cez 292 VZS
                        (popolna vrsta cez 110 zanesljivih tednov; ISTI
                        nabor kot pri delno_ocisceno, ker VZS blok-izpad iz
                        poletja 2024 ni razlog za izlocitev — glej
                        11_panel_kakovost.py).

Primerjava izhodiscna -> delno_ocisceno -> ocisceno omogoca razclenitev
ucinka (a) tedna, ki je bil ze prej znan, od (b) dodatnih ugotovitev A3,
namesto da bi se razlika samo domnevala (korak D4).

Izhodi: rezultati/5_4_*.csv; osrednji je 5_4_povzetek.csv — preglednica
vseh stevilk, ki se pojavijo v besedilu poglavja.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.seasonal import STL

import vrste as vr

warnings.filterwarnings("ignore")
# konzola je cp1250; izpis vsebuje sumnike in matematicne znake
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REZ = vr.REZ
REZ.mkdir(exist_ok=True)

MIN_TRAIN = 52
HORIZONTI = (1, 4)
MODELI = ["naivni", "lin", "ar1"]
MAX_LAG = 8

RAZLICICE = ("izhodiscna", "delno_ocisceno", "ocisceno")

panel = vr.nalozi()
povzetek: list[dict] = []


def zapisi(korak: str, razlicica: str, vrsta_: str, kazalnik: str,
           vrednost, enota: str = "") -> None:
    povzetek.append({"korak": korak, "razlicica": razlicica, "vrsta": vrsta_,
                     "kazalnik": kazalnik,
                     "vrednost": (round(float(vrednost), 4)
                                  if isinstance(vrednost, (int, float, np.floating))
                                  and not isinstance(vrednost, bool)
                                  else vrednost),
                     "enota": enota})


def naslov(s: str) -> None:
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


def serija(sifra: str, razlicica: str, stolpec: str = vr.KANON) -> pd.Series:
    """Vrsta enega kazalnika v izbrani razlicici (indeks = datum objave).

    Nabor VZS za AGREGAT se v vsaki razlicici doloci na novo: VZS mora
    imeti vrednost v VSEH tednih TE razlicice (ne v vseh 112) — to je
    korak A6, uporabljen dosledno za vse tri poimenovane razlicice.
    """
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


# ============================================================================
# B — opisna analiza
# ============================================================================
naslov("B — opisna analiza (rast, trendi, obcutljivost na izlocitev tednov)")

b_rows = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        y = serija(s, razl)
        prva, zadnja = y.iloc[0], y.iloc[-1]
        vrh, dno = y.max(), y.min()
        # linearni trend cez zaporedni indeks opazovanj (glej D2 v vrste.py)
        t = np.arange(len(y))
        X = sm.add_constant(t)
        fit = sm.OLS(y.values, X).fit()
        b_rows.append({
            "razlicica": razl, "vzs": s, "naziv": vr.IMENA[s], "n_tednov": len(y),
            "prva": prva, "zadnja": zadnja, "vrh": vrh, "dno": dno,
            "rast_prva_zadnja_pct": 100 * (zadnja / prva - 1),
            "rast_prva_vrh_pct": 100 * (vrh / prva - 1),
            "naklon_na_teden": fit.params[1], "R2": fit.rsquared,
            "p_naklon": fit.pvalues[1],
            "povprecje": y.mean(), "mediana": y.median(),
            "sd_razlik": y.diff().std(),
        })
b = pd.DataFrame(b_rows)
b.round(4).to_csv(REZ / "5_4_B_opisna.csv", index=False, encoding="utf-8-sig")

pri = b.pivot(index="naziv", columns="razlicica",
              values="rast_prva_zadnja_pct").round(2)
pri["razlika_o_t"] = (pri["ocisceno"] - pri["izhodiscna"]).round(3)
print("\nB1 — rast med prvo in zadnjo objavo (%), obe razlicici:")
print(pri.to_string())

print("\nB1 — rast med prvo objavo in vrhom (%):")
pv = b.pivot(index="naziv", columns="razlicica",
             values="rast_prva_vrh_pct").round(2)
pv["razlika_o_t"] = (pv["ocisceno"] - pv["izhodiscna"]).round(3)
print(pv.to_string())

print("\nB2 — kazalniki, ki uporabljajo povprecje/regresijo cez celo obdobje "
      "(obcutljivi na izlocitev tednov):")
ob = b.pivot(index="naziv", columns="razlicica", values="povprecje").round(1)
ob["razlika_pct"] = (100 * (ob["ocisceno"] / ob["izhodiscna"] - 1)).round(3)
nak = b.pivot(index="naziv", columns="razlicica",
              values="naklon_na_teden").round(1)
nak["razlika_pct"] = (100 * (nak["ocisceno"] / nak["izhodiscna"] - 1)).round(2)
print("\n  povprecje ravni:")
print(ob.to_string())
print("\n  naklon linearnega trenda (na teden):")
print(nak.to_string())
r2 = b.pivot(index="naziv", columns="razlicica", values="R2").round(4)
print("\n  R2 linearnega trenda:")
print(r2.to_string())

for _, r in b.iterrows():
    for k in ("rast_prva_zadnja_pct", "rast_prva_vrh_pct", "naklon_na_teden",
              "R2", "povprecje", "sd_razlik", "n_tednov"):
        zapisi("B", r["razlicica"], r["naziv"], k, r[k])

# ============================================================================
# C — detekcija anomalij
# ============================================================================
naslov("C — detekcija anomalij (konsenz Z-score + Isolation Forest)")


def anomalije(y: pd.Series, contamination: float = 0.05,
              prag_z: float = 2.0) -> pd.DataFrame:
    d = y.diff().dropna()
    z = (d - d.mean()) / d.std()
    feat = pd.DataFrame({
        "razlika": d,
        "drseci_std4": d.rolling(4, min_periods=2).std(),
        "odmik_ma4": y - y.rolling(4, min_periods=2).mean(),
    }).dropna()
    X = StandardScaler().fit_transform(feat)
    iforest = IsolationForest(n_estimators=200, contamination=contamination,
                              random_state=42)
    if_flag = pd.Series(iforest.fit_predict(X) == -1, index=feat.index)
    out = pd.DataFrame({"datum": d.index, "razlika": d.values, "z": z.values,
                        "z_flag": (z.abs() > prag_z).values,
                        "if_flag": if_flag.reindex(d.index,
                                                   fill_value=False).values})
    out["konsenz"] = out["z_flag"] & out["if_flag"]
    return out


c_vse, c_sd = [], []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        y = serija(s, razl)
        a = anomalije(y)
        a.insert(0, "razlicica", razl)
        a.insert(1, "vzs", s)
        a.insert(2, "naziv", vr.IMENA[s])
        c_vse.append(a)
        c_sd.append({"razlicica": razl, "naziv": vr.IMENA[s],
                     "sd_razlik": y.diff().std(),
                     "n_tock": len(a), "z_flag": int(a.z_flag.sum()),
                     "if_flag": int(a.if_flag.sum()),
                     "konsenz": int(a.konsenz.sum())})
c = pd.concat(c_vse, ignore_index=True)
c.round(4).to_csv(REZ / "5_4_C_anomalije_vse.csv", index=False,
                  encoding="utf-8-sig")
csd = pd.DataFrame(c_sd)

print("\nC1 — stevilo zaznav po razlicicah:")
skup = csd.groupby("razlicica")[["n_tock", "z_flag", "if_flag", "konsenz"]].sum()
print(skup.to_string())
for razl in RAZLICICE:
    r = skup.loc[razl]
    for k in ("n_tock", "z_flag", "if_flag", "konsenz"):
        zapisi("C", razl, "vse vrste skupaj", k, r[k])

print("\nC2 — past: st. odklon tedenskih razlik pade, prag z se zaostri")
p_sd = csd.pivot(index="naziv", columns="razlicica", values="sd_razlik").round(1)
p_sd["sprememba_pct"] = (100 * (p_sd["ocisceno"] / p_sd["izhodiscna"] - 1)).round(2)
p_k = csd.pivot(index="naziv", columns="razlicica", values="konsenz")
p_sd["konsenz_izhodiscna"] = p_k["izhodiscna"]
p_sd["konsenz_delno_ocisceno"] = p_k["delno_ocisceno"]
p_sd["konsenz_ocisceno"] = p_k["ocisceno"]
print(p_sd.to_string())

# C3 — obcutljivost na contamination
c3 = []
for cont in (0.02, 0.03, 0.05, 0.08, 0.10):
    for razl in RAZLICICE:
        n_k = n_if = 0
        for s in vr.VSE_VRSTE:
            a = anomalije(serija(s, razl), contamination=cont)
            n_k += int(a.konsenz.sum())
            n_if += int(a.if_flag.sum())
        c3.append({"contamination": cont, "razlicica": razl,
                   "if_zaznav": n_if, "konsenznih": n_k})
c3 = pd.DataFrame(c3)
c3.to_csv(REZ / "5_4_C3_contamination.csv", index=False, encoding="utf-8-sig")
print("\nC3 — obcutljivost na parameter contamination:")
print(c3.pivot(index="contamination", columns="razlicica",
               values=["if_zaznav", "konsenznih"]).to_string())
for _, r in c3.iterrows():
    zapisi("C3", r["razlicica"], f"contamination={r['contamination']}",
           "konsenznih", r["konsenznih"])

# C4 — razvrstitev zaznav: podatkovne proti procesnim
NEZANESLJIVI = set(pd.to_datetime(["2025-06-11", "2025-08-20"]))


def ob_prazniku(dat: pd.Timestamp, dni: int = 10) -> bool:
    return bool(any(abs((dat - p).days) <= dni for p in vr.PRAZNIKI))


def razvrsti(dat: pd.Timestamp, razlika: float, y: pd.Series) -> str:
    """Razvrsti zaznavo v podatkovno ali procesno (korak C4).

    Podatkovna = ima administrativno razlago: oznacen nezanesljiv teden,
    par padec-odboj (vrednost se v naslednjem koraku v veliki meri vrne,
    kar pri zalogi ni mozno kot resnicna dinamika) ali sprememba, izmerjena
    cez vrzel v arhivu. Vse ostalo ostane kandidat za procesno anomalijo.
    """
    if dat in NEZANESLJIVI:
        return "podatkovna: oznacen nezanesljiv teden"
    razmik = y.index.to_series().diff().dt.days.loc[dat]
    if pd.notna(razmik) and razmik > 8:
        return "podatkovna: sprememba izmerjena cez vrzel v arhivu"
    i = list(y.index).index(dat)
    if i + 1 < len(y):
        nasl = y.iloc[i + 1] - y.iloc[i]
        if np.sign(nasl) != np.sign(razlika) and abs(nasl) > 0.6 * abs(razlika):
            return "podatkovna: par padec-odboj"
    if ob_prazniku(dat):
        return "podatkovna: teden ob prazniku"
    return "procesna ali nepojasnjena"


c4 = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        y = serija(s, razl)
        a = anomalije(y)
        for _, r in a[a.konsenz].iterrows():
            c4.append({"razlicica": razl, "vzs": s, "naziv": vr.IMENA[s],
                       "datum": r["datum"], "razlika": r["razlika"],
                       "z": round(r["z"], 2),
                       "razvrstitev": razvrsti(r["datum"], r["razlika"], y)})
c4 = pd.DataFrame(c4)
c4.to_csv(REZ / "5_4_C4_razvrstitev.csv", index=False, encoding="utf-8-sig")
print("\nC4 — razvrstitev konsenznih zaznav:")
print(c4.groupby(["razlicica", "razvrstitev"]).size()
      .unstack(fill_value=0).to_string())
for (razl, kat), n in c4.groupby(["razlicica", "razvrstitev"]).size().items():
    zapisi("C4", razl, kat, "st_zaznav", n)

# ============================================================================
# D — drsece preverjanje in napovedni modeli
# ============================================================================
naslov("D — walk-forward primerjava modelov")


def napovej(v: np.ndarray, h: int, model: str) -> float | None:
    if model == "naivni":
        return float(v[-1])
    if model == "lin":
        t = np.arange(len(v))
        A = np.vstack([np.ones(len(v)), t]).T
        coef, *_ = np.linalg.lstsq(A, v, rcond=None)
        return float(coef[0] + coef[1] * (len(v) - 1 + h))
    if model == "ar1":
        try:
            return float(AutoReg(v, lags=1, old_names=False).fit().forecast(h)[-1])
        except Exception:
            return None
    raise ValueError(model)


d_zapisi = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        y = serija(s, razl)
        idx = y.index
        for h in HORIZONTI:
            for i in range(MIN_TRAIN - 1, len(y) - h):
                y_tr = y.iloc[: i + 1]
                for m in MODELI:
                    pred = napovej(y_tr.values, h, m)
                    if pred is None:
                        continue
                    d_zapisi.append({
                        "razlicica": razl, "vzs": s, "naziv": vr.IMENA[s],
                        "horizont": h, "model": m,
                        "izvor": idx[i], "cilj": idx[i + h],
                        "y_true": y.iloc[i + h], "y_pred": pred,
                        "cez_vrzel": vr.cez_vrzel(idx, i, i + h),
                        "mase_scale": np.abs(np.diff(y_tr.values)).mean(),
                    })
    print(f"  razlicica '{razl}' koncana")

d = pd.DataFrame(d_zapisi)
d["ae"] = (d.y_true - d.y_pred).abs()
d["se"] = (d.y_true - d.y_pred) ** 2
d["ase"] = d["ae"] / d["mase_scale"]
d.round(4).to_csv(REZ / "5_4_D_napovedi_dolge.csv", index=False,
                  encoding="utf-8-sig")


def metrike(df: pd.DataFrame) -> pd.DataFrame:
    m = (df.groupby(["razlicica", "vzs", "naziv", "horizont", "model"])
         .agg(n=("ae", "size"), MAE=("ae", "mean"),
              RMSE=("se", lambda x: np.sqrt(x.mean())), MASE=("ase", "mean"))
         .reset_index())
    naiv = m[m.model == "naivni"].set_index(
        ["razlicica", "vzs", "horizont"])["MAE"]
    m["MAE_vs_naivni_pct"] = m.apply(
        lambda r: 100 * (1 - r.MAE / naiv.loc[(r.razlicica, r.vzs, r.horizont)]),
        axis=1)
    return m


met = metrike(d)
met.round(3).to_csv(REZ / "5_4_D_metrike.csv", index=False, encoding="utf-8-sig")

print("\nD1 — stevilo testnih tock:")
tt = (met[met.model == "naivni"].pivot_table(index="horizont",
                                             columns="razlicica", values="n",
                                             aggfunc="max"))
print(tt.to_string())
for razl in RAZLICICE:
    for h in HORIZONTI:
        zapisi("D1", razl, f"h={h}", "testnih_tock", tt.loc[h, razl])

print("\nD2 — izpostavljenost predpostavki enakomernega koraka:")
for razl in RAZLICICE:
    y = serija(vr.AGREGAT, razl)
    info = vr.delez_vrzeli(y.index)
    print(f"  {razl}: {info}")
    for k, v in info.items():
        zapisi("D2", razl, "Agregat", k, v)
dg = (d[d.model == "naivni"].groupby(["razlicica", "horizont"])["cez_vrzel"]
      .mean().round(4))
print("\n  delez testnih tock, katerih okno precka vrzel > 8 dni:")
print(dg.to_string())

print("\nD3/D4 — izboljsava MAE proti naivnemu (%), po razlicicah:")
for h in HORIZONTI:
    print(f"\n--- horizont h = {h} ---")
    piv = (met[(met.horizont == h) & (met.model != "naivni")]
           .pivot_table(index="naziv", columns=["model", "razlicica"],
                        values="MAE_vs_naivni_pct").round(1))
    print(piv.to_string())

print("\nD4 — MAE naivnega modela in njegov delez v ravni vrste:")
nv = met[met.model == "naivni"].copy()
ravni = {(razl, s): serija(s, razl).mean()
         for razl in RAZLICICE for s in vr.VSE_VRSTE}
nv["raven"] = nv.apply(lambda r: ravni[(r.razlicica, r.vzs)], axis=1)
nv["MAE_pct_ravni"] = 100 * nv["MAE"] / nv["raven"]
print(nv.pivot_table(index="naziv", columns=["horizont", "razlicica"],
                     values="MAE_pct_ravni").round(2).to_string())

for _, r in met.iterrows():
    zapisi("D", r["razlicica"], f"{r['naziv']} h={r['horizont']} {r['model']}",
           "MAE_vs_naivni_pct", r["MAE_vs_naivni_pct"])
    zapisi("D", r["razlicica"], f"{r['naziv']} h={r['horizont']} {r['model']}",
           "MAE", r["MAE"])
    zapisi("D", r["razlicica"], f"{r['naziv']} h={r['horizont']} {r['model']}",
           "MASE", r["MASE"])

# D4 — je razlika do naivnega sploh statisticno razlocljiva?
# Razlika v MAE sama po sebi ne pove, ali je model boljsi; na 55–60 tockah
# je treba primerjati PARNE absolutne napake na istih ciljnih tednih
# (Wilcoxonov test predznacenih rangov, ker porazdelitev razlik ni normalna).
w_rows = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        for h in HORIZONTI:
            sub = d[(d.vzs == s) & (d.horizont == h) & (d.razlicica == razl)]
            naiv = sub[sub.model == "naivni"].set_index("cilj")["ae"]
            for m in ("ar1", "lin"):
                alt = sub[sub.model == m].set_index("cilj")["ae"]
                idx = naiv.index.intersection(alt.index)
                razlika = naiv.loc[idx] - alt.loc[idx]   # > 0 = model boljsi
                try:
                    _, p = stats.wilcoxon(razlika)
                except ValueError:
                    p = np.nan
                w_rows.append({
                    "razlicica": razl, "vzs": s, "naziv": vr.IMENA[s],
                    "horizont": h, "model": m, "n": len(idx),
                    "model_boljsi_na_n": int((razlika > 0).sum()),
                    "mediana_razlike": razlika.median(),
                    "wilcoxon_p": p,
                    "razlocljivo_p05": bool(p < 0.05) if pd.notna(p) else None})
w = pd.DataFrame(w_rows)
w.round(4).to_csv(REZ / "5_4_D4_parni_testi.csv", index=False,
                  encoding="utf-8-sig")
print("\nD4 — parna primerjava z naivnim (Wilcoxon na absolutnih napakah):")
print(w[w.model == "ar1"].pivot_table(index="naziv",
                                      columns=["horizont", "razlicica"],
                                      values="wilcoxon_p").round(3).to_string())
print("\n  st. vrst, kjer je AR(1) od naivnega RAZLOCLJIVO drugacen (p < 0,05):")
print(w[w.model == "ar1"].groupby(["razlicica", "horizont"])["razlocljivo_p05"]
      .sum().to_string())
for _, r in w.iterrows():
    zapisi("D4", r["razlicica"],
           f"{r['naziv']} h={r['horizont']} {r['model']}", "wilcoxon_p",
           r["wilcoxon_p"])

# obcutljivost na obravnavo vrzeli (D2, alternativa b)
met_bv = metrike(d[~d["cez_vrzel"]])
prim = (met.merge(met_bv, on=["razlicica", "vzs", "naziv", "horizont", "model"],
                  suffixes=("_vse", "_brez_vrzeli")))
prim["razlika_o_t"] = (prim["MAE_vs_naivni_pct_brez_vrzeli"]
                       - prim["MAE_vs_naivni_pct_vse"])
prim.round(3).to_csv(REZ / "5_4_D2_vrzeli_obcutljivost.csv", index=False,
                     encoding="utf-8-sig")
print("\nD2 — obcutljivost: ista metrika brez oken cez vrzel "
      "(razlika v odstotnih tockah, razlicica 'ocisceno', h = 1):")
print(prim[(prim.razlicica == "ocisceno") & (prim.horizont == 1)
           & (prim.model != "naivni")]
      [["naziv", "model", "MAE_vs_naivni_pct_vse",
        "MAE_vs_naivni_pct_brez_vrzeli", "razlika_o_t"]].round(1)
      .to_string(index=False))

# ============================================================================
# E — korelacije in AR-X
# ============================================================================
naslov("E — krizne korelacije Δcakajoci ↔ ΔČD in AR-X")

e_rows = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        cak = serija(s, razl, "cak_skupaj")
        cd = serija(s, razl, "cd_redno")
        idx = cak.index.intersection(cd.index)
        d_cak, d_cd = cak.loc[idx].diff(), cd.loc[idx].diff()
        for lag in range(0, MAX_LAG + 1):
            par = pd.concat([d_cak.shift(lag), d_cd], axis=1).dropna()
            if len(par) < 10:
                continue
            r, p = stats.pearsonr(par.iloc[:, 0], par.iloc[:, 1])
            e_rows.append({"razlicica": razl, "vzs": s, "naziv": vr.IMENA[s],
                           "zamik_tednov": lag, "r": r, "p": p, "n": len(par),
                           "meja_2sqrt_n": 2 / np.sqrt(len(par)),
                           "znacilna_p05": p < 0.05})
e = pd.DataFrame(e_rows)
e.round(4).to_csv(REZ / "5_4_E_ccf.csv", index=False, encoding="utf-8-sig")

print("\nE1 — najnizja p-vrednost po vrstah in razlicicah:")
najm = (e.loc[e.groupby(["razlicica", "naziv"])["p"].idxmin()]
        [["razlicica", "naziv", "zamik_tednov", "r", "p", "n"]])
print(najm.round(4).to_string(index=False))
# Korekcija za mnogotere teste: 7 vrst x 9 zamikov = 63 testov na razlicico,
# zato je nekaj nominalno znacilnih korelacij pricakovanih ze po nakljucju
# (63 x 0,05 = 3,2). Poroca se Bonferronijev prag in Benjamini-Hochberg (FDR).
for razl in RAZLICICE:
    m = e["razlicica"] == razl
    k = int(m.sum())
    e.loc[m, "p_bonferroni"] = (e.loc[m, "p"] * k).clip(upper=1.0)
    rang = e.loc[m, "p"].rank(method="first")
    e.loc[m, "p_bh"] = (e.loc[m, "p"] * k / rang).clip(upper=1.0)
    e.loc[m, "n_testov"] = k

print(f"\n  nominalno znacilnih pri p < 0,05: "
      f"{e.groupby('razlicica')['znacilna_p05'].sum().to_dict()}")
print("  pricakovano po nakljucju pri 63 testih: 3,2")
print(f"  preziveli Bonferronijev prag: "
      f"{e[e.p_bonferroni < 0.05].groupby('razlicica').size().to_dict()}")
print(f"  preziveli BH (FDR 5 %):       "
      f"{e[e.p_bh < 0.05].groupby('razlicica').size().to_dict()}")
e.round(4).to_csv(REZ / "5_4_E_ccf.csv", index=False, encoding="utf-8-sig")
for razl in RAZLICICE:
    m = e["razlicica"] == razl
    zapisi("E1", razl, "vse vrste", "nominalno_znacilnih_p05",
           int(e.loc[m, "znacilna_p05"].sum()))
    zapisi("E1", razl, "vse vrste", "znacilnih_po_bonferroni",
           int((e.loc[m, "p_bonferroni"] < 0.05).sum()))
    zapisi("E1", razl, "vse vrste", "znacilnih_po_BH",
           int((e.loc[m, "p_bh"] < 0.05).sum()))
for _, r in najm.iterrows():
    zapisi("E1", r["razlicica"], r["naziv"], "najnizja_p", r["p"])
    zapisi("E1", r["razlicica"], r["naziv"], "r_pri_najnizji_p", r["r"])
    zapisi("E1", r["razlicica"], r["naziv"], "zamik_pri_najnizji_p",
           r["zamik_tednov"])

print("\n  vse kombinacije z p < 0,10:")
print(e[e.p < 0.10][["razlicica", "naziv", "zamik_tednov", "r", "p", "n"]]
      .round(4).to_string(index=False))


def wf_ar(cd: pd.Series, cak: pd.Series | None) -> tuple[float, int]:
    df = pd.DataFrame({"y": cd})
    df["lag1"] = df["y"].shift(1)
    if cak is not None:
        df["x1"] = cak.reindex(cd.index).diff().shift(1)
        df["x2"] = cak.reindex(cd.index).diff().shift(2)
    df = df.dropna()
    errs = []
    for i in range(MIN_TRAIN, len(df)):
        tr = df.iloc[:i]
        cilj = df.index[i]
        X = sm.add_constant(tr.drop(columns="y"))
        fit = sm.OLS(tr["y"], X).fit()
        x_now = sm.add_constant(df.drop(columns="y"),
                                has_constant="add").loc[[cilj]]
        errs.append(abs(df.loc[cilj, "y"] - fit.predict(x_now).iloc[0]))
    return (float(np.mean(errs)) if errs else np.nan), len(errs)


arx_rows = []
for razl in RAZLICICE:
    for s in vr.VSE_VRSTE:
        cak = serija(s, razl, "cak_skupaj")
        cd = serija(s, razl, "cd_redno")
        mae_ar, n1 = wf_ar(cd, None)
        mae_arx, n2 = wf_ar(cd, cak)
        arx_rows.append({"razlicica": razl, "vzs": s, "naziv": vr.IMENA[s],
                         "n": n1, "MAE_AR": mae_ar, "MAE_ARX": mae_arx,
                         "izboljsava_pct": 100 * (1 - mae_arx / mae_ar)})
arx = pd.DataFrame(arx_rows)
arx.round(4).to_csv(REZ / "5_4_E2_arx.csv", index=False, encoding="utf-8-sig")
print("\nE2 — AR proti AR-X pri napovedi cakalne dobe (h = 1):")
print(arx.pivot(index="naziv", columns="razlicica",
                values="izboljsava_pct").round(2).to_string())
for _, r in arx.iterrows():
    zapisi("E2", r["razlicica"], r["naziv"], "ARX_izboljsava_pct",
           r["izboljsava_pct"])

# ============================================================================
# F — sezonskost
# ============================================================================
naslov("F — sezonskost")

f_rows = []
for razl in RAZLICICE:
    y = serija(vr.AGREGAT, razl)
    # STL zahteva enakomerno mrezo: uporabi zaporedni indeks (glej D2)
    ys = pd.Series(y.values, index=pd.RangeIndex(len(y)))
    res = STL(pd.Series(y.values,
                        index=pd.date_range("2024-01-03", periods=len(y),
                                            freq="7D")),
              period=52, robust=True).fit()
    delez = res.seasonal.std() / y.std()
    # medletna primerjava istoleznih ISO tednov
    iso = y.index.isocalendar()
    tab = pd.DataFrame({"y": y.values, "leto": iso["year"].values,
                        "teden": iso["week"].values})
    med_letom = tab.groupby("leto")["y"].mean()
    znotraj = tab.groupby("teden")["y"].mean()
    f_rows.append({"razlicica": razl, "n": len(y),
                   "STL_sezonska_delez_sd": delez,
                   "sd_med_leti": med_letom.std(),
                   "sd_znotraj_leta": znotraj.std(),
                   "razmerje_med_znotraj": med_letom.std() / znotraj.std()})
f = pd.DataFrame(f_rows)
f.round(4).to_csv(REZ / "5_4_F_sezonskost.csv", index=False,
                  encoding="utf-8-sig")
print(f.round(4).to_string(index=False))
print("\nF1 — utemeljitev izkljucitve sezonskosti sloni na razmerju "
      "med medletno in znotrajletno razprsenostjo; obe razlicici dasta "
      "isti sklep, ce je razmerje > 1 v obeh vrsticah.")
for _, r in f.iterrows():
    for k in ("STL_sezonska_delez_sd", "sd_med_leti", "sd_znotraj_leta",
              "razmerje_med_znotraj"):
        zapisi("F", r["razlicica"], "Agregat", k, r[k])

# ============================================================================
# G1 — povzetek
# ============================================================================
naslov("G1 — povzetek vseh stevilk poglavja 5.4")

pov = pd.DataFrame(povzetek)
pov.to_csv(REZ / "5_4_povzetek.csv", index=False, encoding="utf-8-sig")
print(f"Zapisanih {len(pov)} stevilk v rezultati/5_4_povzetek.csv")
print("\nDatoteke:")
for p in sorted(REZ.glob("5_4_*.csv")):
    print(f"  {p.name}")
