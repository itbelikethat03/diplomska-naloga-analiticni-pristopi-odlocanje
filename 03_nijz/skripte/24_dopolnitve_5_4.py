# -*- coding: utf-8 -*-
"""
Dopolnitve za besedilo poglavij 5.4.1 in 5.4.2: manjkajoce stevilke in
potrditve vrednosti, podedovanih iz starejsih razlicic cevovoda.

Vsi izracuni na OCISCENI razlicici (110 zanesljivih tednov, nabor 292 VZS
s popolnimi vrstami), razen kjer je izrecno navedeno drugace.

Razdelki:
  A  detekcija anomalij: razvrstitev 26 konsenznih zaznav, obcutljivost na
     contamination, zaznave na vrzelih, ki jih je ustvarila nasa izlocitev
  B  natancne Wilcoxonove p-vrednosti (4 decimalke) in Bonferronijev prag
  C  primerjava treh razlicic z NESPREMENJENIM naborom VZS
  D  potrditve podedovanih stevilk
  E  opisna analiza: katere storitve so v razponu rasti slikovne diagnostike
  F  razponi iz poskusa o interpolaciji, loceno po horizontih

Skripta ne spreminja obstojecih skript ali rezultatov.
Izhod: rezultati/5_4_dopolnitve.csv (+ podrobnejsi 5_4_dopolnitve_*.csv)
Zagon: py -3.11 24_dopolnitve_5_4.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.ar_model import AutoReg

import vrste as vr

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REZ = vr.REZ
MIN_TRAIN = 52
HORIZONTI = (1, 4)
MODELI = ["naivni", "ar1", "lin"]
NEZANESLJIVI = [pd.Timestamp("2025-06-11"), pd.Timestamp("2025-08-20")]
BONF_14 = 0.05 / 14

panel = vr.nalozi()
izpis: list[dict] = []


def zapisi(razdelek, postavka, vrednost, opomba=""):
    izpis.append({"razdelek": razdelek, "postavka": postavka,
                  "vrednost": vrednost, "opomba": opomba})


def naslov(s):
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


# --------------------------------------------------------------- nabori
pz = panel[~panel["datum"].isin(NEZANESLJIVI)]
_c110 = pz.groupby("vzs_sifra")[vr.KANON].count()
SET292 = sorted(_c110[_c110 == pz["datum"].nunique()].index)
_c112 = panel.groupby("vzs_sifra")[vr.KANON].count()
SET282 = sorted(_c112[_c112 == panel["datum"].nunique()].index)


def serija(sifra, izloci_tedne, nabor, stolpec=vr.KANON):
    p = panel[~panel["datum"].isin(izloci_tedne)]
    if sifra == vr.AGREGAT:
        s = p[p["vzs_sifra"].isin(nabor)].groupby("datum")[stolpec].sum()
    else:
        s = p[p["vzs_sifra"] == sifra].set_index("datum")[stolpec]
    return s.sort_index().dropna()


def ocisceno(sifra, stolpec=vr.KANON):
    return serija(sifra, NEZANESLJIVI, SET292, stolpec)


# ============================================================ A. ANOMALIJE
naslov("A. DETEKCIJA ANOMALIJ (nabor 292, ocisceno)")


def anomalije(y, contamination=0.05, prag_z=2.0):
    d = y.diff().dropna()
    z = (d - d.mean()) / d.std()
    feat = pd.DataFrame({
        "razlika": d,
        "drseci_std4": d.rolling(4, min_periods=2).std(),
        "odmik_ma4": y - y.rolling(4, min_periods=2).mean(),
    }).dropna()
    X = StandardScaler().fit_transform(feat)
    ifo = IsolationForest(n_estimators=200, contamination=contamination,
                          random_state=42)
    iff = pd.Series(ifo.fit_predict(X) == -1, index=feat.index)
    out = pd.DataFrame({"datum": d.index, "razlika": d.values, "z": z.values,
                        "z_flag": (z.abs() > prag_z).values,
                        "if_flag": iff.reindex(d.index, fill_value=False).values})
    out["konsenz"] = out["z_flag"] & out["if_flag"]
    return out


def ob_prazniku(dat, dni=10):
    return bool(any(abs((dat - p).days) <= dni for p in vr.PRAZNIKI))


# vrzeli, ki jih je ustvarila NASA izlocitev (prvi teden po izlocenem tednu)
VRZEL_NASA = set()
_vsi = sorted(panel["datum"].unique())
for dd in NEZANESLJIVI:
    i = _vsi.index(dd)
    if i + 1 < len(_vsi):
        VRZEL_NASA.add(pd.Timestamp(_vsi[i + 1]))


def razvrsti(dat, razlika, y):
    razmik = y.index.to_series().diff().dt.days.loc[dat]
    if pd.notna(razmik) and razmik > 8:
        return "podatkovna: prvi teden po vrzeli"
    i = list(y.index).index(dat)
    if i + 1 < len(y):
        nasl = y.iloc[i + 1] - y.iloc[i]
        if np.sign(nasl) != np.sign(razlika) and abs(nasl) > 0.6 * abs(razlika):
            return "podatkovna: par padec-odboj"
    if ob_prazniku(dat):
        return "podatkovna: teden ob prazniku"
    return "procesna ali nepojasnjena"


# ---- A1
a1 = []
for s in vr.VSE_VRSTE:
    y = ocisceno(s)
    a = anomalije(y)
    for _, r in a[a["konsenz"]].iterrows():
        d0 = r["datum"]
        razmik = y.index.to_series().diff().dt.days.loc[d0]
        a1.append({
            "vrsta": vr.IMENA[s], "vzs": s, "datum": d0.date(),
            "razlika": round(r["razlika"], 1), "abs_z": round(abs(r["z"]), 2),
            "razmik_dni": int(razmik) if pd.notna(razmik) else None,
            "skupina": razvrsti(d0, r["razlika"], y),
            "vrzel_zaradi_nase_izlocitve": d0 in VRZEL_NASA,
        })
A1 = pd.DataFrame(a1).sort_values(["skupina", "datum", "vrsta"])
A1.to_csv(REZ / "5_4_dopolnitve_A1_zaznave.csv", index=False,
          encoding="utf-8-sig")

print(f"Konsenznih zaznav skupaj: {len(A1)}\n")
for sk, g in A1.groupby("skupina"):
    print(f"--- {sk}  (n = {len(g)}) ---")
    print(g[["vrsta", "datum", "razlika", "abs_z", "razmik_dni"]]
          .to_string(index=False))
    print()
    zapisi("A1", f"st. zaznav: {sk}", len(g))

proc = A1[A1["skupina"] == "procesna ali nepojasnjena"]
print(f"Razpon |Z| v skupini procesnih/nepojasnjenih: "
      f"{proc['abs_z'].min():.2f} do {proc['abs_z'].max():.2f}  (n = {len(proc)})")
zapisi("A1", "procesne: min |Z|", round(float(proc["abs_z"].min()), 2))
zapisi("A1", "procesne: max |Z|", round(float(proc["abs_z"].max()), 2))
zapisi("A1", "konsenznih skupaj", len(A1))

# ---- A2
print("\n--- A2: obcutljivost na contamination (nabor 292) ---")
a2 = []
for cont in (0.02, 0.05, 0.10):
    nz = nif = nk = 0
    for s in vr.VSE_VRSTE:
        a = anomalije(ocisceno(s), contamination=cont)
        nz += int(a["z_flag"].sum())
        nif += int(a["if_flag"].sum())
        nk += int(a["konsenz"].sum())
    a2.append({"contamination": cont, "z_oznacb": nz, "if_oznacb": nif,
               "konsenznih": nk})
    zapisi("A2", f"konsenznih pri contamination={cont}", nk)
    zapisi("A2", f"IF-oznacb pri contamination={cont}", nif)
A2 = pd.DataFrame(a2)
print(A2.to_string(index=False))
print("\nOpomba: stevilo Z-oznacb je od parametra contamination NEODVISNO\n"
      "(Z-prag je |z| > 2), zato je v vseh vrsticah enako.")

# ---- A3
print("\n--- A3: zaznave na vrzelih, ki jih je ustvarila nasa izlocitev ---")
print(f"Prizadeta tedna (prvi teden po izlocenem): "
      f"{sorted(str(d.date()) for d in VRZEL_NASA)}")
nase = A1[A1["vrzel_zaradi_nase_izlocitve"]]
if len(nase) == 0:
    print("  Nobena od zaznav ne lezi na teh dveh tednih.")
else:
    print(f"  DA — {len(nase)} zaznav(a). To je treba v besedilu razkriti:")
    print(nase[["vrsta", "datum", "razlika", "abs_z", "razmik_dni", "skupina"]]
          .to_string(index=False))
zapisi("A3", "zaznav na vrzeli zaradi nase izlocitve", len(nase))


# ====================================================== B. p-VREDNOSTI
naslov("B. NATANCNE WILCOXONOVE p-VREDNOSTI")


def napovej(v, h, model):
    if model == "naivni":
        return float(v[-1])
    if model == "lin":
        t = np.arange(len(v))
        X = np.vstack([np.ones(len(v)), t]).T
        coef, *_ = np.linalg.lstsq(X, v, rcond=None)
        return float(coef[0] + coef[1] * (len(v) - 1 + h))
    if model == "ar1":
        try:
            return float(AutoReg(v, lags=1, old_names=False).fit().forecast(h)[-1])
        except Exception:
            return None


def wf(y, h, model):
    rows = []
    for i in range(MIN_TRAIN - 1, len(y) - h):
        p_ = napovej(y.iloc[: i + 1].values, h, model)
        if p_ is None:
            continue
        rows.append({"cilj": y.index[i + h],
                     "ae": abs(y.iloc[i + h] - p_)})
    return pd.DataFrame(rows).set_index("cilj")["ae"]


b_rows = []
for s in vr.VSE_VRSTE:
    y = ocisceno(s)
    for h in HORIZONTI:
        naiv = wf(y, h, "naivni")
        for model in ("ar1", "lin"):
            alt = wf(y, h, model)
            idx = naiv.index.intersection(alt.index)
            dif = naiv.loc[idx] - alt.loc[idx]
            _, p = stats.wilcoxon(dif)
            b_rows.append({
                "vrsta": vr.IMENA[s], "vzs": s, "horizont": h, "model": model,
                "n": len(idx),
                "MAE_naivni": naiv.loc[idx].mean(), "MAE_model": alt.loc[idx].mean(),
                "delta_pct": 100 * (1 - alt.loc[idx].mean() / naiv.loc[idx].mean()),
                "wilcoxon_p": p,
                "prezivi_bonferroni": bool(p < BONF_14)})
B = pd.DataFrame(b_rows)
B.to_csv(REZ / "5_4_dopolnitve_B_pvrednosti.csv", index=False,
         encoding="utf-8-sig")

print(f"Bonferronijev prag za 14 primerjav: 0,05 / 14 = {BONF_14:.6f}\n")

print("--- B1: linearna regresija, endoproteza kolena, h = 1 ---")
b1 = B[(B["vzs"] == "1626") & (B["horizont"] == 1) & (B["model"] == "lin")].iloc[0]
print(f"  p = {b1['wilcoxon_p']:.8f}  ({b1['wilcoxon_p']:.4e})")
print(f"  Bonferronijev prag = {BONF_14:.6f}")
print(f"  -> {'POD pragom (prezivi)' if b1['wilcoxon_p'] < BONF_14 else 'NAD pragom (ne prezivi)'}")
zapisi("B1", "p lin/endoproteza/h=1", f"{b1['wilcoxon_p']:.8f}")
zapisi("B1", "prezivi Bonferroni 0,00357",
       "da" if b1["wilcoxon_p"] < BONF_14 else "ne")

for model in ("ar1", "lin"):
    print(f"\n--- B2: {model.upper()} — vseh 14 kombinacij ---")
    t = B[B["model"] == model][["vrsta", "horizont", "n", "delta_pct",
                                "wilcoxon_p", "prezivi_bonferroni"]].copy()
    t["delta_pct"] = t["delta_pct"].round(1)
    t["wilcoxon_p"] = t["wilcoxon_p"].map(lambda x: f"{x:.4f}")
    t["prezivi_bonferroni"] = t["prezivi_bonferroni"].map({True: "DA", False: "-"})
    print(t.sort_values(["horizont", "vrsta"]).to_string(index=False))
    n_pre = int(B[(B["model"] == model)]["prezivi_bonferroni"].sum())
    print(f"  prezivi Bonferronijev prag: {n_pre} od 14")
    zapisi("B2", f"{model}: prezivi Bonferroni", f"{n_pre}/14")


# ================================================ C. TRI RAZLICICE, NABOR 292
naslov("C. PRIMERJAVA TREH RAZLICIC Z NESPREMENJENIM NABOROM VZS")

extra10 = sorted(set(SET292) - set(SET282))
luknje = panel[panel["vzs_sifra"].isin(SET292) & panel[vr.KANON].isna()]
print("OVIRA — nabor 292 na 112 tednih NI dosegljiv brez posledic:\n")
print(f"  Nabor 292 je definiran kot popolna vrsta cez 110 ZANESLJIVIH tednov.")
print(f"  Na vseh 112 tednih ima ta nabor {len(luknje)} lukenj, vse na "
      f"{sorted(set(luknje['datum'].dt.date))[0]}:")
print(f"  gre za {len(extra10)} VZS, ki so v nabor vstopile prav zato, ker jim "
      f"manjka\n  natanko ta en teden: {', '.join(extra10)}")
v_pred = panel[(panel["datum"] == "2025-06-04")
               & (panel["vzs_sifra"].isin(extra10))][vr.KANON].sum()
v_po = panel[(panel["datum"] == "2025-06-18")
             & (panel["vzs_sifra"].isin(extra10))][vr.KANON].sum()
print(f"\n  Te VZS prispevajo {v_pred:.0f} cakajocih teden prej in {v_po:.0f} "
      f"teden pozneje;\n  ce bi agregat 11. 6. 2025 sestevali cez 292, bi bil "
      f"prenizek za ~{(v_pred + v_po) / 2:.0f}\n  cakajocih (~"
      f"{100 * ((v_pred + v_po) / 2) / 306000:.2f} % ravni), kar bi anomalijo "
      f"tistega tedna umetno POVECALO.")

print("\n  Moznosti (izbira je tvoja, skripta nobene ne razglasa za pravilno):")
print("    (1) FIKSEN NABOR 282 za vse tri razlicice — 282 je podmnozica 292 in")
print("        nima lukenj v nobenem tednu, zato se razlicice razlikujejo")
print("        IZKLJUCNO po izlocenih tednih. Cena: nabor je 282, ne 292.")
print("    (2) FIKSEN NABOR 292 za vse tri — cena: agregat 11. 6. 2025 je")
print("        prenizek za ~563 cakajocih (glej zgoraj), le v izhodiscni")
print("        razlicici; drugi dve ta teden itak izlocita.")
print("    (3) Nabor se dolocі znova v vsaki razlicici (282/292/292) —")
print("        to je sedanje stanje in je zmes obeh ucinkov.")
print("\n  Spodaj sta izracunani (1) in (2), da je razlika vidna.\n")

VARIANTE = {
    "izhodiscna": [],
    "delno_ocisceno": [pd.Timestamp("2025-06-11")],
    "ocisceno": NEZANESLJIVI,
}

c_rows = []
for oznaka_nabora, nabor in (("fiksni_282", SET282), ("fiksni_292", SET292)):
    for var, izl in VARIANTE.items():
        for s in vr.VSE_VRSTE:
            y = serija(s, izl, nabor)
            for h in HORIZONTI:
                naiv = wf(y, h, "naivni")
                for model in ("ar1", "lin"):
                    alt = wf(y, h, model)
                    idx = naiv.index.intersection(alt.index)
                    c_rows.append({
                        "nabor": oznaka_nabora, "razlicica": var,
                        "vrsta": vr.IMENA[s], "vzs": s, "horizont": h,
                        "model": model, "n": len(idx),
                        "delta_pct": 100 * (1 - alt.loc[idx].mean()
                                            / naiv.loc[idx].mean())})
C = pd.DataFrame(c_rows)
C.to_csv(REZ / "5_4_dopolnitve_C_tri_razlicice.csv", index=False,
         encoding="utf-8-sig")

for oznaka_nabora in ("fiksni_282", "fiksni_292"):
    for model in ("ar1", "lin"):
        sub = C[(C["nabor"] == oznaka_nabora) & (C["model"] == model)]
        piv = sub.pivot_table(index="vrsta", columns=["horizont", "razlicica"],
                              values="delta_pct")
        t = pd.DataFrame(index=piv.index)
        for h in HORIZONTI:
            t[f"h{h} izh."] = piv[(h, "izhodiscna")].round(1)
            t[f"h{h} delno"] = piv[(h, "delno_ocisceno")].round(1)
            t[f"h{h} ocis."] = piv[(h, "ocisceno")].round(1)
            t[f"h{h} korak1"] = (piv[(h, "delno_ocisceno")]
                                 - piv[(h, "izhodiscna")]).round(1)
            t[f"h{h} korak2"] = (piv[(h, "ocisceno")]
                                 - piv[(h, "delno_ocisceno")]).round(1)
        print(f"\n=== {oznaka_nabora}, {model.upper()} "
              f"(korak1 = izlocitev 11. 6., korak2 = izlocitev 20. 8.) ===")
        print(t.to_string())


# ================================================== D. POTRDITVE
naslov("D. POTRDITVE PODEDOVANIH STEVILK")

print(f"D1  vrstic panela: {len(panel):,}  "
      f"(pricakovano 41.767 -> "
      f"{'UJEMA SE' if len(panel) == 41767 else 'NE UJEMA SE'})")
zapisi("D1", "vrstic panela", len(panel))

y_ag = ocisceno(vr.AGREGAT)
koraki = y_ag.index.to_series().diff().dt.days.dropna()
nad8 = int((koraki > 8).sum())
print(f"\nD2  tednov v ocisceni vrsti: {len(y_ag)}")
print(f"    zaporednih korakov: {len(koraki)}  "
      f"(pricakovano 109 -> {'UJEMA SE' if len(koraki) == 109 else 'NE UJEMA SE'})")
print(f"    korakov, daljsih od 8 dni: {nad8} = {100 * nad8 / len(koraki):.1f} %  "
      f"(pricakovano 8 = 7,3 % -> "
      f"{'UJEMA SE' if nad8 == 8 else 'NE UJEMA SE'})")
print(f"    porazdelitev korakov (dni): "
      f"{koraki.astype(int).value_counts().sort_index().to_dict()}")
zapisi("D2", "zaporednih korakov", len(koraki))
zapisi("D2", "korakov nad 8 dni", nad8)
zapisi("D2", "delez korakov nad 8 dni (%)", round(100 * nad8 / len(koraki), 1))

# D3 — rekonstrukcija kontrole iz poskusa o interpolaciji
def na_iso_sredo(idx):
    iso = idx.isocalendar()
    return pd.DatetimeIndex(pd.to_datetime(
        iso["year"].astype(int).astype(str) + "-W"
        + iso["week"].astype(int).astype(str).str.zfill(2) + "-3",
        format="%G-W%V-%u"))


b_s = pd.Series(y_ag.values, index=na_iso_sredo(y_ag.index)).sort_index()
mreza = pd.date_range(b_s.index.min(), b_s.index.max(), freq="7D")
a_s = b_s.reindex(mreza).interpolate("linear")

nap = {}
for oznaka, yy in (("A", a_s), ("B", b_s)):
    rows = []
    for i in range(MIN_TRAIN - 1, len(yy) - 1):
        rows.append({"cilj": yy.index[i + 1], "izvor": yy.index[i],
                     "ae": abs(yy.iloc[i + 1] - yy.iloc[i])})
    nap[oznaka] = pd.DataFrame(rows).set_index("cilj")

skupni = nap["A"].index.intersection(nap["B"].index)
bv = [t for t in skupni
      if (t - nap["B"].loc[t, "izvor"]).days <= 7]
ae_a = nap["A"].loc[bv, "ae"]
ae_b = nap["B"].loc[bv, "ae"]
print(f"\nD3  kontrola iz poskusa o interpolaciji (naivni, agregat, h = 1,")
print(f"    testne tocke brez vrzeli, n = {len(bv)}):")
print(f"      povprecje |napake|  (MAE):    A = {ae_a.mean():.4f}  "
      f"B = {ae_b.mean():.4f}")
print(f"      mediana  |napake|:            A = {ae_a.median():.4f}  "
      f"B = {ae_b.median():.4f}")
print(f"      RMSE:                         A = {np.sqrt((ae_a**2).mean()):.4f}  "
      f"B = {np.sqrt((ae_b**2).mean()):.4f}")
print(f"    -> vrednost 1.452,92 je POVPRECJE absolutnih napak (MAE): "
      f"{'POTRJENO' if abs(ae_a.mean() - 1452.92) < 0.01 else 'NE UJEMA SE'}")
zapisi("D3", "MAE (kontrola brez vrzeli)", round(float(ae_a.mean()), 4))
zapisi("D3", "mediana abs. napake (za primerjavo)", round(float(ae_a.median()), 4))


# ========================================= E. RAST V SLIKOVNI DIAGNOSTIKI
naslov("E. OPISNA ANALIZA — KATERE STORITVE V RAZPONU 59,0 % DO 80,9 %")

nazivi = (panel.sort_values("datum").drop_duplicates("vzs_sifra", keep="last")
          .set_index("vzs_sifra")["vzs_naziv"])
rast = []
for s in SET292:
    y = ocisceno(s)
    if len(y) < 2 or y.iloc[0] == 0:
        continue
    rast.append({"vzs": s, "naziv": nazivi.get(s, ""),
                 "prva": y.iloc[0], "zadnja": y.iloc[-1],
                 "rast_pct": 100 * (y.iloc[-1] / y.iloc[0] - 1),
                 "mediana": y.median()})
R = pd.DataFrame(rast)
R["modelirana"] = R["vzs"].isin(vr.IZBRANE.keys())
R.round(2).to_csv(REZ / "5_4_dopolnitve_E_rast.csv", index=False,
                  encoding="utf-8-sig")

for sifra in ("1755", "1772", "1941"):
    r = R[R["vzs"] == sifra]
    if len(r):
        r = r.iloc[0]
        print(f"  {sifra:>5}  {r['naziv'][:40]:<42} "
              f"{r['prva']:>7.0f} -> {r['zadnja']:>7.0f} = "
              f"{r['rast_pct']:+6.1f} %   "
              f"{'MODELIRANA' if r['modelirana'] else 'ni med sesterico'}")
    else:
        print(f"  {sifra}: NI v naboru 292")

print(f"\n  1755 (MR glave) je med sesterico modeliranih storitev.")
v1772 = "1772" in set(R["vzs"])
print(f"  1772 (MR kolena) je v naboru 292: {'DA' if v1772 else 'NE'}; "
      f"med sesterico modeliranih: NE")

# slikovna diagnostika po nazivu
slik = R[R["naziv"].str.match(r"^(MR|CT|UZ|RTG)\b", na=False)].copy()
slik_vel = slik[slik["mediana"] >= 1000].sort_values("rast_pct")
print(f"\n  Slikovna diagnostika v naboru 292 (naziv se zacne z MR/CT/UZ/RTG): "
      f"{len(slik)} VZS,\n  od tega {len(slik_vel)} z mediano >= 1.000 cakajocih:")
print(slik_vel[["vzs", "naziv", "prva", "zadnja", "rast_pct", "modelirana"]]
      .round(1).to_string(index=False))
print(f"\n  Razpon rasti med temi: {slik_vel['rast_pct'].min():+.1f} % do "
      f"{slik_vel['rast_pct'].max():+.1f} %")
print(f"  Razpon rasti med MODELIRANIMA slikovnima (1755, 1941): "
      f"{R[R['vzs'].isin(['1755', '1941'])]['rast_pct'].min():+.1f} % do "
      f"{R[R['vzs'].isin(['1755', '1941'])]['rast_pct'].max():+.1f} %")
print("\n  SKLEP: razpon 59,0–80,9 % je racunan cez SIRSI nabor kot modelirana\n"
      "  sesterica — zgornja meja 80,9 % pripada VZS 1772 (MR kolena), ki je v\n"
      "  naboru 292, ni pa med sestimi modeliranimi storitvami. To je treba v\n"
      "  besedilu izrecno povedati.")
zapisi("E", "rast 1755 MR glave (%)",
       round(float(R[R["vzs"] == "1755"]["rast_pct"].iloc[0]), 1))
zapisi("E", "rast 1772 MR kolena (%)",
       round(float(R[R["vzs"] == "1772"]["rast_pct"].iloc[0]), 1))
zapisi("E", "1772 med modeliranimi", "ne")


# ================================= F. RAZPONI IZ POSKUSA O INTERPOLACIJI
naslov("F. RAZPONI IZ POSKUSA O INTERPOLACIJI, LOCENO PO HORIZONTIH")

pot = REZ / "5_4_ucinek_interpolacije_polno.csv"
if not pot.exists():
    print(f"  {pot.name} ne obstaja — pozeni najprej 23_ucinek_interpolacije.py")
else:
    I = pd.read_csv(pot)
    lin = I[I["model"] == "lin"]
    print("Sprememba lastnega MAE linearne regresije ob interpolaciji (A/B - 1):")
    for h in HORIZONTI:
        a = lin[(lin["horizont"] == h)
                & (lin["razlicica"] == "A_interpolirano")].set_index("vzs")["MAE"]
        b = lin[(lin["horizont"] == h)
                & (lin["razlicica"] == "B_brez_interpolacije")].set_index("vzs")["MAE"]
        d_ = 100 * (a / b - 1)
        print(f"  h = {h}: {d_.min():+.2f} % do {d_.max():+.2f} %  "
              f"(mediana {d_.median():+.2f} %)")
        zapisi("F", f"lin: sprememba MAE h={h} min (%)", round(float(d_.min()), 2))
        zapisi("F", f"lin: sprememba MAE h={h} max (%)", round(float(d_.max()), 2))

    print("\nPoslabsanje relativne uspesnosti linearne regresije (A - B, o. t.):")
    for h in HORIZONTI:
        a = lin[(lin["horizont"] == h)
                & (lin["razlicica"] == "A_interpolirano")
                ].set_index("vzs")["delta_MAE_proti_naivnemu_pct"]
        b = lin[(lin["horizont"] == h)
                & (lin["razlicica"] == "B_brez_interpolacije")
                ].set_index("vzs")["delta_MAE_proti_naivnemu_pct"]
        d_ = a - b
        print(f"  h = {h}: {d_.min():+.1f} do {d_.max():+.1f} o. t.  "
              f"(vse negativne: {'da' if (d_ < 0).all() else 'ne'})")
        zapisi("F", f"lin: poslabsanje h={h} min (o.t.)", round(float(d_.min()), 1))
        zapisi("F", f"lin: poslabsanje h={h} max (o.t.)", round(float(d_.max()), 1))

    print("\n  ODGOVOR: oba razpona, ki sta navedena v besedilu (-6,4 do +10,2 %\n"
          "  in 18,3 do 112,8 o. t.), sta racunana SAMO pri h = 1, ne cez oba\n"
          "  horizonta skupaj.")


# ------------------------------------------------------------------ izhod
naslov("IZHOD")
pd.DataFrame(izpis).to_csv(REZ / "5_4_dopolnitve.csv", index=False,
                           encoding="utf-8-sig")
print("Zapisano:")
for f in ["5_4_dopolnitve.csv", "5_4_dopolnitve_A1_zaznave.csv",
          "5_4_dopolnitve_B_pvrednosti.csv", "5_4_dopolnitve_C_tri_razlicice.csv",
          "5_4_dopolnitve_E_rast.csv"]:
    print(f"  rezultati/{f}")
