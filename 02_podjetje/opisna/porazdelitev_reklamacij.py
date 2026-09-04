"""
Porazdelitev vrst reklamacij – vodoravni stolpčni graf.
Akademska vizualizacija za diplomsko nalogo (slovenščina).
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────────────────────
# 1. KONFIGURACIJA
# ─────────────────────────────────────────────────────────────────────────────

# Nastavitve povezave so v ../.env (glej db_common.py v korenu projekta)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from db_common import DB

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'rezultati', 'porazdelitev_reklamacij.png')

# Oznaka za manjkajoče in neveljavne vrednosti ('DA' + NULL → ena kategorija)
NEZABELEZENO = 'Nezabeleženo / neveljavno'

BLUE = '#2c6fad'   # barva podatkovnih stolpcev
GRAY = '#a0a0a0'   # barva kategorije brez podatka

# ─────────────────────────────────────────────────────────────────────────────
# 2. PRIDOBIVANJE PODATKOV
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db: dict) -> tuple[pd.DataFrame, int]:
    """
    Vrne (df, total):
      df    – DataFrame s stolpci vrsta, stevilo, delez
      total – skupno število vseh reklamacij (imenovalec za deleže)
    """
    url = (
        "mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
        .format(**db)
    )
    engine = create_engine(url, echo=False)

    # 'DA' (neveljavna vrednost) se združi z NULL v skupno kategorijo
    query_kategorije = """
        SELECT
            CASE
                WHEN vrl.naziv IS NULL OR vrl.naziv = 'DA'
                THEN 'Nezabeleženo / neveljavno'
                ELSE vrl.naziv
            END AS vrsta,
            COUNT(*) AS stevilo
        FROM reklamacija r
        LEFT JOIN vrsta_reklamacije_lookup vrl
            ON r.vrsta_reklamacije_id = vrl.vrsta_reklamacije_id
        GROUP BY vrsta
        ORDER BY stevilo DESC
    """

    # Imenovalec: VSE reklamacije, ne le klasificirane
    query_skupaj = "SELECT COUNT(*) FROM reklamacija"

    with engine.connect() as conn:
        df = pd.read_sql(text(query_kategorije), conn)
        total = conn.execute(text(query_skupaj)).scalar()

    df['delez'] = df['stevilo'] / total * 100
    return df, total

# ─────────────────────────────────────────────────────────────────────────────
# 3. POMOŽNE FUNKCIJE – SLOVENSKA TIPOGRAFIJA
# ─────────────────────────────────────────────────────────────────────────────

def si_delez(x: float, dec: int = 1) -> str:
    """Delež z decimalno vejico: 86,0 %"""
    return f"{x:.{dec}f}".replace('.', ',') + ' %'   # nedeljivi presledek pred %

def si_stevilo(n: int) -> str:
    """Celo število s piko kot tisočico: 9.493"""
    return f"{int(n):,}".replace(',', '.')

# ─────────────────────────────────────────────────────────────────────────────
# 4. IZRIS
# ─────────────────────────────────────────────────────────────────────────────

def plot_porazdelitev(df: pd.DataFrame, total: int, output: str) -> None:
    colors = [GRAY if v == NEZABELEZENO else BLUE for v in df['vrsta']]

    _, ax = plt.subplots(figsize=(9, max(4, len(df) * 0.52 + 1)))

    bars = ax.barh(
        df['vrsta'][::-1],
        df['delez'][::-1],
        color=colors[::-1],
        edgecolor='white',
        height=0.6,
    )

    # Oznake desno od vsakega stolpca: delež in absolutno število
    for bar, row in zip(bars, df[::-1].itertuples()):
        label = f"{si_delez(row.delez)}  ({si_stevilo(row.stevilo)})"
        ax.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            label,
            va='center', ha='left', fontsize=10, color='#333333',
        )

    # Os x – celi deleži z decimalno vejico (npr. »0 %«, »20 %«)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: si_delez(x, dec=0))
    )
    ax.set_xlabel('Delež (%)', fontsize=11, labelpad=8)
    ax.set_xlim(0, 107)   # prostor za oznake

    # Čisto akademsko oblikovanje
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='y', labelsize=10)
    ax.tick_params(axis='x', labelsize=9)

    # Opomba n v spodnjem desnem kotu
    ax.text(
        1, -0.09,
        f'n = {si_stevilo(total)}',
        transform=ax.transAxes, ha='right', fontsize=9, color='#666666',
    )

    plt.tight_layout()
    plt.savefig(output, dpi=300, bbox_inches='tight')
    plt.show()
    print(f'Shranjeno: {output}')

# ─────────────────────────────────────────────────────────────────────────────
# 5. ZAGON
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    df, total = load_data(DB)
    plot_porazdelitev(df, total, OUTPUT)
