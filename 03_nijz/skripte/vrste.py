# -*- coding: utf-8 -*-
"""
Skupni modul za popravljeno poglavje 5.4: sestava tedenskih vrst iz panela
z zastavico kakovosti (nadomesca izbor_storitev.py).

Bistvene razlike od prejsnje razlicice:

1. BREZ INTERPOLACIJE. Prejsnji modul je vrsto preslikal na redno 7-dnevno
   mrezo in manjkajoce tedne linearno interpoliral; interpolirane vrednosti
   so vstopale v trening modelov. Tu se uporabljajo izkljucno dejansko
   opazovani in kot zanesljivi oznaceni tedni.

2. OBRAVNAVA VRZELI (korak D2). Arhiv nima enakomernih korakov: 8 tednov
   manjka (prazniki), 2 sta oznacena kot nezanesljiva, dan objave pa niha
   med sredo in cetrtkom (razmiki 6, 7, 8, 14, 20 in 21 dni). Modeli AR(1)
   in linearni trend predpostavljajo enakomeren korak. Privzeta odlocitev:
   uporabi se ZAPOREDNI INDEKS opazovanj ne glede na dolzino vrzeli, torej
   se 14-dnevna vrzel obravnava kot en korak. Utemeljitev: (a) merjena
   kolicina je stanje (zaloga) in ne tok, zato je vrednost ob vsakem
   preseku primerljiva ne glede na razmik do prejsnjega preseka; (b) ohrani
   se celotna dolzina vrste, kar je pri 110 tockah bistveno; (c) alternativa
   (izlocitev oken cez vrzel) bi odstranila prav tedne okoli praznikov, ki
   so za oceno robustnosti najbolj informativni. Funkcija delez_vrzeli()
   izmeri, kolikSen del napovedi je te predpostavke sploh izpostavljen,
   funkcija cez_vrzel() pa omogoca obcutljivostni izracun brez njih.
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
REZ = BASE / "rezultati"
VIZ = BASE / "visualizations"

KANON = "cak_skupaj"          # A1: edina mera stevila cakajocih
AGREGAT = "AGREGAT"

IZBRANE = {
    "1010P": "Dermatološki pregled - prvi",
    "1018P": "Kardiološki pregled - prvi",
    "1941": "UZ vratnih žil",
    "1755": "MR glave brez kontrasta",
    "1195": "Operacija sive mrene (katarakte)",
    "1626": "Endoproteza kolena",
}
VSE_VRSTE = list(IZBRANE) + [AGREGAT]
IMENA = dict(IZBRANE, **{AGREGAT: "Agregat"})

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

KAZALNIKI = ["cak_skupaj", "cak_zelo_hitro", "cak_hitro", "cak_redno",
             "cd_zelo_hitro", "cd_hitro", "cd_redno"]


def nalozi() -> pd.DataFrame:
    """Panel z zastavico kakovosti (izhod 11_panel_kakovost.py)."""
    return pd.read_parquet(DATA / "panel_kakovost.parquet")


def nabor() -> pd.DataFrame:
    return pd.read_csv(DATA / "nabor_vzs.csv", dtype={"vzs_sifra": str})


def sifre_agregata() -> list[str]:
    n = nabor()
    return sorted(n.loc[n["v_agregatu"], "vzs_sifra"])


def vrsta(panel: pd.DataFrame, sifra: str, samo_zanesljivi: bool = True
          ) -> pd.DataFrame:
    """Tedenska vrsta ene storitve ali agregata; indeks = datum porocila.

    samo_zanesljivi=True izpusti tedne z zastavico nezanesljivosti (A4).
    Vrne se stolpec 'dni_od_prej' za diagnostiko vrzeli (D2).
    """
    p = panel[panel["zanesljiv"]] if samo_zanesljivi else panel
    if sifra == AGREGAT:
        sub = p[p["vzs_sifra"].isin(sifre_agregata())]
        g = sub.groupby("datum")
        out = g[["cak_skupaj", "cak_zelo_hitro", "cak_hitro", "cak_redno"]].sum()
        # ČD agregata = mediana cez VZS (vsota dni bi bila brez pomena)
        out[["cd_zelo_hitro", "cd_hitro", "cd_redno"]] = (
            g[["cd_zelo_hitro", "cd_hitro", "cd_redno"]].median())
        out = out.sort_index()
    else:
        out = (p[p["vzs_sifra"] == sifra].set_index("datum").sort_index()
               [KAZALNIKI])
    out = out.copy()
    out["dni_od_prej"] = out.index.to_series().diff().dt.days
    return out


def delez_vrzeli(idx: pd.DatetimeIndex) -> dict:
    """Koliko je vrsta sploh izpostavljena predpostavki enakomernega koraka."""
    d = pd.Series(idx).diff().dt.days.dropna()
    return {"n_korakov": int(len(d)),
            "korakov_7_dni": int((d == 7).sum()),
            "korakov_6_8_dni": int(d.between(6, 8).sum()),
            "korakov_nad_8_dni": int((d > 8).sum()),
            "delez_nerednih": round(float((~d.between(6, 8)).mean()), 4)}


def cez_vrzel(idx: pd.DatetimeIndex, i_izvor: int, i_cilj: int,
              prag_dni: int = 8) -> bool:
    """Ali napoved iz tocke i_izvor v i_cilj prečka vrzel, daljso od praga."""
    d = pd.Series(idx).diff().dt.days
    return bool((d.iloc[i_izvor + 1: i_cilj + 1] > prag_dni).any())


def robustni_z(x: pd.Series) -> pd.Series:
    m = x.median()
    mad = (x - m).abs().median()
    return (x - m) / (1.4826 * mad) if mad > 0 else pd.Series(np.nan, index=x.index)
