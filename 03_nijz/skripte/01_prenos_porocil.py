# -*- coding: utf-8 -*-
"""
Faza 2, korak 1: prenos vseh tedenskih porocil NIJZ o cakalnih dobah.

Vir: https://nijz.si/podatki/cakalne-dobe/tedenska-porocila-o-cakalnih-dobah/
Surove .xlsx datoteke se shranijo v data/raw/ in se nikoli ne prepisujejo
(ce datoteka ze obstaja in ni prazna, se prenos preskoci).
"""

import re
import sys
import time
from pathlib import Path

import requests

LISTING_URL = (
    "https://nijz.si/podatki/cakalne-dobe/tedenska-porocila-o-cakalnih-dobah/"
)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MAX_RETRIES = 3
RETRY_PAUSE_S = 5


def fetch_listing() -> list[str]:
    """Vrne seznam vseh URL-jev .xlsx datotek s strani z arhivom."""
    r = requests.get(LISTING_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    urls = re.findall(r'href="(https://nijz\.si/wp-content/uploads/[^"]+?\.xlsx)"', r.text)
    # odstranimo morebitne dvojnike, ohranimo vrstni red s strani
    seen, unique = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def download(url: str, dest: Path) -> str:
    """Prenese eno datoteko z do MAX_RETRIES poskusi. Vrne status."""
    if dest.exists() and dest.stat().st_size > 0:
        return "preskok (ze obstaja)"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return f"preneseno ({len(r.content)} B)"
        except Exception as e:  # noqa: BLE001
            if attempt == MAX_RETRIES:
                return f"NAPAKA: {e}"
            time.sleep(RETRY_PAUSE_S)
    return "NAPAKA: nedosegljivo"


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    urls = fetch_listing()
    print(f"Najdenih {len(urls)} .xlsx povezav na strani z arhivom.")
    errors = 0
    for i, url in enumerate(urls, 1):
        name = url.rsplit("/", 1)[-1]
        status = download(url, RAW_DIR / name)
        print(f"[{i:3d}/{len(urls)}] {name}: {status}")
        if status.startswith("NAPAKA"):
            errors += 1
        time.sleep(0.3)  # obzirnost do streznika
    print(f"\nKoncano. Napak: {errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
