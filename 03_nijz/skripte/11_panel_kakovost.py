# -*- coding: utf-8 -*-
"""
Podatkovni sloj za popravljeno poglavje 5.4 (koraki A1, A4, A6).

A1  Kanonicna mera stevila cakajocih je EN sam stolpec, cak_skupaj.
    Diagnostika 10_diagnostika_kakovosti.py je pokazala, da je ta stolpec
    v vseh 36.946 vrsticah, kjer sta definirana oba, natanko enak vsoti
    treh stopenj nujnosti; sestevanje vec stolpcev hkrati (cak_* + nad_*)
    isto kolicino steje veckrat in se nikjer ne uporablja.

A4  Zastavica kakovosti namesto brisanja: surovi panel ostane nedotaknjen,
    doda se stolpec 'zanesljiv' (in 'razlog_oznake'). Interpolacije ni —
    neopazovani in neveljavni tedni preprosto niso del vrste za modeliranje.

A6  Nabor VZS s popolno vrsto se doloci NA ZANESLJIVIH TEDNIH (ne na vseh),
    zato se spremeni z 282 na 292. Agregat se racuna cez vseh 292 — VZS z
    veclednim blok-izpadom poleti 2024 (2395P, 1264) se NE izlocata.

    Odlocitev (revidirano): blok-izpad je le eden od 149 tovrstnih blokov
    pri 68 VZS (glej diag_a3_blok_izpadi.csv); izlocitev natanko teh dveh
    brez splosnega praga za "dovolj velik blok" bi bila selektivna in bi
    ponovila isto krozno logiko kot pri prvotni obravnavi 20. 8. 2025.
    Dodatna kontrola: prvo ucno okno walk-forward zajame tedne #1-52, prva
    testna tocka pa je teden #53 (16. 4. 2025 pri h=1); blok (tedna #16-21,
    jul.-avg. 2024) je torej v celoti v ucnem delu in nikoli sam ne nastopi
    kot ocenjevana napoved — vpliva lahko kvecjemu na oceno parametrov, ne
    na izmerjeno MAE. To je bistveno sibkejsi kanal vpliva kot pri 11. 6.
    in 20. 8., kjer je bil prizadeti teden neposredno testna tocka. Blok
    ostaja v podatkih kot ilustracija, da detekcija anomalij na ravni
    posamezne VZS deluje (glej 6.2.3), ne kot razlog za izlocitev.

Izhoda: data/panel_kakovost.parquet, data/nabor_vzs.csv
"""

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

KANON = "cak_skupaj"

# --- A4: tedni, oznaceni kot nezanesljivi (izid koraka A3) -------------------
# Merilo: mediana relativne spremembe cez uravnotezen nabor VZS odstopa za
# velikostni red od ozadja (ozadje |mediana| <= 0,85 %), padec se v naslednjem
# tednu v veliki meri povrne -> gre za izpad porocanja, ne za dinamiko procesa.
NEZANESLJIVI = {
    pd.Timestamp("2025-06-11"):
        "sistemski izpad porocanja ob spremembi formata (27 -> 30 stolpcev); "
        "mediana rel. spremembe -10,0 %, 61 % VZS s padcem > 5 %, "
        "95 % padca povrnjenega naslednji teden",
    pd.Timestamp("2025-08-20"):
        "izpad porocanja brez spremembe formata, koncentriran v slikovni "
        "diagnostiki; mediana rel. spremembe -2,1 %, 36 % VZS s padcem > 5 %, "
        "82 % padca povrnjenega naslednji teden",
}

# --- A3, sloj 3: VZS z veclednim blok-izpadom poleti 2024 (informativno,
# NISO izloceni iz agregata — glej utemeljitev v uvodnem komentarju) ---------
BLOK_IZPAD_INFO = {
    "2395P": "blok-izpad 18. 7. – 22. 8. 2024 (raven ~9.400 namesto ~18.800)",
    "1264": "blok-izpad 25. 7. – 22. 8. 2024 (raven ~590 namesto ~1.860)",
}


