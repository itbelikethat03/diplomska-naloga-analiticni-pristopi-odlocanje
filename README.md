# Koda diplomske naloge

Programska koda, s katero so bili izdelani rezultati diplomskega dela
**»Uporaba podatkovne analitike za podporo odločanju v servisni dejavnosti«**
(Fakulteta za upravo, Univerza v Ljubljani).

Repozitorij vsebuje izključno tisto, kar je bilo dejansko uporabljeno za
ponazoritve in številke v končni različici naloge. Vsaka slika, grafikon in
tabela iz naloge je v razpredelnici spodaj povezana s skripto, ki jo je
ustvarila.

Naloga obsega dva empirična dela:

1. **Interni podatki podjetja** (mape `01_etl`, `02_fotona`) — dve ploski
   razpredelnici iz internega sistema sta bili s cevovodom ETL preneseni v
   normalizirano bazo MySQL (24 tabel, 124.741 zapisov), nad njo pa so bile
   izvedene opisna analiza, nadzorna plošča in napovedni modeli.
2. **Javni podatki NIJZ o čakalnih dobah** (mapa `03_nijz`) — primerjalni
   preizkus prenosljivosti istega analitičnega pristopa na javno domeno
   (raziskovalno vprašanje RV4). Brez baze, vse v datotekah.

## Kaj v repozitoriju NI

- **Izvorna izvoza CSV iz internega sistema podjetja** in **baza `servis_db`**.
  Gre za poslovno občutljive podatke, za katere je bilo dano soglasje za
  uporabo v nalogi, ne pa za javno objavo. Skripte iz mape `02_fotona` se
  zato brez lokalne baze ne izvedejo; njihovi izhodi so priloženi v
  `02_fotona/rezultati/`.
- **Datoteka Power BI (`.pbix`)**, ker vsebuje predpomnjeno kopijo podatkov.
  Zasnova nadzorne plošče je dokumentirana v poglavju 5.2 naloge, zaslonske
  slike so v `slike_v_nalogi/`.
- **Dejanska imena trgov in družin izdelkov.** Naloga jih prikazuje
  anonimizirano (»Trg 1«, »Naprava A«); preslikavi v
  `02_fotona/opisna/anonimizacija_drzav.py` in `anonimizacija_druzin.py` sta
  zato v javni objavi prazni. Objava bi anonimizacijo v nalogi izničila.
- **Slika 1** iz naloge (cikel vrednosti podatkov), ker je povzeta po
  van Ooijen idr. (2019) in ni lastno delo.
- **Surova poročila NIJZ** (112 datotek .xlsx, ~200 MB). Prenesejo se s
  skripto `03_nijz/skripte/01_prenos_porocil.py`; sestavljen panel je
  priložen kot `03_nijz/data/panel_vzs.parquet`.

## Struktura

```
01_etl/                cevovod ETL in shema baze servis_db
  etl_servis.py            CSV -> 24 normaliziranih tabel v MySQL
  schema_servis_db.sql     shema baze (DDL, tuji ključi, pogleda SQL)
  servisni_proces.drawio   izvorna datoteka diagrama servisnega procesa
  poizvedbe/               poizvedbe SQL za opisne številke poglavja 5.1

02_fotona/             analiza internih podatkov podjetja
  db_common.py             povezava na bazo + rekonstrukcija stolpca kategorija
  opisna/                  grafikoni 1-5 (poglavje 5.1)
  napovedni/               napovedni modeli in detekcija anomalij (poglavje 5.3)
  rezultati/               izhodne datoteke CSV in PNG teh skript

03_nijz/               analiza javnih podatkov o čakalnih dobah (poglavje 5.4)
  skripte/                 01-11 priprava in diagnostika, 20-24 končna analiza
  data/                    sestavljen panel (parquet) in pomožne razpredelnice
  rezultati/               vse izračunane številke poglavja 5.4 (CSV)
  visualizations/          grafi analize NIJZ (v nalogi niso objavljeni)

04_priloge/            skripta in podatki za sestavo dokumenta Priloge.docx
docs/                  tehnični poročili o obeh analizah
slike_v_nalogi/        ponazoritve, kot so natisnjene v nalogi
```

## Ponazoritve v nalogi in njihov izvor

