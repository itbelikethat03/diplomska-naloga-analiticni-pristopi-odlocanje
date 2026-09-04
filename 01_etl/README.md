# 01 — ETL in podatkovna baza

Cevovod, ki iz dveh ploskih izvozov CSV sestavi normalizirano bazo MySQL
`servis_db` (poglavji 4.1 in 4.2 naloge).

| Datoteka | Namen |
|---|---|
| `etl_servis.py` | celoten cevovod ETL: branje, čiščenje, standardizacija, razčlemba večvrednostnih celic, nalaganje 24 tabel, indeksi, tuji ključi, kontrolni izpis |
| `schema_servis_db.sql` | shema baze (DDL): tabele po odvisnostih, tuji ključi, indeksi in pogleda `v_drzave_analiza` in `v_reklamacije_po_drzave` |
| `servisni_proces.drawio` | izvorna datoteka diagrama EPC servisnega procesa (slika 2) |
| `poizvedbe/ekstrahiraj_podatke.py` | poizvedbe SQL, ki dajo opisne številke poglavja 5.1 (obseg, zanesljivost, načini prejema, časi reševanja) |

## Varstvo osebnih podatkov

Objavljena je **psevdonimizirana različica** cevovoda. Tabela `tuji_kontakt`
dobi le sintetični identifikator (`Kontakt_<id>`), imena, elektronski naslovi
in telefonske številke kontaktnih oseb pa se v bazo ne zapišejo — preslikava
obstaja samo v pomnilniku med izvajanjem skripte. Tako baza ne vsebuje
osebnih podatkov, skladno z načelom najmanjšega obsega iz člena 5(1)(c)
Splošne uredbe o varstvu podatkov.

## Zagon

```bash
mysql -u root -p -e "CREATE DATABASE servis_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
py -3.11 etl_servis.py
```

Skripta pričakuje datoteki `pregled_servisnih_posegov.csv` in
`pregled_reklamacij.csv` (kodiranje cp1250, ločilo `;`) v mapi `podatki/` v
korenu repozitorija oziroma v mapi, ki jo določa spremenljivka okolja
`SERVIS_CSV_DIR`. **Datoteki nista del te objave** — gre za interne izvoze
podjetja.

Poverilnice za bazo se berejo iz `.env` v korenu repozitorija.

## Kontrola kakovosti (poglavje 4.1.4)

Cevovod po nalaganju izpiše ugotovljene nepopolnosti, ki so v nalogi
namenoma **ohranjene v izvornem stanju** in ne popravljene:

- 871 od 4.078 servisnih posegov (21,4 %) nima povezave z nobeno reklamacijo
  (preventivno vzdrževanje, nadgradnje),
- 964 od 11.039 reklamacij (8,7 %) nima zapisa o zaključku,
- 280 reklamacij (2,5 %) nima zapisa v `analiza_reklamacije`,
- polje za količino v `servisni_poseg_postavka` ostane besedilno, ker v
  izvornih podatkih vsebuje tudi ne-numerične zapise.