def main() -> None:
    panel = pd.read_parquet(DATA / "panel_vzs.parquet")

    # ---------------------------------------------------------------- A4
    panel["zanesljiv"] = ~panel["datum"].isin(NEZANESLJIVI)
    panel["razlog_oznake"] = panel["datum"].map(NEZANESLJIVI).fillna("")

    zan = panel.loc[panel["zanesljiv"], "datum"].nunique()
    print(f"A4  tednov skupaj: {panel['datum'].nunique()}, "
          f"zanesljivih: {zan}, oznacenih kot nezanesljivi: "
          f"{len(NEZANESLJIVI)}")
    for d, r in NEZANESLJIVI.items():
        print(f"    {d.date()}: {r}")

    # ---------------------------------------------------------------- A6
    zanesljiv = panel[panel["zanesljiv"]]
    n_zan = zanesljiv["datum"].nunique()
    cnt = zanesljiv.groupby("vzs_sifra")[KANON].count()
    popolni = sorted(cnt[cnt == n_zan].index)

    # primerjava s starim merilom (cez vseh 112 tednov)
    cnt_vsi = panel.groupby("vzs_sifra")[KANON].count()
    popolni_stari = sorted(cnt_vsi[cnt_vsi == panel["datum"].nunique()].index)

    print(f"\nA6  popolna vrsta cez vseh {panel['datum'].nunique()} tednov: "
          f"{len(popolni_stari)} VZS   (staro merilo)")
    print(f"    popolna vrsta cez {n_zan} zanesljivih tednov: "
          f"{len(popolni)} VZS   (novo merilo)")
    print(f"    razlika: +{len(set(popolni) - set(popolni_stari))} / "
          f"-{len(set(popolni_stari) - set(popolni))}")

    # agregat = vseh 292 popolnih VZS; blok-izpad se NE izloca (glej zgoraj)
    v_agregatu = popolni
    print(f"    nabor za AGREGAT: {len(v_agregatu)} VZS "
          f"(blok-izpad 2395P/1264 ni izlocen — glej utemeljitev v modulu)")

    # ------------------------------------------- kontrola: kdaj blok pade v walk-forward
    sir = (zanesljiv[zanesljiv["vzs_sifra"].isin(v_agregatu)]
           .pivot_table(index="datum", columns="vzs_sifra", values=KANON))
    rm = sir.rolling(11, center=True, min_periods=5).median()
    dev = (sir - rm) / rm
    obseg = ((rm - sir)[dev < -0.25]).max()
    velik = obseg[obseg > 500].sort_values(ascending=False)
    print(f"\n    kontrola: VZS v agregatu z blok-odklonom > 500 cakajocih: "
          f"{len(velik)} (149 blokov pri 68 VZS skupno, glej diag_a3_blok_izpadi.csv)")
    if len(velik):
        print(velik.round(0).to_string())
    idx_ag = sorted(sir.index)
    MIN_TRAIN = 52
    print(f"    prvo ucno okno: tedni #1-{MIN_TRAIN}, prva testna tocka (h=1): "
          f"teden #{MIN_TRAIN + 1} = {idx_ag[MIN_TRAIN].date()}")
    print("    blok 2395P/1264 (tedna #16-21, jul.-avg. 2024) je torej v celoti "
          "v ucnem delu, nikoli testna tocka")

    # ------------------------------------------------------------- izhoda
    nazivi = (panel.sort_values("datum").drop_duplicates("vzs_sifra", keep="last")
              .set_index("vzs_sifra")["vzs_naziv"])
    nabor = pd.DataFrame({"vzs_sifra": sorted(cnt.index)})
    nabor["vzs_naziv"] = nabor["vzs_sifra"].map(nazivi)
    nabor["n_zanesljivih_tednov"] = nabor["vzs_sifra"].map(cnt)
    nabor["popolna_vrsta"] = nabor["vzs_sifra"].isin(popolni)
    nabor["v_agregatu"] = nabor["vzs_sifra"].isin(v_agregatu)
    nabor["opomba"] = nabor["vzs_sifra"].map(BLOK_IZPAD_INFO).fillna("")
    nabor.to_csv(DATA / "nabor_vzs.csv", index=False, encoding="utf-8-sig")

    panel.to_parquet(DATA / "panel_kakovost.parquet", index=False)
    print(f"\nZapisano: data/panel_kakovost.parquet ({len(panel):,} vrstic, "
          f"{panel.shape[1]} stolpcev), data/nabor_vzs.csv")


if __name__ == "__main__":
    main()