| Ponazoritev | Poglavje | Nastala z |
|---|---|---|
| Slika 1: Cikel vrednosti podatkov | 2.2.2 | tuji vir (van Ooijen idr., 2019) — ni v repozitoriju |
| Slika 2: Potek servisnega procesa | 3.1 | `01_etl/servisni_proces.drawio` (diagram EPC, draw.io) |
| Slika 3: Logični podatkovni model | 4.1.3 | obratni inženiring sheme v MySQL Workbench (`01_etl/schema_servis_db.sql`) |
| Grafikon 1: Porazdelitev po vrstah reklamacije | 5.1.1 | `02_fotona/opisna/porazdelitev_reklamacij.py` |
| Grafikon 2: Porazdelitev po družini izdelkov | 5.1.2 | `02_fotona/opisna/porazdelitev_reklamacij_po_druzini.py` |
| Grafikon 3: Reklamacije skozi leta | 5.1.4 | `02_fotona/opisna/graf_reklamacije_leta.py` |
| Grafikon 4: Servisni posegi skozi leta | 5.1.4 | `02_fotona/opisna/trend_servisnih_posegov.py` |
| Grafikon 5: Razpršenost po trgih | 5.1.5 | `02_fotona/opisna/porazdelitev_servisnih_posegov_po_drzavi_anonimizirano.py` |
| Slika 4: Preslikava podatkovne sheme | 5.2.2 | pogled modela v Power BI |
| Slike 5-7: Strani nadzorne plošče | 5.2.3 | Power BI nad bazo `servis_db` |
| Tabela 1 in grafikon 6: Drseče preverjanje po kategorijah | 5.3.2 | `02_fotona/napovedni/backtest_kategorije.py` |
| Tabela 2: Modeli z eksternimi prediktorji | 5.3.3 | `02_fotona/napovedni/backtest_kategorije_multivariant.py`, `koleracije_posegi_reklamacijami.py` |
| Tabela 3: Mesečni napovedni modeli | 5.3.4 | `02_fotona/napovedni/posegi_reklamacije_mesecno.py` |
| Grafikona 7 in 8: Detekcija anomalij | 5.3.5 | `02_fotona/napovedni/anomaly_detection.py` |
| Tabela 4 in grafikon 9: Napoved časa reševanja | 5.3.6 | `02_fotona/napovedni/fotona_solution_time.py` |
| Tabela 5: Merila za nezanesljive tedne | 5.4.1 | `03_nijz/skripte/10_diagnostika_kakovosti.py`, `11_panel_kakovost.py` |
| Tabela 6: Sprememba MAE proti naivnemu modelu | 5.4.2 | `03_nijz/skripte/20_analiza_5_4.py` |
| Priloge 1-5 | priloge | `04_priloge/gradi_docx.py` |

Grafikona 7 in 8 sta v nalogi objavljena kot izrezka zgornjih dveh polj
skupne slike `02_fotona/rezultati/fotona_anomaly_detection.png`.

## Zagon

Zahtevan je Python 3.11.

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Del s podatki podjetja

Potrebna je lokalna baza MySQL. Poverilnice se berejo iz datoteke `.env` v
korenu repozitorija (predloga je `.env.example`); v kodi niso zapisane.

```bash
mysql -u root -p -e "CREATE DATABASE servis_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
py -3.11 01_etl/etl_servis.py          # zahteva izvorna CSV, ki nista objavljena
```

Skripte v `02_fotona/` izhodne datoteke zapisujejo v delovno mapo, zato se
poganjajo iz mape `02_fotona/rezultati/`:

```bash
cd 02_fotona/rezultati
py -3.11 ../napovedni/backtest_kategorije.py
```

Skripte v `02_fotona/opisna/` pot izhoda določijo same in se lahko poženejo
od koderkoli.

### Del s podatki NIJZ

Deluje brez baze in brez dostopa do podatkov podjetja. Priložen panel
zadošča za ponovitev vseh številk poglavja 5.4:

```bash
cd 03_nijz
py -3.11 skripte/20_analiza_5_4.py     # vse številke poglavja 5.4
py -3.11 skripte/21_g2_primerjava.py   # primerjava s prejšnjo različico
```

Za popolno ponovitev od začetka (prenos 112 poročil z arhivske strani NIJZ,
nato sestava panela):

```bash
py -3.11 skripte/01_prenos_porocil.py
py -3.11 skripte/02_preverba_strukture.py
py -3.11 skripte/03_sestava_panela.py
py -3.11 skripte/10_diagnostika_kakovosti.py
py -3.11 skripte/11_panel_kakovost.py
```

Podrobnosti o zaporedju skript in o tem, katera različica analize je
merodajna, so v `03_nijz/README.md`.

## Metodološke opombe

- Vrednotenje je povsod časovno pravilno: uporabljeno je drseče preverjanje
  z rastočim učnim oknom, naključna delitev podatkov ni bila uporabljena.
- Vsak model je primerjan z naivno oziroma sezonsko naivno napovedjo. Brez te
  primerjave absolutna vrednost MAE ne pove ničesar.
- Stolpec `kategorija` (šest kategorij napak) v shemi baze ne obstaja in je
  rekonstruiran iz polja `vrsta_napake`; preslikava in njena kalibracija sta
  dokumentirani v `02_fotona/db_common.py` in v prilogi 1.
- Pri podatkih NIJZ manjkajoči tedni **niso** interpolirani. Učinek te
  odločitve je izmerjen ločeno v `03_nijz/skripte/23_ucinek_interpolacije.py`.

## Licenca in uporaba

Koda je objavljena za namen preverljivosti diplomskega dela. Podatki podjetja
so bili uporabljeni na podlagi pisnega soglasja in niso del te objave.
