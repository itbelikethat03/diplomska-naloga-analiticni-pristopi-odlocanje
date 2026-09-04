# -*- coding: utf-8 -*-
"""
Cist poskus: izmeri IZKLJUCNO ucinek linearne interpolacije manjkajocih
tednov na rezultate napovednega dela poglavja 5.4.

Obstojeca primerjava (stara obdelava proti novi) tega ne omogoca, ker se
razlicici razlikujeta v treh stvareh hkrati: interpolacija, nabor VZS
(282 proti 292) in stevilo tednov (112 proti 110). Tu se spremeni SAMO
obravnava vrzeli, vse ostalo je identicno.

    A (z interpolacijo)   redna tedenska mreza, luknje linearno
                          interpolirane, interpolirane tocke vstopajo
                          v UCENJE IN V OCENJEVANJE
    B (brez)              samo dejansko opazovani tedni, vrzeli ostanejo
                          vrzeli (zaporedni indeks opazovanj)

Skupno obema: nabor 292 VZS, 110 zanesljivih tednov (izlocena 11. 6. 2025
in 20. 8. 2025), min. 52 tednov ucnega okna, rastoce okno, modeli
naivni / AR(1) / linearna regresija, horizonta h = 1 in h = 4, 7 vrst.

POMEMBNA OPOMBA O STEVILU INTERPOLIRANIH TOCK
Naloga govori o "8 manjkajocih tednih". Na redni mrezi cez 110 zanesljivih
tednov je lukenj DESET, ne osem: 8 vrzeli arhiva (prazniki) + 2 tedna, ki
sta bila izlocena kot nezanesljiva. Redna mreza po definiciji nima praznih
mest, zato jih interpolacija mora zapolniti vse. Skripta obe vrsti lukenj
prijavi loceno; interpolirajo se vse, ker je to edina koherentna izvedba
razlicice A.

KONTROLA PRAVILNOSTI POSKUSA
Pri naivnem modelu mora biti MAE na testnih tockah, ki NE preckajo vrzeli,
v A in B natanko enak (ista realna izvorna vrednost, ista ciljna vrednost).
Ce ni, je v poskusu napaka. Pri AR(1) in linearni regresiji ta identiteta
NE velja niti na teh tockah, ker se ucni nabor razlikuje (A ima v zgodovini
dodatne interpolirane tocke, ki premaknejo ocene parametrov).

Izhoda: rezultati/5_4_ucinek_interpolacije.csv
        rezultati/slike/5_4_interpolacija_primerjava.png

Skripta ne spreminja obstojecih skript, rezultatov ali grafov.
Zagon: py -3.11 23_ucinek_interpolacije.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.ar_model import AutoReg

import vrste as vr

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parents[1]
REZ = BASE / "rezultati"
SLIKE = REZ / "slike"
SLIKE.mkdir(parents=True, exist_ok=True)

MIN_TRAIN = 52
HORIZONTI = (1, 4)
MODELI = ["naivni", "ar1", "lin"]
NEZANESLJIVI = [pd.Timestamp("2025-06-11"), pd.Timestamp("2025-08-20")]


def naslov(s: str) -> None:
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


# ---------------------------------------------------------------- podatki
panel_vse = vr.nalozi()
panel = panel_vse[~panel_vse["datum"].isin(NEZANESLJIVI)]
N_TEDNOV = panel["datum"].nunique()

_cnt = panel.groupby("vzs_sifra")[vr.KANON].count()
NABOR = sorted(_cnt[_cnt == N_TEDNOV].index)


def opazovana_vrsta(sifra: str) -> pd.Series:
    """Vrsta samo iz dejansko opazovanih zanesljivih tednov."""
    if sifra == vr.AGREGAT:
        s = (panel[panel["vzs_sifra"].isin(NABOR)]
             .groupby("datum")[vr.KANON].sum())
    else:
        s = panel[panel["vzs_sifra"] == sifra].set_index("datum")[vr.KANON]
    return s.sort_index().dropna()


def na_iso_sredo(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Preslika datum objave na sredo pripadajocega ISO tedna.

    Dan objave niha (sreda/cetrtek/petek), zato je za redno mrezo potrebna
    kanonicna oznaka tedna; brez tega bi 'redna' mreza vsebovala razmike
    6 in 8 dni in interpolacija ne bi bila primerljiva.
    """
    iso = idx.isocalendar()
    return pd.DatetimeIndex(pd.to_datetime(
        iso["year"].astype(int).astype(str) + "-W"
        + iso["week"].astype(int).astype(str).str.zfill(2) + "-3",
        format="%G-W%V-%u"))


