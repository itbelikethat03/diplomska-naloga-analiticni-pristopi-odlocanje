"""
Gibanje števila servisnih posegov po mesecih (2020-2025) – linijski graf.
Akademska vizualizacija za diplomsko nalogo (slovenščina).

Namen grafa je pokazati naraščajoč trend in sezonska nihanja v številu
servisnih posegov na mesečni ravni. Ker gre za velik čas serij (71 mesecev),
graf je brez markerjev, oznake na osi x pa so omejene na januar vsakega leta.
"""

import pandas as pd
import os

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ─────────────────────────────────────────────────────────────────────────────
# 1. KONFIGURACIJA
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'rezultati', 'trend_servisnih_posegov.png')

BLUE = '#2c6fad'   # barva linije

# ─────────────────────────────────────────────────────────────────────────────
# 2. PODATKI
# ─────────────────────────────────────────────────────────────────────────────

# Mesečno število servisnih posegov, januar 2020 - november 2025.
STEVILO_POSEGOV = [
    77, 35, 25, 27, 39, 27, 27, 27, 45, 53, 61, 22,
    56, 44, 31, 47, 44, 39, 34, 28, 90, 58, 43, 54,
    30, 50, 62, 41, 56, 35, 63, 48, 47, 26, 41, 64,
    60, 57, 53, 51, 88, 92, 45, 64, 72, 45, 73, 23,
    105, 78, 106, 68, 89, 81, 83, 66, 96, 102, 90, 46,
    69, 64, 75, 51, 61, 42, 63, 60, 85, 105, 74,
]

def pripravi_podatke(stevilo_posegov: list) -> pd.DataFrame:
    """Vrne DataFrame s stolpcema datum (mesečni začetek) in stevilo."""
    datumi = pd.date_range(start='2020-01-01', periods=len(stevilo_posegov), freq='MS')
    return pd.DataFrame({'datum': datumi, 'stevilo': stevilo_posegov})

# ─────────────────────────────────────────────────────────────────────────────
# 3. POMOŽNE FUNKCIJE – SLOVENSKA TIPOGRAFIJA
# ─────────────────────────────────────────────────────────────────────────────

def si_stevilo(n: int) -> str:
    """Celo število s piko kot tisočico: 4.078"""
    return f"{int(n):,}".replace(',', '.')

# ─────────────────────────────────────────────────────────────────────────────
# 4. IZRIS
# ─────────────────────────────────────────────────────────────────────────────

def plot_trend(df: pd.DataFrame, output: str) -> None:
    total = int(df['stevilo'].sum())

    _, ax = plt.subplots(figsize=(10, 4.5))

    ax.plot(df['datum'], df['stevilo'], color=BLUE, linewidth=1.6)

    # Os y – začne pri 0
    ax.set_ylim(bottom=0)

    # Os x – oznake samo ob januarju vsakega leta
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.set_xlim(df['datum'].min(), df['datum'].max())

    ax.set_ylabel('Število servisnih posegov', fontsize=11, labelpad=8)

    # Čisto akademsko oblikovanje
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='both', labelsize=9)

    # Opomba n v spodnjem desnem kotu
    ax.text(
        1, -0.14,
        f'n = {si_stevilo(total)} (mesečno, 2020–2025)',
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
    df = pripravi_podatke(STEVILO_POSEGOV)
    plot_trend(df, OUTPUT)
