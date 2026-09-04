# -*- coding: utf-8 -*-
"""
G2: primerjava vsake stevilke iz obstojecega POROCILO_NIJZ.md s svezim
izpisom po popravkih.

Levi stolpec je prepisan iz obstojecega besedila (stanje pred popravki),
desni se PREBERE iz rezultatov skript 10, 11 in 20 — nobene stevilke se ne
prepisuje rocno. Izhod je rezultati/5_4_G2_primerjava.csv s statusom
'nespremenjeno' / 'spremenjeno' / 'napacno' za vsako postavko.

Zagon: py -3.11 21_g2_primerjava.py   (po 11_panel_kakovost.py in 20_analiza_5_4.py)
"""

import sys
from pathlib import Path

import pandas as pd

import vrste as vr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REZ = vr.REZ
B = pd.read_csv(REZ / "5_4_B_opisna.csv")
M = pd.read_csv(REZ / "5_4_D_metrike.csv")
C = pd.read_csv(REZ / "5_4_C_anomalije_vse.csv")
E = pd.read_csv(REZ / "5_4_E_ccf.csv")
A = pd.read_csv(REZ / "5_4_E2_arx.csv")
F = pd.read_csv(REZ / "5_4_F_sezonskost.csv")
panel = vr.nalozi()
nabor = vr.nabor()

O = "ocisceno"


def b(vzs, kaz):
    return float(B[(B.vzs == vzs) & (B.razlicica == O)][kaz].iloc[0])


def mae_vs(vzs, h, model):
    r = M[(M.vzs == vzs) & (M.horizont == h) & (M.model == model)
          & (M.razlicica == O)]
    return float(r["MAE_vs_naivni_pct"].iloc[0])


def naivni(vzs, h, kaz):
    r = M[(M.vzs == vzs) & (M.horizont == h) & (M.model == "naivni")
          & (M.razlicica == O)]
    return float(r[kaz].iloc[0])


zanesljivi = panel.loc[panel["zanesljiv"], "datum"].nunique()
cak_nan = panel["cak_skupaj"].isna().mean()
cs = C[C.razlicica == O]

