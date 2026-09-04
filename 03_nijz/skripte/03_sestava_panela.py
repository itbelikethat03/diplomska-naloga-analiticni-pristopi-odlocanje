# -*- coding: utf-8 -*-
"""
Faza 2, korak 3: sestava panela teden x VZS iz listov 'Tb 01' vseh porocil.

Iz vsake datoteke se prebere nacionalni agregat po VZS (list 'Tb 01') in
zdruzi v en panel. Stolpci se preslikajo po imenu (format se je skozi cas
aditivno spreminjal), zato so kazalniki, ki jih v starejsih porocilih ni
(realizirana CD, preklici), za tiste tedne manjkajoci (NaN) po konstrukciji.

Izhod: data/panel_vzs.parquet in data/panel_vzs.csv
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT_DIR = Path(__file__).resolve().parents[1] / "data"

# dovoli pripono "-1"/"-2" (ponovno nalozene datoteke na strani NIJZ)
DATE_RE = re.compile(r"na-dan-(\d{2})\.(\d{2})\.(\d{4})(?:-\d)?\.xlsx$")

# preslikava izvirnih imen stolpcev -> kratka imena panela
COLMAP = {
    "VZS šifra": "vzs_sifra",
    "VZS naziv": "vzs_naziv",
    "TIP VZS": "tip_vzs",
    "Povprečna ČD na prvi prosti termin ZELO HITRO": "cd_zelo_hitro",
    "Povprečna ČD na prvi prosti termin HITRO": "cd_hitro",
    "Povprečna ČD na prvi prosti termin REDNO": "cd_redno",
    "Povprečna REALIZIRANA ČD v zadnjih 7 dneh ZELO HITRO": "real_cd_zelo_hitro",
    "Povprečna REALIZIRANA ČD v zadnjih 7 dneh HITRO": "real_cd_hitro",
    "Povprečna REALIZIRANA ČD v zadnjih 7 dneh REDNO": "real_cd_redno",
    "Število izvajalcev s čakajočimi pacienti Bolnišnica": "izv_bolnisnica",
    "Število izvajalcev s čakajočimi pacienti Zdravstveni dom": "izv_zd",
    "Število izvajalcev s čakajočimi pacienti Zasebnik s koncesijo": "izv_zasebnik",
    "Število čakajočih Zelo hitro": "cak_zelo_hitro",
    "Število čakajočih Hitro": "cak_hitro",
    "Število čakajočih Redno": "cak_redno",
    "Število čakajočih skupna vsota": "cak_skupaj",
    "Število čakajočih NAD dop. ČD Zelo hitro": "nad_zelo_hitro",
    "Število čakajočih NAD dop. ČD Hitro": "nad_hitro",
    "Število čakajočih NAD dop. ČD Redno": "nad_redno",
    "Število čakajočih NAD dop. ČD skupna vsota": "nad_skupaj",
    "Preklicana naročila s strani CENTRALNEGA SISTEMA v zadnjih 7 dneh": "prekl_sistem",
    "Preklicana naročila s strani PACIENTA v zadnjih 7 dneh": "prekl_pacient",
    "Preklicana naročila s strani IZVAJALCA v zadnjih 7 dneh": "prekl_izvajalec",
    "Preklicana naročila v zadnjih 7 dneh SKUPNA VSOTA": "prekl_skupaj",
}

NUMERIC = [v for v in COLMAP.values() if v not in ("vzs_sifra", "vzs_naziv", "tip_vzs")]


def norm_text(s: pd.Series) -> pd.Series:
    """Poenoti zapis besedilnih oznak, ki se med porocili razlikuje
    (npr. 'Kurativni pregled- Prvi' proti 'Kurativni pregled - Prvi')."""
    return (s.astype(str).str.strip()
            .str.replace(r"\s*-\s*", " - ", regex=True)
            .str.replace(r"\s+", " ", regex=True))


def report_date(name: str) -> pd.Timestamp:
    m = DATE_RE.search(name)
    return pd.Timestamp(f"{m.group(3)}-{m.group(2)}-{m.group(1)}")


def read_one(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Tb 01", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=COLMAP)
    keep = [c for c in COLMAP.values() if c in df.columns]
    df = df[keep].copy()
    df = df[df["vzs_sifra"].notna()]
    df["vzs_sifra"] = df["vzs_sifra"].astype(str).str.strip()
    for c in ("vzs_naziv", "tip_vzs"):
        if c in df.columns:
            df[c] = norm_text(df[c])
    for c in NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df.insert(0, "datum", report_date(path.name))
    return df


def main() -> None:
    files = sorted(RAW_DIR.glob("*.xlsx"), key=lambda p: report_date(p.name))
    parts = []
    for i, f in enumerate(files, 1):
        parts.append(read_one(f))
        if i % 20 == 0:
            print(f"  ... {i}/{len(files)}")
    panel = pd.concat(parts, ignore_index=True)
    panel = panel.sort_values(["datum", "vzs_sifra"]).reset_index(drop=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(OUT_DIR / "panel_vzs.parquet", index=False)
    panel.to_csv(OUT_DIR / "panel_vzs.csv", index=False, encoding="utf-8-sig")

    # povzetek
    dates = panel["datum"].drop_duplicates().sort_values()
    print(f"\nPanel: {len(panel)} vrstic, {panel.shape[1]} stolpcev")
    print(f"Tednov: {dates.nunique()}, od {dates.min().date()} do {dates.max().date()}")
    print(f"Razlicnih VZS: {panel['vzs_sifra'].nunique()}")
    gaps = dates.diff().dt.days.dropna()
    print("Razmiki med porocili (dni):", gaps.value_counts().sort_index().to_dict())
    miss = panel[NUMERIC].isna().mean().round(3)
    print("\nDelez manjkajocih po stolpcih:")
    print(miss.to_string())


if __name__ == "__main__":
    main()