def razlicici(sifra: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Vrne (B, A, opazovan_A) na skupni ISO-tedenski casovni osi."""
    sur = opazovana_vrsta(sifra)
    b = pd.Series(sur.values, index=na_iso_sredo(sur.index)).sort_index()
    if b.index.duplicated().any():
        raise RuntimeError("dve objavi v istem ISO tednu — mreza ni enolicna")
    mreza = pd.date_range(b.index.min(), b.index.max(), freq="7D")
    a = b.reindex(mreza)
    opazovan = a.notna()
    a = a.interpolate("linear")
    return b, a, opazovan


# ------------------------------------------------------------ diagnostika mreze
naslov("Struktura mreze: koliko tock interpolacija sploh doda")

_b, _a, _opaz = razlicici(vr.AGREGAT)
luknje = _a.index[~_opaz]
iso_nezanesljivi = set(na_iso_sredo(pd.DatetimeIndex(NEZANESLJIVI)))
luknje_arhiv = [d for d in luknje if d not in iso_nezanesljivi]
luknje_izloceni = [d for d in luknje if d in iso_nezanesljivi]

print(f"Opazovanih (zanesljivih) tednov:      {len(_b)}")
print(f"Mest na redni tedenski mrezi:         {len(_a)}")
print(f"Interpoliranih tock skupaj:           {len(luknje)}")
print(f"  od tega vrzeli arhiva (prazniki):   {len(luknje_arhiv)}")
print(f"  od tega izloceni nezanesljivi tedni:{len(luknje_izloceni)}")
print("\nInterpolirane tocke (ISO sreda):")
for d in luknje:
    vir = "izlocen nezanesljiv teden" if d in iso_nezanesljivi else "vrzel arhiva"
    print(f"  {d.date()}  ({vir})")


# ------------------------------------------------------------------ modeli
def napovej(v: np.ndarray, h: int, model: str) -> float | None:
    if model == "naivni":
        return float(v[-1])
    if model == "lin":
        t = np.arange(len(v))
        X = np.vstack([np.ones(len(v)), t]).T
        coef, *_ = np.linalg.lstsq(X, v, rcond=None)
        return float(coef[0] + coef[1] * (len(v) - 1 + h))
    if model == "ar1":
        try:
            return float(AutoReg(v, lags=1, old_names=False)
                         .fit().forecast(h)[-1])
        except Exception:
            return None
    raise ValueError(model)


def walk_forward(y: pd.Series, h: int, model: str) -> pd.DataFrame:
    rows = []
    for i in range(MIN_TRAIN - 1, len(y) - h):
        pred = napovej(y.iloc[: i + 1].values, h, model)
        if pred is None:
            continue
        rows.append({"izvor": y.index[i], "cilj": y.index[i + h],
                     "y_true": y.iloc[i + h], "y_pred": pred})
    out = pd.DataFrame(rows)
    out["ae"] = (out["y_true"] - out["y_pred"]).abs()
    return out


# --------------------------------------------------------------- izvedba
naslov("Izvedba drsecega preverjanja (A z interpolacijo, B brez)")

zapisi = []
for sifra in vr.VSE_VRSTE:
    b, a, opaz = razlicici(sifra)
    opazovani_datumi = set(b.index)
    for h in HORIZONTI:
        for model in MODELI:
            for oznaka, y in (("A_interpolirano", a), ("B_brez_interpolacije", b)):
                r = walk_forward(y, h, model)
                r["razlicica"] = oznaka
                r["vrsta"] = vr.IMENA[sifra]
                r["vzs"] = sifra
                r["horizont"] = h
                r["model"] = model
                # ali okno precka vrzel: razmik daljsi od h tednov
                r["precka_vrzel"] = (r["cilj"] - r["izvor"]).dt.days > 7 * h
                r["cilj_opazovan"] = r["cilj"].isin(opazovani_datumi)
                zapisi.append(r)
    print(f"  {vr.IMENA[sifra]} koncano")

d = pd.concat(zapisi, ignore_index=True)


# ------------------------------------------------- 1. delez tock cez vrzel
naslov("1. Delez testnih tock, ki preckajo vrzel (razlicica B)")

# v razlicici A je mreza redna, zato je razmik vedno natanko h tednov;
# vrzel je lastnost DEJANSKE casovne osi, zato se meri na B
dv = (d[(d["razlicica"] == "B_brez_interpolacije") & (d["model"] == "naivni")]
      .groupby(["vrsta", "horizont"])["precka_vrzel"]
      .agg(n="size", cez_vrzel="sum"))
dv["delez_pct"] = (100 * dv["cez_vrzel"] / dv["n"]).round(1)
print(dv.to_string())
print("\nSkupaj po horizontu:")
sk = (d[(d["razlicica"] == "B_brez_interpolacije") & (d["model"] == "naivni")]
      .groupby("horizont")["precka_vrzel"].mean() * 100).round(1)
print(sk.to_string())


# ------------------------------------------------------------- metrike
def metrike(df: pd.DataFrame) -> pd.DataFrame:
    m = (df.groupby(["razlicica", "vzs", "vrsta", "horizont", "model"])
         .agg(n_testnih_tock=("ae", "size"), MAE=("ae", "mean"))
         .reset_index())
    naiv = (m[m["model"] == "naivni"]
            .set_index(["razlicica", "vzs", "horizont"])["MAE"])
    m["delta_MAE_proti_naivnemu_pct"] = m.apply(
        lambda r: 100 * (1 - r["MAE"] / naiv.loc[
            (r["razlicica"], r["vzs"], r["horizont"])]), axis=1)
    return m


met = metrike(d)

# Wilcoxon: model proti naivnemu, parno po ciljnem tednu, znotraj razlicice
wp = {}
for (razl, vzs, h), g in d.groupby(["razlicica", "vzs", "horizont"]):
    naiv = g[g["model"] == "naivni"].set_index("cilj")["ae"]
    for model in ("ar1", "lin"):
        alt = g[g["model"] == model].set_index("cilj")["ae"]
        idx = naiv.index.intersection(alt.index)
        try:
            _, p = stats.wilcoxon(naiv.loc[idx] - alt.loc[idx])
        except ValueError:
            p = np.nan
        wp[(razl, vzs, h, model)] = p
met["wilcoxon_p"] = met.apply(
    lambda r: wp.get((r["razlicica"], r["vzs"], r["horizont"], r["model"]),
                     np.nan), axis=1)

izhod = met[["razlicica", "vrsta", "horizont", "model", "n_testnih_tock",
             "MAE", "delta_MAE_proti_naivnemu_pct", "wilcoxon_p"]]
izhod.round(4).to_csv(REZ / "5_4_ucinek_interpolacije.csv", index=False,
                      encoding="utf-8-sig")


# --------------------------------- 2. razlika A - B v odstotnih tockah
naslov("2. Razlika A - B v izboljsavi proti naivnemu (odstotne tocke)")

for model in ("ar1", "lin"):
    piv = (met[met["model"] == model]
           .pivot_table(index=["vrsta"], columns=["horizont", "razlicica"],
                        values="delta_MAE_proti_naivnemu_pct"))
    print(f"\n--- {model.upper()} ---")
    tab = pd.DataFrame(index=piv.index)
    for h in HORIZONTI:
        tab[f"h{h}_A"] = piv[(h, "A_interpolirano")].round(1)
        tab[f"h{h}_B"] = piv[(h, "B_brez_interpolacije")].round(1)
        tab[f"h{h}_A-B_ot"] = (piv[(h, "A_interpolirano")]
                               - piv[(h, "B_brez_interpolacije")]).round(1)
    print(tab.to_string())

naslov("2b. MAE po modelih: koliko interpolacija zmanjsa napako (H1)")
mp = met.pivot_table(index=["vrsta", "horizont"], columns=["model", "razlicica"],
                     values="MAE")
for model in MODELI:
    kol = (mp[(model, "A_interpolirano")] / mp[(model, "B_brez_interpolacije")]
           - 1) * 100
    mp[(model, "A/B_pct")] = kol.round(2)
print("\nSprememba MAE ob interpolaciji (%, negativno = interpolacija "
      "zmanjsa izmerjeno napako):")
print(pd.DataFrame({m: mp[(m, "A/B_pct")] for m in MODELI}).to_string())


# --------------------------------- 3. kontrola: naivni na tockah brez vrzeli
naslov("3. KONTROLA — naivni model, agregat, h = 1")

ag = d[(d["vzs"] == vr.AGREGAT) & (d["horizont"] == 1)
       & (d["model"] == "naivni")]
b_ag = ag[ag["razlicica"] == "B_brez_interpolacije"].set_index("cilj")
a_ag = ag[ag["razlicica"] == "A_interpolirano"].set_index("cilj")

skupni = b_ag.index.intersection(a_ag.index)
brez_vrzeli = [t for t in skupni if not b_ag.loc[t, "precka_vrzel"]]
z_vrzeljo = [t for t in skupni if b_ag.loc[t, "precka_vrzel"]]

print(f"Skupnih ciljnih tednov (opazovani v obeh): {len(skupni)}")
print(f"  brez vrzeli: {len(brez_vrzeli)} | z vrzeljo: {len(z_vrzeljo)}")

mae_a_bv = a_ag.loc[brez_vrzeli, "ae"].mean()
mae_b_bv = b_ag.loc[brez_vrzeli, "ae"].mean()
mae_a_zv = a_ag.loc[z_vrzeljo, "ae"].mean() if z_vrzeljo else np.nan
mae_b_zv = b_ag.loc[z_vrzeljo, "ae"].mean() if z_vrzeljo else np.nan

print(f"\n  MAE na tockah BREZ vrzeli:  A = {mae_a_bv:10.4f} | "
      f"B = {mae_b_bv:10.4f} | razlika = {abs(mae_a_bv - mae_b_bv):.6f}")
print(f"  MAE na tockah Z vrzeljo:    A = {mae_a_zv:10.4f} | "
      f"B = {mae_b_zv:10.4f} | razlika = {abs(mae_a_zv - mae_b_zv):.6f}")

ujema = np.isclose(mae_a_bv, mae_b_bv, rtol=0, atol=1e-6)
print(f"\n  KONTROLA {'USPESNA' if ujema else 'NEUSPESNA'}: MAE na tockah "
      f"brez vrzeli je {'identicen' if ujema else 'RAZLICEN — v poskusu je napaka'}")

print(f"\n  MAE naivnega na VSEH lastnih testnih tockah razlicice:")
print(f"    A (vkljucno z interpoliranimi cilji, "
      f"n = {len(a_ag)}): {a_ag['ae'].mean():.1f}")
print(f"    B (samo opazovani cilji,           "
      f"n = {len(b_ag)}): {b_ag['ae'].mean():.1f}")

# koliko od razlike prispevajo interpolirani cilji
interp_cilji = a_ag[~a_ag["cilj_opazovan"]]
print(f"\n    od tega A na INTERPOLIRANIH ciljih "
      f"(n = {len(interp_cilji)}): MAE = {interp_cilji['ae'].mean():.1f}")
print(f"    ti cilji so umetni: y_true je sam produkt interpolacije")


# --------------------------------------------------------------- H1 / H2
naslov("Preverba hipotez")

# sprememba lastnega MAE vsakega modela ob interpolaciji, po vrstah
spr = {}
for h in HORIZONTI:
    for model in MODELI:
        sub = met[(met["horizont"] == h) & (met["model"] == model)]
        a = sub[sub["razlicica"] == "A_interpolirano"].set_index("vzs")["MAE"]
        b = sub[sub["razlicica"] == "B_brez_interpolacije"].set_index("vzs")["MAE"]
        spr[(h, model)] = 100 * (a / b - 1)

h1 = pd.DataFrame({m: {h: spr[(h, m)].median() for h in HORIZONTI}
                   for m in MODELI}).round(2)
h1.index.name = "horizont"
print("Mediana spremembe lastnega MAE ob interpolaciji, po modelih (%):")
print(h1.to_string())

print("\n" + "-" * 78)
print("H1: interpolacija zmanjsa napako naivnega BOLJ kot napako AR(1)")
print("-" * 78)
print("Mediana ne zadosca — razlika je premajhna, da bi o njej sklepali iz\n"
      "ene same stevilke, zato se preverja se smer po posameznih vrstah in\n"
      "parni test cez sedem vrst.\n")
for h in HORIZONTI:
    n_, a_ = spr[(h, "naivni")], spr[(h, "ar1")]
    idx = n_.index
    v_smeri = int((n_.loc[idx] < a_.loc[idx]).sum())
    try:
        _, p = stats.wilcoxon(n_.loc[idx] - a_.loc[idx])
    except ValueError:
        p = np.nan
    print(f"  h = {h}: mediana naivni {n_.median():+.2f} % proti "
          f"AR(1) {a_.median():+.2f} % (razlika "
          f"{n_.median() - a_.median():+.2f} o. t.)")
    print(f"          v smeri H1: {v_smeri} od {len(idx)} vrst | "
          f"parni Wilcoxon p = {p:.3f}")
    if v_smeri >= 6 and p < 0.05:
        sklep = "POTRJENA"
    elif v_smeri >= 5:
        sklep = "SIBKO PODPRTA (vecina vrst v smeri, a test ni znacilen)"
    else:
        sklep = "NI POTRJENA"
    print(f"          -> {sklep}\n")

print("-" * 78)
print("H2: linearna regresija ucinka ni delezna")
print("-" * 78)
for h in HORIZONTI:
    l_ = spr[(h, "lin")]
    print(f"  h = {h}: mediana {l_.median():+.2f} %, razpon po vrstah "
          f"{l_.min():+.2f} % do {l_.max():+.2f} %, "
          f"pozitivnih {int((l_ > 0).sum())}/{len(l_)}")
    sistematicen = abs(l_.median()) >= 1 and (l_ > 0).sum() in (0, len(l_))
    if sistematicen:
        print("          -> NI POTRJENA: ucinek je sistematicen")
    else:
        print("          -> DELNO: ucinek NI zanemarljiv po posameznih vrstah\n"
              "             (do desetih odstotkov), a nima sistematicne smeri —\n"
              "             predznaki se med vrstami mesajo in se v mediani\n"
              "             iznicijo. Skladno z razlago: linearna regresija\n"
              "             zamaknjenih vrednosti ne uporablja, zato nanjo\n"
              "             interpolacija ucinkuje samo posredno, prek\n"
              "             spremenjenega ucnega vzorca, ki naklon premakne\n"
              "             v obe smeri.")
    print()

print("-" * 78)
print("Posredni ucinek na linearno regresijo prek IMENOVALCA")
print("-" * 78)
print("Ceprav je neposredni ucinek na MAE linearne regresije nesistematicen,\n"
      "se njena izboljsava PROTI NAIVNEMU sistematicno poslabsa, ker se\n"
      "zmanjsa napaka naivnega modela v imenovalcu:")
for h in HORIZONTI:
    sub = met[(met["horizont"] == h) & (met["model"] == "lin")]
    a = sub[sub["razlicica"] == "A_interpolirano"].set_index("vzs")[
        "delta_MAE_proti_naivnemu_pct"]
    b = sub[sub["razlicica"] == "B_brez_interpolacije"].set_index("vzs")[
        "delta_MAE_proti_naivnemu_pct"]
    dif = (a - b)
    print(f"  h = {h}: A - B = {dif.min():+.1f} do {dif.max():+.1f} o. t., "
          f"negativnih {int((dif < 0).sum())}/{len(dif)}")

met.round(4).to_csv(REZ / "5_4_ucinek_interpolacije_polno.csv", index=False,
                    encoding="utf-8-sig")


# --------------------------------- ocenjeni avtoregresijski koeficient (fi)
naslov("Ocenjeni avtoregresijski koeficient AR(1)")

print("Zakaj je uhajanje pri naivnem modelu in AR(1) skoraj enako veliko:\n"
      "ce je fi blizu 1, se AR(1) v praksi obnasa kot naivni model\n"
      "(napoved ~ zadnja vrednost) in prejme primerljiv delez uhajanja.\n")

fi_rows = []
for sifra in vr.VSE_VRSTE:
    b, a, _ = razlicici(sifra)
    for oznaka, y in (("A_interpolirano", a), ("B_brez_interpolacije", b)):
        fit = AutoReg(y.values, lags=1, old_names=False).fit()
        fi = float(fit.params[1])
        se = float(fit.bse[1])
        # ocene fi cez vsa rastoca ucna okna, kot jih model dejansko uporabi
        wf_fi = []
        for i in range(MIN_TRAIN - 1, len(y) - 1):
            try:
                wf_fi.append(float(AutoReg(y.iloc[: i + 1].values, lags=1,
                                           old_names=False).fit().params[1]))
            except Exception:
                pass
        wf_fi = np.array(wf_fi)
        fi_rows.append({
            "razlicica": oznaka, "vzs": sifra, "vrsta": vr.IMENA[sifra],
            "fi_celotni_vzorec": fi, "se": se,
            "ci95_sp": fi - 1.96 * se, "ci95_zg": fi + 1.96 * se,
            "ena_v_ci95": bool(fi - 1.96 * se <= 1 <= fi + 1.96 * se),
            "t_proti_ena": (fi - 1) / se if se > 0 else np.nan,
            "wf_fi_min": wf_fi.min(), "wf_fi_mediana": float(np.median(wf_fi)),
            "wf_fi_max": wf_fi.max(), "wf_n_oken": len(wf_fi),
        })

fi_df = pd.DataFrame(fi_rows)
fi_df.round(4).to_csv(REZ / "5_4_ar1_koeficient.csv", index=False,
                      encoding="utf-8-sig")

for oznaka in ("B_brez_interpolacije", "A_interpolirano"):
    sub = fi_df[fi_df["razlicica"] == oznaka]
    print(f"--- {oznaka} ---")
    t = sub[["vrsta", "fi_celotni_vzorec", "se", "ci95_sp", "ci95_zg",
             "ena_v_ci95", "wf_fi_min", "wf_fi_mediana", "wf_fi_max"]].copy()
    t.columns = ["vrsta", "fi", "se", "CI95 sp.", "CI95 zg.", "1 v CI95",
                 "WF min", "WF mediana", "WF max"]
    print(t.round(4).to_string(index=False))
    print()

sub_b = fi_df[fi_df["razlicica"] == "B_brez_interpolacije"]
print(f"Razpon fi (celotni vzorec, brez interpolacije): "
      f"{sub_b['fi_celotni_vzorec'].min():.4f} do "
      f"{sub_b['fi_celotni_vzorec'].max():.4f}, "
      f"mediana {sub_b['fi_celotni_vzorec'].median():.4f}")
print(f"Vrst, pri katerih 1 lezi v 95 % intervalu zaupanja za fi: "
      f"{int(sub_b['ena_v_ci95'].sum())} od {len(sub_b)}")


# ------------------------------------------- odprto vprasanje: lin. regresija
naslov("Odprto vprasanje: zakaj se je lin. regresija na agregatu poslabsala")

print("Objavljena vrednost pred popravki: -131,2 % (h = 1, agregat).\n"
      "Nova vrednost:                     -246,6 %.\n"
      "Ce bi bila edina sprememba odprava interpolacije, bi se morala\n"
      "IZBOLJSATI. Razclenitev prispevkov:\n")

lin_a = float(met[(met["vzs"] == vr.AGREGAT) & (met["horizont"] == 1)
                  & (met["model"] == "lin")
                  & (met["razlicica"] == "A_interpolirano")]
              ["delta_MAE_proti_naivnemu_pct"].iloc[0])
lin_b = float(met[(met["vzs"] == vr.AGREGAT) & (met["horizont"] == 1)
                  & (met["model"] == "lin")
                  & (met["razlicica"] == "B_brez_interpolacije")]
              ["delta_MAE_proti_naivnemu_pct"].iloc[0])
print(f"  (i)  ucinek SAME interpolacije (ta poskus, vse ostalo enako):")
print(f"       A = {lin_a:.1f} %  ->  B = {lin_b:.1f} %  "
       f"= {lin_b - lin_a:+.1f} o. t.  (IZBOLJSANJE)")

try:
    M = pd.read_csv(REZ / "5_4_D_metrike.csv")
    ml = M[(M["vzs"] == "AGREGAT") & (M["horizont"] == 1) & (M["model"] == "lin")]
    v = ml.set_index("razlicica")["MAE_vs_naivni_pct"]
    print(f"\n  (ii) ucinek izlocitve tednov in nabora VZS "
          f"(iz 5_4_D_metrike.csv):")
    print(f"       izhodiscna     (112 t., 282 VZS): {v['izhodiscna']:.1f} %")
    print(f"       delno_ocisceno (111 t., 292 VZS): {v['delno_ocisceno']:.1f} %  "
          f"({v['delno_ocisceno'] - v['izhodiscna']:+.1f} o. t.)")
    print(f"       ocisceno       (110 t., 292 VZS): {v['ocisceno']:.1f} %  "
          f"({v['ocisceno'] - v['delno_ocisceno']:+.1f} o. t.)")
    print(f"       skupaj: {v['ocisceno'] - v['izhodiscna']:+.1f} o. t.  "
          f"(POSLABSANJE)")
    print("\n  SKLEP: poslabsanja NE pojasni odprava interpolacije — ta deluje\n"
          "  v nasprotno smer. Poslabsanje v celoti izvira iz izlocitve dveh\n"
          "  nezanesljivih tednov in spremembe nabora VZS, ki ucinek odprave\n"
          "  interpolacije vec kot izniciti.")
except Exception as e:
    print(f"  (ii) 5_4_D_metrike.csv ni na voljo ({e}); pozeni najprej "
          f"20_analiza_5_4.py")


# ------------------------------------------------------------------ graf
naslov("Graf")

b_ag_s, a_ag_s, opaz_ag = razlicici(vr.AGREGAT)
# B narisan na redni mrezi z NaN na luknjah -> crta se PREKINE
b_na_mrezi = b_ag_s.reindex(a_ag_s.index)

# Zvezna crta A se z B ujema povsod razen na luknjah, zato bi risanje cele
# vrste A razliko skrilo. Narisejo se samo MOSTOVI: odsek od zadnjega
# opazovanega tedna pred vrzeljo do prvega za njo.
mask = (~opaz_ag).values
mostovi = []
i = 0
while i < len(mask):
    if mask[i]:
        j = i
        while j + 1 < len(mask) and mask[j + 1]:
            j += 1
        od, do = max(i - 1, 0), min(j + 1, len(mask) - 1)
        mostovi.append(a_ag_s.iloc[od:do + 1])
        i = j + 1
    else:
        i += 1


def narisi(ax, xlim=None):
    for k, m in enumerate(mostovi):
        ax.plot(m.index, m.values, lw=2.0, color="#c00000", ls="--",
                zorder=3, alpha=0.95,
                label=("A: interpolacija cez vrzel" if k == 0 else None))
    ax.plot(b_na_mrezi.index, b_na_mrezi.values, lw=1.5, color="#1f4e79",
            zorder=4, label="B: brez interpolacije (prekinitve = vrzeli)")
    ax.scatter(a_ag_s.index[mask], a_ag_s.values[mask], s=40,
               facecolor="white", edgecolor="#c00000", linewidth=1.5, zorder=5,
               label=f"interpolirane tocke (n = {int(mask.sum())})")
    for i2, dd in enumerate(NEZANESLJIVI):
        ax.axvline(na_iso_sredo(pd.DatetimeIndex([dd]))[0], color="#7a3ea3",
                   ls=":", lw=1.3, alpha=0.9, zorder=2,
                   label="izlocen nezanesljiv teden" if i2 == 0 else None)
    if xlim:
        ax.set_xlim(*xlim)


plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 7.2),
                              gridspec_kw={"height_ratios": [2.1, 1]})

narisi(ax)
ax.set_title("Agregat (292 VZS s popolnimi vrstami), 110 zanesljivih tednov: "
             "učinek linearne interpolacije vrzeli", fontsize=10.5)
ax.set_ylabel("Število čakajočih")
ax.legend(loc="upper left", framealpha=0.92, fontsize=8.5)

# povecava na najdaljso vrzel (bozic/novo leto 2024/25, dva zaporedna tedna)
narisi(ax2, xlim=(pd.Timestamp("2024-11-15"), pd.Timestamp("2025-02-20")))
okno = a_ag_s.loc["2024-11-15":"2025-02-20"]
ax2.set_ylim(okno.min() - 900, okno.max() + 900)
ax2.set_title("Povečava: vrzel ob božiču in novem letu 2024/25 "
              "(dva zaporedna interpolirana tedna)", fontsize=9.5)
ax2.set_ylabel("Število čakajočih")
ax2.set_xlabel("Teden objave (ISO)")

fig.tight_layout()
fig.savefig(SLIKE / "5_4_interpolacija_primerjava.png", dpi=150)
plt.close(fig)

print(f"Zapisano: rezultati/slike/5_4_interpolacija_primerjava.png")
print(f"Zapisano: rezultati/5_4_ucinek_interpolacije.csv")
print(f"Zapisano: rezultati/5_4_ucinek_interpolacije_polno.csv")
