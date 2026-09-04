# -*- coding: utf-8 -*-
"""
Diagnostika kakovosti panela pred popravki poglavja 5.4.

Pokriva korake A1, A2, A3, A5 in A6 iz seznama popravkov:

  A1  kanonicni stolpec za "cakajoce" (preveri identiteto
      cak_skupaj == cak_zelo_hitro + cak_hitro + cak_redno in izkljuci
      dvojno stetje, ki nastane ob vsoti vseh 17 stevilskih stolpcev),
  A2  koledar pricakovanih tednov (zaporedje vseh tednov med prvo in
      zadnjo objavo proti dejanskim datotekam),
  A3  iskanje VSEH prizadetih tednov (delez praznih vrednosti in
      tedenska sprememba agregata cez celotni arhiv),
  A5  uskladitev stevila vrstic panela (112 x 373 != 41.767),
  A6  nabor VZS s popolno vrsto, z in brez prizadetih tednov.

Skripta samo bere in porocila; panela ne spreminja.
Izhod: rezultati/diag_*.csv + izpis na zaslon.
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
REZ = BASE / "rezultati"
REZ.mkdir(exist_ok=True)

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 200)

panel = pd.read_parquet(BASE / "data" / "panel_vzs.parquet")
dates = pd.Series(sorted(panel["datum"].unique()))

CAK_NUJNOST = ["cak_zelo_hitro", "cak_hitro", "cak_redno"]
KANON = "cak_skupaj"


def naslov(s: str) -> None:
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


# ============================================================== A1
naslov("A1 — kanonicni stolpec za stevilo cakajocih")

vsi_stevilski = [c for c in panel.columns
                 if panel[c].dtype.kind in "if"]
print(f"Stevilskih stolpcev v panelu: {len(vsi_stevilski)}")
print("  ", ", ".join(vsi_stevilski))

# identiteta: ali je cak_skupaj vsota treh stopenj nujnosti?
sub = panel[CAK_NUJNOST + [KANON]].copy()
vsota_nujnosti = sub[CAK_NUJNOST].sum(axis=1, min_count=1)
oba = sub[KANON].notna() & vsota_nujnosti.notna()
razlika = (sub.loc[oba, KANON] - vsota_nujnosti[oba])
print(f"\nVrstic, kjer sta definirana oba (cak_skupaj in vsota nujnosti): {int(oba.sum())}")
print(f"  ujemanje na enoto natancno: {int((razlika == 0).sum())} "
      f"({(razlika == 0).mean() * 100:.2f} %)")
print(f"  neujemanj: {int((razlika != 0).sum())}, "
      f"max |razlika|: {razlika.abs().max() if len(razlika) else 0}")

# koliko znasa napacna vsota vseh stolpcev s 'cakajoc' v imenu (stara diagnostika)
napacni = [c for c in panel.columns if c.startswith(("cak_", "nad_"))]
teden_primer = pd.Timestamp("2025-06-11")
d0 = panel[panel["datum"] == teden_primer]
print(f"\nPrimerjava na tednu {teden_primer.date()}:")
print(f"  vsota kanonicnega stolpca {KANON:>12}: {d0[KANON].sum():>12,.0f}")
print(f"  vsota vseh stolpcev cak_*+nad_* ({len(napacni)}): "
      f"{d0[napacni].sum().sum():>12,.0f}   <- dvojno stetje, NE uporabljaj")

# ============================================================== A2
naslov("A2 — koledar pricakovanih tednov")

# Dan objave ni fiksen (sreda/cetrtek/petek), zato 7-dnevna mreza od prve
# objave ne deluje; koledar se gradi po ISO tednih (leto, teden).
dow = dates.dt.day_name().value_counts()
print("Dan v tednu pri objavah:", dow.to_dict())

iso = dates.dt.isocalendar()
kljuc = list(zip(iso["year"].astype(int), iso["week"].astype(int)))
objave = pd.DataFrame({"datum": dates, "iso_leto": iso["year"].astype(int).values,
                       "iso_teden": iso["week"].astype(int).values})

prvi, zadnji = dates.iloc[0], dates.iloc[-1]
# pricakovano zaporedje ISO tednov med prvo in zadnjo objavo
mreza = pd.date_range(prvi - pd.Timedelta(days=int(prvi.dayofweek)),
                      zadnji, freq="7D")          # ponedeljki vseh vmesnih tednov
mreza_iso = mreza.isocalendar()
pricakovani = list(zip(mreza_iso["year"].astype(int),
                       mreza_iso["week"].astype(int)))
dejanski = set(kljuc)
manjka_iso = [k for k in pricakovani if k not in dejanski]
podvojeni = [k for k in set(kljuc) if kljuc.count(k) > 1]

print(f"\nObdobje: {prvi.date()} – {zadnji.date()}")
print(f"Pricakovanih ISO tednov: {len(pricakovani)}")
print(f"Dejanskih objav:         {len(dates)}")
print(f"ISO tednov z 2 objavama: {len(podvojeni)}"
      + (f" -> {podvojeni}" if podvojeni else ""))
print(f"\nMANJKAJOCIH TEDNOV: {len(manjka_iso)}")

gaps = dates.diff().dt.days
vrstice = []
for (leto, teden) in manjka_iso:
    pon = pd.Timestamp.fromisocalendar(leto, teden, 1)
    poz = dates[dates < pon].iloc[-1] if (dates < pon).any() else pd.NaT
    nas = dates[dates > pon].iloc[0] if (dates > pon).any() else pd.NaT
    vrstice.append({"iso_leto": leto, "iso_teden": teden,
                    "ponedeljek": pon.date(),
                    "prejsnja_objava": poz.date(), "naslednja_objava": nas.date(),
                    "vrzel_dni": (nas - poz).days})
    print(f"  ISO {leto}-W{teden:02d} (teden od {pon.date()}): vrzel "
          f"{poz.date()} -> {nas.date()} = {(nas - poz).days} dni")

pd.DataFrame(vrstice).to_csv(REZ / "diag_a2_manjkajoci_tedni.csv",
                             index=False, encoding="utf-8-sig")

print("\nPorazdelitev razmikov med objavami (dni):",
      gaps.dropna().astype(int).value_counts().sort_index().to_dict())

# ============================================================== A3
naslov("A3 — iskanje VSEH prizadetih tednov")

# (a) delez praznih vrednosti kanonicnega stolpca po tednu
po_tednu = panel.groupby("datum").agg(
    n_vrstic=("vzs_sifra", "size"),
    n_vzs=("vzs_sifra", "nunique"),
    n_cak=(KANON, "count"),
)
po_tednu["delez_praznih"] = 1 - po_tednu["n_cak"] / po_tednu["n_vrstic"]

# (b) agregat cez URAVNOTEZEN nabor VZS (brez ucinka spremembe nabora):
#     VZS, ki imajo vrednost v vseh 112 tednih
polni_vsi = (panel.groupby("vzs_sifra")[KANON].count() == len(dates))
polni_vsi = set(polni_vsi[polni_vsi].index)
ag_bal = (panel[panel["vzs_sifra"].isin(polni_vsi)]
          .groupby("datum")[KANON].sum())
po_tednu["agregat_bal"] = ag_bal
po_tednu["agregat_vse"] = panel.groupby("datum")[KANON].sum()

# tedenska sprememba, normirana na dolzino razmika (vrzeli!)
po_tednu = po_tednu.reset_index()
po_tednu["dni_od_prej"] = po_tednu["datum"].diff().dt.days
po_tednu["dif"] = po_tednu["agregat_bal"].diff()
po_tednu["dif_na_teden"] = po_tednu["dif"] / (po_tednu["dni_od_prej"] / 7)
po_tednu["dif_rel"] = po_tednu["dif"] / po_tednu["agregat_bal"].shift(1)


def robust_z(x: pd.Series) -> pd.Series:
    x = x.astype(float)
    med = x.median()
    mad = (x - med).abs().median()
    return (x - med) / (1.4826 * mad) if mad > 0 else pd.Series(np.nan, index=x.index)


po_tednu["z_dif"] = robust_z(po_tednu["dif_na_teden"])
po_tednu["z_praznih"] = robust_z(po_tednu["delez_praznih"])

print(f"Uravnotezen nabor VZS (vrednost v vseh {len(dates)} tednih): {len(polni_vsi)}")
print(f"\nDelez praznih vrednosti {KANON} po tednu: "
      f"mediana {po_tednu['delez_praznih'].median():.4f}, "
      f"min {po_tednu['delez_praznih'].min():.4f}, "
      f"max {po_tednu['delez_praznih'].max():.4f}")

PRAG = 4.0
sum_praznih = po_tednu[po_tednu["z_praznih"].abs() > PRAG]
sum_dif = po_tednu[po_tednu["z_dif"].abs() > PRAG]

print(f"\n--- tedni z odstopajocim delezem praznih (|robustni z| > {PRAG}) ---")
if sum_praznih.empty:
    print("  (nobenega)")
else:
    print(sum_praznih[["datum", "n_vrstic", "n_cak", "delez_praznih",
                       "z_praznih"]].to_string(index=False))

print(f"\n--- tedni z odstopajoco tedensko spremembo agregata (|robustni z| > {PRAG}) ---")
print(sum_dif[["datum", "dni_od_prej", "agregat_bal", "dif", "dif_na_teden",
               "dif_rel", "z_dif"]].to_string(index=False))

# 10 najvecjih absolutnih sprememb — za oceno, kje je meja "normalnega"
print("\n--- 12 najvecjih |tedenskih sprememb| agregata (uravnotezen nabor) ---")
top = po_tednu.reindex(po_tednu["dif_na_teden"].abs().sort_values(
    ascending=False).index).head(12)
print(top[["datum", "dni_od_prej", "agregat_bal", "dif_na_teden", "dif_rel",
           "z_dif", "delez_praznih"]].to_string(index=False))

# pari padec-odboj: sosednji spremembi nasprotnega predznaka, obe veliki
po_tednu["dif_nasl"] = po_tednu["dif_na_teden"].shift(-1)
meja = po_tednu["dif_na_teden"].abs().quantile(0.90)
pari = po_tednu[(po_tednu["dif_na_teden"].abs() > meja)
                & (po_tednu["dif_nasl"].abs() > meja)
                & (np.sign(po_tednu["dif_na_teden"]) != np.sign(po_tednu["dif_nasl"]))]
print(f"\n--- pari padec–odboj (obe spremembi > 90. percentil = {meja:,.0f}) ---")
print(pari[["datum", "dif_na_teden", "dif_nasl", "delez_praznih"]]
      .to_string(index=False))

print("\n--- 10 tednov z najvecjim delezem praznih vrednosti ---")
print(po_tednu.nlargest(10, "delez_praznih")[
    ["datum", "n_vrstic", "n_cak", "delez_praznih", "z_praznih"]]
    .to_string(index=False))

po_tednu.to_csv(REZ / "diag_a3_tedenska_diagnostika.csv", index=False,
                encoding="utf-8-sig")

# ---------------------------------------------------------------- A3, sloj 2
# Agregat lahko skrije, kaj se dogaja spodaj: en velik VZS z veliko spremembo
# ali sistemski izpad pri mnogih. Zato po VZS: kolikSen delez uravnotezenega
# nabora ima ta teden (a) mocan padec, (b) V-obliko padec->odboj.
print("\n" + "-" * 78)
print("A3, sloj 2 — koliksen delez posameznih VZS je prizadet v danem tednu")
print("-" * 78)

sir = (panel[panel["vzs_sifra"].isin(polni_vsi)]
       .pivot_table(index="datum", columns="vzs_sifra", values=KANON))
rel = sir.pct_change()
rel_nasl = rel.shift(-1)

PADEC = -0.05          # padec za vec kot 5 % v enem tednu
ODBOJ = 0.05
v_oblika = (rel < PADEC) & (rel_nasl > ODBOJ)

sloj2 = pd.DataFrame({
    "delez_padec": (rel < PADEC).mean(axis=1),
    "delez_rast": (rel > ODBOJ).mean(axis=1),
    "delez_v_oblika": v_oblika.mean(axis=1),
    "mediana_rel_spr": rel.median(axis=1),
})
print("\nTedni, kjer ima >10 % VZS padec nad 5 % (uravnotezen nabor "
      f"{len(polni_vsi)} VZS):")
print(sloj2[sloj2["delez_padec"] > 0.10].round(4).to_string())

print("\nTedni, kjer ima >5 % VZS V-obliko (padec -> odboj):")
print(sloj2[sloj2["delez_v_oblika"] > 0.05].round(4).to_string())

print("\n10 tednov z najbolj negativno MEDIANO relativne spremembe "
      "(sistemski premik, neodvisen od velikosti VZS):")
print(sloj2.nsmallest(10, "mediana_rel_spr").round(4).to_string())

sloj2.to_csv(REZ / "diag_a3_po_vzs_sloj2.csv", encoding="utf-8-sig")

# kdo poganja posamezne kandidatne tedne
kandidatni = [pd.Timestamp(d) for d in
              sorted(set(sum_dif["datum"]) | set(sum_praznih["datum"]))]
for d in kandidatni:
    if d not in rel.index:
        continue
    r = rel.loc[d].dropna()
    abs_spr = (sir.loc[d] - sir.shift(1).loc[d]).dropna()
    print(f"\n--- {d.date()}: struktura spremembe ---")
    print(f"  VZS s padcem >5 %: {(r < PADEC).sum()} / {len(r)}   "
          f"| z rastjo >5 %: {(r > ODBOJ).sum()}   "
          f"| mediana rel. spremembe: {r.median():+.4f}")
    print("  5 najvecjih absolutnih padcev:")
    for s, v in abs_spr.nsmallest(5).items():
        print(f"    {s:>6}  {v:>10,.0f}  ({r.get(s, float('nan')):+.1%})")

# ---------------------------------------------------------------- A3, sloj 3
# Ne gre le za enotedenske izpade: posamezen VZS lahko vec tednov zapored
# porocav prenizko raven in se nato vrne (blok-izpad). Tak vzorec se v
# tedenskih razlikah pokaze kot dva locena "dogodka" (padec ob zacetku,
# odboj ob koncu), ceprav gre za en sam pojav.
print("\n" + "-" * 78)
print("A3, sloj 3 — blok-izpadi po posameznih VZS (>=2 tedna pod lokalno ravnjo)")
print("-" * 78)

rm = sir.rolling(11, center=True, min_periods=5).median()
dev = (sir - rm) / rm
pod = dev < -0.25
nazivi_vsi = panel.drop_duplicates("vzs_sifra").set_index("vzs_sifra")["vzs_naziv"]

bloki = []
for c in sir.columns:
    m = pod[c].values
    i = 0
    while i < len(m):
        if m[i]:
            j = i
            while j + 1 < len(m) and m[j + 1]:
                j += 1
            if j - i + 1 >= 2:
                bloki.append({
                    "vzs_sifra": c, "vzs_naziv": nazivi_vsi.get(c, "")[:45],
                    "od": pd.Timestamp(sir.index[i]).date(),
                    "do": pd.Timestamp(sir.index[j]).date(),
                    "tednov": j - i + 1,
                    "najv_odklon": round(float(dev[c].iloc[i:j + 1].min()), 3),
                    "povpr_raven": int(sir[c].iloc[i:j + 1].mean()),
                    "lokalna_mediana": int(rm[c].iloc[i:j + 1].median())})
            i = j + 1
        else:
            i += 1
bl = pd.DataFrame(bloki)
bl["manjkajoc_obseg"] = bl["lokalna_mediana"] - bl["povpr_raven"]
bl = bl.sort_values("manjkajoc_obseg", ascending=False)
bl.to_csv(REZ / "diag_a3_blok_izpadi.csv", index=False, encoding="utf-8-sig")

print(f"Blok-izpadov: {len(bl)} pri {bl['vzs_sifra'].nunique()} VZS. "
      "Vecina je v majhnih VZS in za agregat nepomembna.")
print("\n8 obsegovno najvecjih (samo ta lahko premaknejo agregat):")
print(bl.head(8).to_string(index=False))

# ---------------------------------------------------------------- A3, sloj 4
# Ali sta zaznavi v agregatu iz poletja 2024 posledica zgolj teh dveh VZS?
print("\n" + "-" * 78)
print("A3, sloj 4 — robustnost agregata na dva VZS z blok-izpadom")
print("-" * 78)

for oznaka, stolpci in [("vseh 282 VZS", list(sir.columns)),
                        ("brez 2395P in 1264",
                         [c for c in sir.columns if c not in ("2395P", "1264")])]:
    a = sir[stolpci].sum(axis=1)
    dd = a.diff()
    z = robust_z(dd)
    fl = z[z.abs() > PRAG]
    print(f"\n=== agregat cez {oznaka} ({len(stolpci)} VZS), |z| > {PRAG} ===")
    print(pd.DataFrame({"dif": dd[fl.index].round(0),
                        "z": fl.round(1)}).to_string())

# ============================================================== A5
naslov("A5 — uskladitev stevila vrstic panela")

print(f"Vrstic v panelu: {len(panel):,}")
print(f"Tednov: {len(dates)}, razlicnih VZS: {panel['vzs_sifra'].nunique()}")
print(f"Polni pravokotnik {len(dates)} x {panel['vzs_sifra'].nunique()} = "
      f"{len(dates) * panel['vzs_sifra'].nunique():,}")
n_vrstic = po_tednu.set_index("datum")["n_vrstic"]
print("\nPorazdelitev stevila vrstic na teden:",
      n_vrstic.value_counts().sort_index().to_dict())
print("\nTedni, ki odstopajo od najpogostejsega stevila vrstic:")
modus = int(n_vrstic.mode().iloc[0])
odst = n_vrstic[n_vrstic != modus]
print(f"  modus = {modus} vrstic; odstopajocih tednov: {len(odst)}")
print(odst.to_string())
print(f"\nSestevek: {modus} x {(n_vrstic == modus).sum()} + "
      f"{odst.sum()} = {modus * (n_vrstic == modus).sum() + odst.sum():,}")
# podvojene vrstice (ista VZS dvakrat v istem tednu)?
dup = panel.duplicated(["datum", "vzs_sifra"]).sum()
print(f"Podvojenih parov (datum, vzs_sifra): {dup}")

# ============================================================== A6
naslov("A6 — nabor VZS s popolno vrsto, z in brez prizadetih tednov")

# prizadeti tedni: iz A3 (|z| > PRAG po katerem koli merilu)
prizadeti = sorted(set(sum_dif["datum"]) | set(sum_praznih["datum"]))
print("Kandidati za izlocitev (iz A3):",
      [str(pd.Timestamp(d).date()) for d in prizadeti] or "(nobenega)")


def popolni_nabor(izloci) -> set:
    p = panel[~panel["datum"].isin(izloci)]
    n = p["datum"].nunique()
    c = p.groupby("vzs_sifra")[KANON].count()
    return set(c[c == n].index)


osnovni = popolni_nabor([])
print(f"\nPopolna vrsta cez vseh {len(dates)} tednov:            {len(osnovni)} VZS")

for izl in ([pd.Timestamp("2025-06-11")], prizadeti):
    if not izl:
        continue
    nov = popolni_nabor(izl)
    oznaka = ", ".join(str(pd.Timestamp(d).date()) for d in izl)
    print(f"Brez tednov [{oznaka}]: {len(nov)} VZS "
          f"(+{len(nov - osnovni)} novih, -{len(osnovni - nov)})")
    if nov - osnovni:
        nazivi = panel.drop_duplicates("vzs_sifra").set_index("vzs_sifra")["vzs_naziv"]
        dodane = pd.Series({s: nazivi.get(s, "") for s in sorted(nov - osnovni)})
        print("  na novo popolne VZS:")
        print(dodane.to_string())

print("\nGotovo. Izhodi: rezultati/diag_a2_manjkajoci_tedni.csv, "
      "rezultati/diag_a3_tedenska_diagnostika.csv")