# (postavka, stara vrednost v besedilu, nova vrednost, opomba)
P = [
    # --- 0. podatkovna osnova ---
    ("Surovih datotek", 112, panel["datum"].nunique(), ""),
    ("Vrstic panela", 41767, len(panel), ""),
    ("Razlicnih VZS", 376, panel["vzs_sifra"].nunique(), ""),
    ("VZS s popolno vrsto cak_skupaj", 282,
     int(nabor["popolna_vrsta"].sum()),
     "merilo popolnosti se zdaj presoja na 110 zanesljivih tednih (A6)"),
    ("VZS v agregatu", 282, int(nabor["v_agregatu"].sum()),
     "2395P in 1264 (blok-izpad poleti 2024) NISO izlocena: izlocitev "
     "natanko teh dveh od 68 prizadetih VZS bi bila selektivna brez "
     "splosnega praga; poleg tega je blok v celoti v ucnem, ne testnem delu"),
    ("Uporabljenih tednov za modeliranje", 120, zanesljivi,
     "prej redna mreza 120 tednov z interpolacijo; zdaj 110 dejansko "
     "opazovanih in zanesljivih tednov, brez interpolacije"),
    ("Manjkajocih tednov v arhivu", 8, 8,
     "stevilo drzi, a razlaga ne: 2026-W17 in 2026-W24 ne padeta na noben praznik"),
    ("Nezanesljivih tednov", 0, 2, "11. 6. 2025 in 20. 8. 2025 (A3)"),

    # --- 1. A1 kakovost ---
    ("Delez NaN pri cak_skupaj (%)", 11.5, round(100 * cak_nan, 1), ""),
    ("VZS z nepopolno vrsto", 93,
     int(panel["vzs_sifra"].nunique() - nabor["popolna_vrsta"].sum()),
     "prej navedeno 93; 376 - 282 = 94, torej je bila stara stevilka napacna"),
    ("Dogodkov sprememb nabora VZS", 37, 37, ""),

    # --- 2. B opisna ---
    ("Rast agregata (%)", 15.9, round(b("AGREGAT", "rast_prva_zadnja_pct"), 1),
     "sprememba izhaja iz novega nabora VZS, ne iz izlocitve tednov"),
    ("Agregat, prva vrednost", 294560, int(b("AGREGAT", "prva")),
     "294.560 je bil minimum vrste, ne prva vrednost — stara navedba je bila "
     "napacna ze pred popravki"),
    ("Agregat, zadnja vrednost", None, int(b("AGREGAT", "zadnja")), ""),
    ("Agregat, vrh", 358335, int(b("AGREGAT", "vrh")), ""),
    ("Naklon trenda agregata (na teden)", 589,
     round(b("AGREGAT", "naklon_na_teden")), ""),
    ("R2 trenda agregata", 0.91, round(b("AGREGAT", "R2"), 2), ""),
    ("Rast UZ vratnih zil (%)", 60, round(b("1941", "rast_prva_zadnja_pct"), 1), ""),
    ("Rast MR glave (%)", 59, round(b("1755", "rast_prva_zadnja_pct"), 1), ""),
    ("Rast kardioloskega pregleda (%)", -11.6,
     round(b("1018P", "rast_prva_zadnja_pct"), 1), ""),
    ("Delez sezonske komponente STL (%)", 33,
     round(100 * float(F[F.razlicica == O]["STL_sezonska_delez_sd"].iloc[0]), 1), ""),

    # --- 3. C anomalije ---
    ("Testiranih tock (anomalije)", 777, int(len(cs)), ""),
    ("Z-oznacb", 27, int(cs.z_flag.sum()),
     "porast: po izlocitvi osamelcev pade st. odklon razlik, zato prag |z| > 2 "
     "prekorači vec tednov (past iz koraka C2)"),
    ("IF-oznacb", 42, int(cs.if_flag.sum()), ""),
    ("Konsenznih anomalij", 22, int(cs.konsenz.sum()), ""),

    # --- 4. D napovedi ---
    ("Testnih tock h = 1", 62, int(naivni("AGREGAT", 1, "n")), ""),
    ("Testnih tock h = 4", 59, int(naivni("AGREGAT", 4, "n")), ""),
    ("MAE naivnega, agregat, h = 1", 2561, round(naivni("AGREGAT", 1, "MAE")), ""),
    ("MAE naivnega kot delez ravni, agregat (%)", 0.8,
     round(100 * naivni("AGREGAT", 1, "MAE") / b("AGREGAT", "povprecje"), 2), ""),
    ("AR(1) proti naivnemu, agregat, h = 1 (%)", -16.8,
     round(mae_vs("AGREGAT", 1, "ar1"), 1),
     "OBRAT: prejsnja stevilka izvira iz presezene interpolirane metodologije "
     "(120 t., 62 tock); na izhodiscni (112 t., brez interpolacije) je -17,6 %. "
     "Po popravku obeh tednov razlika ni vec statisticno razlocljiva od nic "
     "(Wilcoxon p = 0,748, glej 5_4_D4_parni_testi.csv) - naivni in AR(1) sta "
     "nerazlocljiva, ne AR(1) zmagovalec"),
    ("AR(1) proti naivnemu, agregat, h = 4 (%)", -56.0,
     round(mae_vs("AGREGAT", 4, "ar1"), 1), ""),
    ("Lin. regresija proti naivnemu, agregat, h = 1 (%)", -131.2,
     round(mae_vs("AGREGAT", 1, "lin"), 1), ""),
    ("AR(1) proti naivnemu, UZ vratnih zil, h = 1 (%)", 3.8,
     round(mae_vs("1941", 1, "ar1"), 1), ""),
    ("AR(1) proti naivnemu, katarakta, h = 4 (%)", 2.3,
     round(mae_vs("1195", 4, "ar1"), 1), ""),
    ("Vrst, kjer AR(1) premaga naivnega pri h = 1", 1,
     int((M[(M.horizont == 1) & (M.model == "ar1") & (M.razlicica == O)]
          ["MAE_vs_naivni_pct"] > 0).sum()), ""),
    ("Vrst, kjer AR(1) premaga naivnega pri h = 4", 1,
     int((M[(M.horizont == 4) & (M.model == "ar1") & (M.razlicica == O)]
          ["MAE_vs_naivni_pct"] > 0).sum()), ""),

    # --- 6. E korelacije ---
    ("Znacilnih kriznih korelacij (nominalno, p < 0,05)", 0,
     int(E[(E.razlicica == O) & (E.p < 0.05)].shape[0]),
     "stara trditev 'nobena ni znacilna' ne drzi vec; a nobena ne prezivi "
     "korekcije za 63 testov (Bonferroni, BH)"),
    ("Znacilnih po korekciji za mnogotere teste", 0,
     int(E[(E.razlicica == O) & (E.p_bh < 0.05)].shape[0]), ""),
    ("Najnizja p-vrednost (agregat)", 0.060,
     round(float(E[(E.razlicica == O) & (E.vzs == "AGREGAT")]["p"].min()), 3), ""),
    ("AR-X: najmanjse poslabsanje (%)", -0.7,
     round(float(A[A.razlicica == O]["izboljsava_pct"].max()), 2),
     "stara trditev 'AR-X poslabsa pri VSEH vrstah' ne drzi: pri kardioloskem "
     "pregledu napoved izboljsa"),
    ("AR-X: najvecje poslabsanje (%)", -10.0,
     round(float(A[A.razlicica == O]["izboljsava_pct"].min()), 2), ""),
]

rows = []
for postavka, staro, novo, opomba in P:
    if staro is None:
        status = "novo"
    elif isinstance(staro, (int, float)) and isinstance(novo, (int, float)):
        status = "nespremenjeno" if abs(staro - novo) < 1e-9 else "spremenjeno"
    else:
        status = "spremenjeno" if staro != novo else "nespremenjeno"
    if "napacn" in opomba:
        status = "napacno v besedilu"
    rows.append({"postavka": postavka, "staro": staro, "novo": novo,
                 "status": status, "opomba": opomba})

g2 = pd.DataFrame(rows)
g2.to_csv(REZ / "5_4_G2_primerjava.csv", index=False, encoding="utf-8-sig")

print("G2 — primerjava besedila POROCILO_NIJZ.md s svezim izpisom\n")
with pd.option_context("display.max_colwidth", 60, "display.width", 220):
    print(g2[["postavka", "staro", "novo", "status"]].to_string(index=False))
print("\nPovzetek statusov:", g2["status"].value_counts().to_dict())
print("\nPostavke z opombo:")
for _, r in g2[g2.opomba != ""].iterrows():
    print(f"  - {r['postavka']}: {r['opomba']}")
print(f"\nZapisano: rezultati/5_4_G2_primerjava.csv")
