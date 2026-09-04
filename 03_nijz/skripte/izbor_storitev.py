# -*- coding: utf-8 -*-
"""
Skupni modul: izbor reprezentativnih storitev (merila iz nacrta, razdelek 1.4)
in priprava tedenskih vrst.

Merila izbora (uporabljena na rezultatih A1, a1_kandidati_izbor.csv):
(1) popolna vrsta cak_skupaj (112/112 tednov), (2) zadostna raven
(min. stevilo cakajocih >= 30, tu dejansko >= 1000), (3) vsebinska
raznolikost: dva ambulantna prva pregleda, dve slikovni diagnostiki
(UZ in MR), dve operativni storitvi (od tega ena z najdaljso CD).
Dodatno AGREGAT: vsota cakajocih cez vse VZS s popolnimi vrstami.
"""

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]

IZBRANE = {
    "1010P": "Dermatološki pregled - prvi",          # ambulantni pregled, najvec cakajocih
    "1018P": "Kardiološki pregled - prvi",           # ambulantni pregled, internistika
    "1941": "UZ vratnih žil",                        # slikovna diagnostika (UZ)
    "1755": "MR glave brez kontrasta",               # slikovna diagnostika (MR)
    "1195": "Operacija sive mrene (katarakte)",      # operativna storitev, najvec cakajocih
    "1626": "Endoproteza kolena",                    # operativna storitev, najdaljsa CD
}
AGREGAT = "AGREGAT"

# slovenski prazniki (dela prosti dnevi) v obdobju arhiva
PRAZNIKI = pd.to_datetime([
    "2024-04-27", "2024-05-01", "2024-05-02", "2024-06-25", "2024-08-15",
    "2024-10-31", "2024-11-01", "2024-12-25", "2024-12-26",
    "2025-01-01", "2025-01-02", "2025-02-08", "2025-04-21", "2025-04-27",
    "2025-05-01", "2025-05-02", "2025-06-25", "2025-08-15", "2025-10-31",
    "2025-11-01", "2025-12-25", "2025-12-26",
    "2026-01-01", "2026-01-02", "2026-02-08", "2026-04-06", "2026-04-27",
    "2026-05-01", "2026-05-02", "2026-06-25",
])


def nalozi_panel() -> pd.DataFrame:
    return pd.read_parquet(BASE / "data" / "panel_vzs.parquet")


def popolne_sifre(panel: pd.DataFrame) -> list[str]:
    """Sifre VZS s popolno vrsto cak_skupaj (v vseh tednih)."""
    n = panel["datum"].nunique()
    cnt = panel.groupby("vzs_sifra")["cak_skupaj"].count()
    return sorted(cnt[cnt == n].index)


def tedenska_vrsta(panel: pd.DataFrame, sifra: str) -> pd.DataFrame:
    """Tedenska vrsta ene storitve ali agregata (indeks: datum porocila).

    Vrne stolpce cak_skupaj, cak_zelo_hitro/hitro/redno, cd_redno, cd_hitro,
    cd_zelo_hitro. Agregat = vsota cakajocih oziroma mediana CD cez vse VZS
    s popolnimi vrstami (stabilen nabor -> brez navideznih skokov zaradi
    sprememb nabora VZS).
    """
    if sifra == AGREGAT:
        pop = popolne_sifre(panel)
        sub = panel[panel["vzs_sifra"].isin(pop)]
        g = sub.groupby("datum")
        out = g[["cak_skupaj", "cak_zelo_hitro", "cak_hitro", "cak_redno"]].sum()
        out[["cd_zelo_hitro", "cd_hitro", "cd_redno"]] = (
            g[["cd_zelo_hitro", "cd_hitro", "cd_redno"]].median())
        return out.sort_index()
    sub = panel[panel["vzs_sifra"] == sifra].set_index("datum").sort_index()
    return sub[["cak_skupaj", "cak_zelo_hitro", "cak_hitro", "cak_redno",
                "cd_zelo_hitro", "cd_hitro", "cd_redno"]]


def redna_tedenska(vrsta: pd.Series) -> pd.DataFrame:
    """Preslika vrsto na redno 7-dnevno mrezo (ISO teden).

    Porocila izhajajo enkrat tedensko, a dan v tednu se je spreminjal in
    ~7 tednov manjka. Vsako porocilo se pripise ISO tednu; manjkajoci tedni
    se linearno interpolirajo, stolpec 'opazovan' pa oznaci, ali je vrednost
    dejansko opazovana (False = interpolirana). Vse metrike napovedi se
    racunajo samo na opazovanih tednih.
    """
    df = vrsta.to_frame("y")
    iso = df.index.isocalendar()
    df["teden"] = pd.to_datetime(iso["year"].astype(str) + "-W"
                                 + iso["week"].astype(str).str.zfill(2) + "-3",
                                 format="%G-W%V-%u")
    df = df.groupby("teden")["y"].mean().to_frame()
    polni = pd.date_range(df.index.min(), df.index.max(), freq="7D")
    df = df.reindex(polni)
    df["opazovan"] = df["y"].notna()
    df["y"] = df["y"].interpolate("linear")
    return df
