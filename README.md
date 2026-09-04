# Koda diplomske naloge

Programska koda, s katero so bili izdelani rezultati diplomskega dela
**»Uporaba podatkovne analitike za podporo odločanju v servisni dejavnosti«**
(Fakulteta za upravo, Univerza v Ljubljani).

Repozitorij vsebuje izključno tisto, kar je bilo dejansko uporabljeno za
ponazoritve in številke v končni različici naloge. Vsaka slika, grafikon in
tabela iz naloge je v razpredelnici spodaj povezana s skripto, ki jo je
ustvarila.

Naloga obsega dva empirična dela:

1. **Interni podatki podjetja** (mape `01_etl`, `02_podjetje) — dve ploski
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

02_podjetje/             analiza internih podatkov podjetja
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



## Zagon

Zahtevan je Python 3.11.

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```


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

- Uporabljeno je drseče preverjanje
  z rastočim učnim oknom, naključna delitev podatkov ni bila uporabljena.
- Vsak model je primerjan z naivno oziroma sezonsko naivno napovedjo. Brez te
  primerjave absolutna vrednost MAE ne pove ničesar.
- Stolpec `kategorija` (šest kategorij napak) v shemi baze ne obstaja in je
  rekonstruiran iz polja `vrsta_napake`; preslikava in njena kalibracija sta
  dokumentirani v `02_fotona/db_common.py` in v prilogi 1.
- Pri podatkih NIJZ manjkajoči tedni **niso** interpolirani. Učinek te
  odločitve je izmerjen ločeno v `03_nijz/skripte/23_ucinek_interpolacije.py`.


