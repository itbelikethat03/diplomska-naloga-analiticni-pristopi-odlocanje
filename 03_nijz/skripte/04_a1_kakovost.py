# -*- coding: utf-8 -*-
"""
A1: analiza kakovosti in manjkajocih podatkov (N-RV1).

- delezi manjkajocih vrednosti po storitvi / tednu / stopnji nujnosti,
- spremembe nabora VZS skozi cas (vstopi/izstopi),
- vizualizacija pokritosti (matrika storitev x teden),
- kandidatni izbor storitev za modeliranje po merilih 1.4:
  (1) popolna vrsta cak_skupaj, (2) zadostna raven (brez nizkih/nicnih
  vrednosti), (3) vsebinska raznolikost — koncni izbor je dokumentiran
  v POROCILO_NIJZ.md.

Izhodi: rezultati/a1_*.csv, visualizations/a1_pokritost.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
REZ = BASE / "rezultati"
VIZ = BASE / "visualizations"
REZ.mkdir(exist_ok=True)
VIZ.mkdir(exist_ok=True)

panel = pd.read_parquet(BASE / "data" / "panel_vzs.parquet")
dates = sorted(panel["datum"].unique())

# ---------------------------------------------------------------- manjkajoci
kaz = ["cd_zelo_hitro", "cd_hitro", "cd_redno",
       "cak_zelo_hitro", "cak_hitro", "cak_redno", "cak_skupaj"]

po_tednu = panel.groupby("datum")[kaz].apply(lambda d: d.isna().mean()).round(4)
po_tednu.to_csv(REZ / "a1_manjkajoci_po_tednu.csv", encoding="utf-8-sig")

po_vzs = panel.groupby(["vzs_sifra", "vzs_naziv"])[kaz].apply(
    lambda d: d.isna().mean()).round(4)
po_vzs["n_tednov"] = panel.groupby(["vzs_sifra", "vzs_naziv"])["datum"].nunique()
po_vzs.to_csv(REZ / "a1_manjkajoci_po_vzs.csv", encoding="utf-8-sig")

print("Povprecen delez manjkajocih po kazalnikih:")
print(panel[kaz].isna().mean().round(3).to_string())

# ------------------------------------------------- spremembe nabora VZS
prisotnost = panel.pivot_table(index="vzs_sifra", columns="datum",
                               values="vzs_naziv", aggfunc="size").notna()
vstopi, izstopi = [], []
for i in range(1, len(dates)):
    prej, zdaj = prisotnost[dates[i - 1]], prisotnost[dates[i]]
    for s in prisotnost.index[~prej & zdaj]:
        vstopi.append({"datum": dates[i], "vzs_sifra": s, "dogodek": "vstop"})
    for s in prisotnost.index[prej & ~zdaj]:
        izstopi.append({"datum": dates[i], "vzs_sifra": s, "dogodek": "izstop"})
spremembe = pd.DataFrame(vstopi + izstopi)
if not spremembe.empty:
    nazivi = panel.drop_duplicates("vzs_sifra").set_index("vzs_sifra")["vzs_naziv"]
    spremembe["vzs_naziv"] = spremembe["vzs_sifra"].map(nazivi)
    spremembe = spremembe.sort_values(["datum", "dogodek"])
spremembe.to_csv(REZ / "a1_spremembe_nabora_vzs.csv", index=False,
                 encoding="utf-8-sig")
print(f"\nDogodkov sprememb nabora VZS: {len(spremembe)} "
      f"(vstopov {len(vstopi)}, izstopov {len(izstopi)})")
n_po_tednu = prisotnost.sum(axis=0)
print("Stevilo VZS po tednih: min", int(n_po_tednu.min()),
      "max", int(n_po_tednu.max()))

# ------------------------------------------------------- matrika pokritosti
ok = panel.pivot_table(index="vzs_sifra", columns="datum",
                       values="cak_skupaj", aggfunc="first")
# 2 = podatek, 1 = vrstica brez vrednosti, 0 = VZS ta teden ni v porocilu
m = np.where(ok.notna(), 2, np.where(prisotnost.loc[ok.index, ok.columns], 1, 0))
order = np.argsort(-(m == 2).sum(axis=1))
fig, ax = plt.subplots(figsize=(12, 8))
ax.imshow(m[order], aspect="auto", cmap=plt.cm.get_cmap("Greys", 3),
          interpolation="nearest")
ax.set_xlabel("Teden (4. 4. 2024 – 15. 7. 2026)")
ax.set_ylabel("VZS (urejeno po popolnosti)")
ax.set_title("Pokritost panela: število čakajočih (temno = podatek, "
             "sivo = brez vrednosti, belo = VZS ni v poročilu)")
xticks = np.linspace(0, len(ok.columns) - 1, 8).astype(int)
ax.set_xticks(xticks)
ax.set_xticklabels([pd.Timestamp(ok.columns[i]).strftime("%m/%y") for i in xticks])
fig.tight_layout()
fig.savefig(VIZ / "a1_pokritost.png", dpi=150)
plt.close(fig)

# ------------------------------------------- kandidati za modeliranje (1.4)
n_dates = len(dates)
# grupira se samo po sifri: naziv/tip se med porocili lahko razlikujeta v zapisu
zadnji = (panel.sort_values("datum").drop_duplicates("vzs_sifra", keep="last")
          .set_index("vzs_sifra")[["vzs_naziv", "tip_vzs"]])
g = panel.groupby("vzs_sifra")
kand = g.agg(n_tednov=("datum", "nunique"),
             n_cak=("cak_skupaj", "count"),
             mediana_cak=("cak_skupaj", "median"),
             min_cak=("cak_skupaj", "min"),
             mediana_cd_redno=("cd_redno", "median")).reset_index()
kand = kand.join(zadnji, on="vzs_sifra")
kand["popolna"] = kand["n_cak"] == n_dates
kandidati = kand[kand["popolna"] & (kand["min_cak"] >= 30)].copy()
kandidati = kandidati.sort_values("mediana_cak", ascending=False)
kandidati.to_csv(REZ / "a1_kandidati_izbor.csv", index=False,
                 encoding="utf-8-sig")
print(f"\nKandidatov (popolna vrsta, min. cakajocih >= 30): {len(kandidati)}")
print("\nNajvecjih 30 kandidatov po mediani stevila cakajocih:")
print(kandidati.head(30)[["vzs_sifra", "vzs_naziv", "tip_vzs",
                          "mediana_cak", "mediana_cd_redno"]]
      .to_string(index=False))

# ------------------------------------------------------- agregatna vrsta
ag = panel.groupby("datum").agg(cak_skupaj=("cak_skupaj", "sum"),
                                n_vzs=("vzs_sifra", "nunique"),
                                n_cak_ne_nan=("cak_skupaj", "count"))
ag.to_csv(REZ / "a1_agregat_tedensko.csv", encoding="utf-8-sig")
print("\nAgregat (vsota cakajocih cez vse VZS): min",
      int(ag["cak_skupaj"].min()), "max", int(ag["cak_skupaj"].max()))
