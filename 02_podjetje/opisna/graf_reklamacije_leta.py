"""
Gibanje števila reklamacij po letih – linijski graf.
Akademska vizualizacija za diplomsko nalogo (slovenščina).

Leto reklamacije je določeno po datumu prejema (prejem_reklamacije.datum_prejema).
Ker ima lahko posamezna reklamacija več zapisov o prejemu, se šteje
COUNT(DISTINCT reklamacija_id), da vsaka reklamacija prispeva natanko enkrat.
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
                      '..', 'rezultati', 'reklamacije_po_letih.png')

LETO_PADCA    = 2020   # leto, ki ga anotacija posebej izpostavi
ZADNJE_NEPOPOLNO_LETO = 2025   # leto, ki v podatkih ni zaključeno

BLUE = '#2c6fad'   # barva linije

# ─────────────────────────────────────────────────────────────────────────────
# 2. PRIDOBIVANJE PODATKOV
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db: dict) -> tuple[pd.DataFrame, int]:
    """
    Vrne (df, total):
      df    – DataFrame s stolpci leto, stevilo (št. reklamacij glede na leto prejema)
      total – skupno število vseh reklamacij (imenovalec opombe n)
    """
    url = (
        "mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
        .format(**db)
    )
    engine = create_engine(url, echo=False)

    query_leta = """
        SELECT
            YEAR(datum_prejema) AS leto,
            COUNT(DISTINCT reklamacija_id) AS stevilo
        FROM prejem_reklamacije
        WHERE datum_prejema IS NOT NULL
        GROUP BY leto
        ORDER BY leto
    """

    # Imenovalec: VSE reklamacije, ne le tiste z znanim datumom prejema
    query_skupaj = "SELECT COUNT(*) FROM reklamacija"

    with engine.connect() as conn:
        df = pd.read_sql(text(query_leta), conn)
        total = conn.execute(text(query_skupaj)).scalar()

    return df, total

# ─────────────────────────────────────────────────────────────────────────────
# 3. POMOŽNE FUNKCIJE – SLOVENSKA TIPOGRAFIJA
# ─────────────────────────────────────────────────────────────────────────────

def si_stevilo(n: int) -> str:
    """Celo število s piko kot tisočico: 1.293"""
    return f"{int(n):,}".replace(',', '.')

# ─────────────────────────────────────────────────────────────────────────────
# 4. IZRIS
# ─────────────────────────────────────────────────────────────────────────────

def plot_gibanje(df: pd.DataFrame, total: int, output: str) -> None:
    _, ax = plt.subplots(figsize=(9, 4.8))

    ax.plot(
        df['leto'], df['stevilo'],
        color=BLUE, linewidth=2,
        marker='o', markersize=5.5,
        markerfacecolor=BLUE, markeredgecolor='white', markeredgewidth=0.8,
        zorder=3,
    )

    # Y os: začne pri 0
    ax.set_ylim(bottom=0)
    ax.set_xlim(df['leto'].min() - 0.4, df['leto'].max() + 0.4)
    ax.set_xticks(df['leto'])
    ax.set_xticklabels(df['leto'], rotation=45, ha='right')

    # Slovensko formatiranje tisočic na osi y
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: si_stevilo(x)))

    ax.set_xlabel('Leto', fontsize=11, labelpad=8)
    ax.set_ylabel('Število reklamacij', fontsize=11)
    ax.set_title('Gibanje števila reklamacij po letih', fontsize=12, pad=14)

    # Diskretne horizontalne mreže za lažje branje
    ax.grid(axis='y', color='#dddddd', linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Čisto akademsko oblikovanje
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='both', labelsize=9)

    # Anotacija: izpostavi padec v izbranem letu
    if LETO_PADCA in df['leto'].values:
        x_p = LETO_PADCA
        y_p = int(df.loc[df['leto'] == LETO_PADCA, 'stevilo'].iloc[0])
        ax.annotate(
            f'padec {LETO_PADCA}',
            xy=(x_p, y_p),
            xytext=(x_p - 3.0, y_p + 220),
            fontsize=9.5, color='#444444', ha='center',
            arrowprops=dict(arrowstyle='->', color='#888888', linewidth=0.9, shrinkA=0, shrinkB=4),
        )

    # Opomba ob nepopolnem zadnjem letu
    if ZADNJE_NEPOPOLNO_LETO in df['leto'].values:
        y_n = int(df.loc[df['leto'] == ZADNJE_NEPOPOLNO_LETO, 'stevilo'].iloc[0])
        ax.annotate(
            f'{ZADNJE_NEPOPOLNO_LETO}: nepopolno leto',
            xy=(ZADNJE_NEPOPOLNO_LETO, y_n),
            xytext=(ZADNJE_NEPOPOLNO_LETO, y_n + 160),
            fontsize=8.5, color='#888888', ha='center',
        )

    # Opomba n v spodnjem desnem kotu
    ax.text(
        1, -0.16,
        f'n = {si_stevilo(total)}',
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
    plot_gibanje(df, total, OUTPUT)
