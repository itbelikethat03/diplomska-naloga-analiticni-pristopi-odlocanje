# Analiza čakalnih dob NIJZ (faza 2)

Del diplomske naloge — primerjalni test prenosljivosti analitičnega pristopa,
razvitega na podatkih Fotone, na javne zdravstvene podatke (RV4).

## Podatki

- **Vir:** tedenska poročila NIJZ »Izpis stanja ČD in čakajočih po VZS«,
  https://nijz.si/podatki/cakalne-dobe/tedenska-porocila-o-cakalnih-dobah/
- **Arhiv:** `data/raw/` — 112 surovih .xlsx datotek (4. 4. 2024 – 15. 7. 2026).
  Surove datoteke se nikoli ne spreminjajo ali prepisujejo. **Zaradi
  velikosti (~200 MB) niso del repozitorija** — prenesejo se s skripto
  `skripte/01_prenos_porocil.py`. Sestavljen panel je priložen, zato
  prenos za ponovitev poglavja 5.4 ni potreben.
- **Panel:** `data/panel_vzs.parquet` — 41.767 vrstic
  (112 tednov × ~373 VZS), sestavljen iz listov »Tb 01« (nacionalni agregat
  po VZS). En zapis = stanje ene vrste zdravstvene storitve (VZS) na presečni
  dan, s čakalno dobo na prvi prosti termin in številom čakajočih po stopnjah
  nujnosti (zelo hitro / hitro / redno).

## Skripte (zaporedje izvajanja)

| Skripta | Namen |
|---|---|
| `skripte/01_prenos_porocil.py` | prenos vseh .xlsx z arhivske strani NIJZ (ponovitve, brez prepisovanja) |
| `skripte/02_preverba_strukture.py` | preverba predpostavk o strukturi (listi, glave, spremembe formata) → `data/struktura_pregled.csv` |
| `skripte/03_sestava_panela.py` | sestava panela teden × VZS → `data/panel_vzs.parquet` |
| `skripte/04_a1_kakovost.py` | A1: kakovost, pokritost, spremembe nabora VZS, izbor storitev |
| `skripte/05_a2_a3_opisna_sezonskost.py` | A2–A3: opisna statistika, trendi, sezonskost |
| `skripte/06_a4_anomalije.py` | A4: detekcija anomalij (konsenz Z-score + Isolation Forest) |
| `skripte/07_a5_napovedi.py` | A5: walk-forward primerjava modelov (naivni, linearna regresija, AR(1)) |
| `skripte/08_a6_intervali.py` | A6: kvantilni intervali in pokritost |
| `skripte/09_a7_zamiki.py` | A7: križne korelacije čakajoči ↔ čakalna doba |

### Popravljena veja (poglavje 5.4)

Skripte 04–09 so prva različica analize. Po reviziji kakovosti podatkov jih
nadomešča spodnje zaporedje; rezultati poglavja 5.4 izhajajo izključno iz njega.

| Skripta | Namen |
|---|---|
| `skripte/10_diagnostika_kakovosti.py` | A1–A3, A5–A6: kanonični stolpec, koledar tednov, iskanje vseh prizadetih tednov, uskladitev vrstic |
| `skripte/11_panel_kakovost.py` | A4: zastavica kakovosti tedna in nabori VZS → `data/panel_kakovost.parquet`, `data/nabor_vzs.csv` |
| `skripte/vrste.py` | skupni modul: sestava vrst brez interpolacije, obravnava vrzeli (D2) |
| `skripte/20_analiza_5_4.py` | B–F: vse številke poglavja 5.4 v eni izvedbi, vsaka v različici »polna« in »očiščeno« |
| `skripte/21_g2_primerjava.py` | G2: primerjava vsake številke iz `POROCILO_NIJZ.md` s svežim izpisom |

Osrednji izhod je `rezultati/5_4_povzetek.csv` (vse številke poglavja) in
`rezultati/5_4_G2_primerjava.csv` (staro proti novemu).

Rezultati analiz: `rezultati/` (CSV) in `visualizations/` (PNG).
Sinteza A8 in celotno tehnično poročilo: `../docs/POROCILO_NIJZ.md`
(**opozorilo:** poročilo je iz stanja pred popravki; merodajni so izhodi
skript 10, 11, 20 in 21).

## Okolje

Python 3.11 (`py -3.11`), pandas, openpyxl, pyarrow, statsmodels,
scikit-learn, matplotlib. Brez baze — vsi podatki v datotekah (zahteva
»samo Python«).

## Ključne strukturne ugotovitve (korak 2)

- Format .xlsx se je spreminjal **aditivno**: 23 stolpcev (april 2024) →
  25 → 27 (dodani preklici, jan. 2025) → 30 (dodana realizirana ČD,
  jun. 2025) → 32 (feb. 2026, enkratno). Jedrni stolpci (ČD na prvi prosti
  termin, število čakajočih po nujnosti) so prisotni v vseh 112 datotekah.
- Kazalnik čakalne dobe = povprečna ČD **na prvi prosti termin** (v dnevih);
  od jun. 2025 dodatno povprečna realizirana ČD zadnjih 7 dni.
- **8** tednov v arhivu manjka (koledar po ISO tednih, ker dan objave niha
  med sredo in četrtkom; razmiki 14–21 dni). Šest izpadov sovpada s prazniki,
  dva (2026-W17, 2026-W24) ne.
- 376 različnih VZS; 367–375 na teden (nabor se skozi čas krči, zato
  41.767 vrstic in ne 112 × 376).
- **292** VZS s popolno vrsto števila čakajočih, merjeno na 110 zanesljivih
  tednih; agregat se računa čez 290 (brez 2395P in 1264, ki imata poleti
  2024 večtedenski blok-izpad).
- **Dva tedna sta označena kot nezanesljiva:** 11. 6. 2025 (sistemski izpad
  ob spremembi formata) in 20. 8. 2025 (izpad v slikovni diagnostiki).
  Surovi podatki ostanejo nedotaknjeni; izločena sta samo iz modeliranja.
