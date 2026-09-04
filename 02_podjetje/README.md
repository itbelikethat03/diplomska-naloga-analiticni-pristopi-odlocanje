# 02 — Analiza internih podatkov podjetja

Opisna analiza (poglavje 5.1) in napovedno modeliranje (poglavje 5.3) nad
bazo `servis_db`. Vse skripte berejo iz baze in vanjo ne pišejo.

## Povezava na bazo

`db_common.py` bere poverilnice iz `../.env` in vrne pripravljen
SQLAlchemy engine (gonilnik PyMySQL). Poleg tega definira podpoizvedbo
`ANALIZA_REKLAMACIJE_KAT`, ki tabeli `analiza_reklamacije` doda
rekonstruiran stolpec `kategorija`.

**Zakaj rekonstrukcija:** shema baze šestih kategorij napak ne hrani kot
samostojnega atributa. Pri zapisih od leta 2019 je kategorija prefiks polja
`vrsta_napake` pred značko `<br>`, pri starejših zapisih (2013–2019) pa je
zapisana le prosto oblikovana oznaka (30 različnih, na primer »okvara
ročnika«). Preslikava starih oznak je kalibrirana proti zgodovinskim
rezultatom in se za leta 2017, 2018 in 2019 ujema na reklamacijo natančno.
Celoten seznam preslikav je v prilogi 1 naloge
(`../04_priloge/priloga1_preslikava_tipov_napak.csv`).

## `opisna/` — grafikoni 1–5

| Skripta | Ponazoritev |
|---|---|
| `porazdelitev_reklamacij.py` | grafikon 1 — vrste reklamacij |
| `porazdelitev_reklamacij_po_druzini.py` | grafikon 2 — družine izdelkov |
| `graf_reklamacije_leta.py` | grafikon 3 — reklamacije 2013–2025 |
| `trend_servisnih_posegov.py` | grafikon 4 — servisni posegi 2020–2025 |
| `porazdelitev_servisnih_posegov_po_drzavi_anonimizirano.py` | grafikon 5 — trgi |
| `anonimizacija_druzin.py`, `anonimizacija_drzav.py` | fiksni preslikavi v anonimne oznake |

Obe preslikavi sta v javni objavi **prazni**: naloga trge in družine
izdelkov prikazuje anonimizirano, objava dejanskih imen pa bi to
anonimizacijo izničila. Funkciji `anonimiziraj_drzavo()` in
`anonimiziraj_druzino()` ob praznem slovarju oznake dodelita sami, po
padajočem deležu, kar da isti vrstni red kot v nalogi.

## `napovedni/` — poglavje 5.3

| Skripta | Rezultat v nalogi | Izhodi |
|---|---|---|
| `backtest_kategorije.py` | tabela 1, grafikon 6 | `fotona_backtest_kategorije.{csv,png}`, `fotona_backtest_skupna_napaka.png` |
| `backtest_kategorije_multivariant.py` | tabela 2 | `fotona_backtest_final.{csv,png}` |
| `koleracije_posegi_reklamacijami.py` | poglavje 5.3.3 | `fotona_backtest_svc_clean.{csv,png}` |
| `posegi_reklamacije_mesecno.py` | tabela 3 | `fotona_posegi_reklamacije_mesecno.{csv,png}` |
| `anomaly_detection.py` | grafikona 7 in 8 | `fotona_anomalije.csv`, `fotona_anomaly_detection.png` |
| `fotona_solution_time.py` | tabela 4, grafikon 9 | `fotona_napoved_casi.csv`, `fotona_casi_model.png`, `fotona_casi_intervali_2025.png` |

Skripte pišejo v delovno mapo, zato jih poganjajte iz `rezultati/`:

```bash
cd rezultati
py -3.11 ../napovedni/backtest_kategorije.py
```

## Metodološka izhodišča

- Časovne vrste so omejene na zaključena obdobja do decembra 2024, ker leto
  2025 ob izvozu ni bilo zaključeno. Izjema je `fotona_solution_time.py`, ki
  ne napoveduje časovne vrste, temveč trajanje posamezne reklamacije, in
  zato vključuje tudi zapise iz leta 2025.
- Povsod je uporabljeno drseče preverjanje z rastočim učnim oknom; naključna
  delitev bi v učno množico spustila opazovanja, ki testnim sledijo v času.
- Vsak model je primerjan z naivno napovedjo (letno) oziroma tudi s sezonsko
  naivno (mesečno).
- Pri kategorijah je treba upoštevati spremembo šifranta leta 2019: nobena
  od 30 starih prostih oznak se po tem letu ne pojavi več in nobena
  strukturirana pred njim, zato letne vrste čez to mejo niso povsem
  primerljive. Najbolj to velja za kategoriji »ni tehnična napaka« in
  »enota za sprej«.

Podrobno tehnično poročilo: `../docs/POROCILO_ML.md`.
