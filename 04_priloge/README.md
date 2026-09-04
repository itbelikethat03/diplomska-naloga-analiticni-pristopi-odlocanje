# 04 — Priloge

Podatki in skripta, s katero je bil sestavljen dokument `Priloge.docx`,
priložen diplomski nalogi.

| Datoteka | Priloga v nalogi |
|---|---|
| `priloga1_preslikava_tipov_napak.csv` | Priloga 1: preslikava izvornih oznak napak v šest kategorij |
| `priloga1_struktura_uvrstitve.csv` | Priloga 1: zbirni pregled uvrstitve po šifrantu in obdobju |
| `priloga2_podatkovni_model.csv` | Priloga 2: pregled 24 tabel baze `servis_db` po slojih |
| `priloga3_izsek_etl.py` | Priloga 3: izsek cevovoda ETL (**ni izvedljiva skripta**, temveč trije reprezentativni izseki iz `../01_etl/etl_servis.py`) |
| `priloga4_nijz_izbor_vzs.csv` | Priloga 4: izbor šestih vrst zdravstvenih storitev |
| `priloga4_nijz_izpadi_objav.csv` | Priloga 4: izpadi objav tedenskih poročil NIJZ |
| `priloga5_drsece_preverjanje.csv` | Priloga 5: rezultati drsečega preverjanja |
| `_podatki.json` | vsebina vseh prilog v strojno berljivi obliki |
| `gradi_docx.py` | sestavi `Priloge.docx` iz `_podatki.json` |

## Zagon

```bash
py -3.11 gradi_docx.py
```

Zahteva `python-docx`. Dokument se zapiše kot `Priloge.docx` v to mapo.
Priloga 1 je razumljiva le skupaj z razlago v `../02_fotona/README.md`
(rekonstrukcija stolpca `kategorija`).
