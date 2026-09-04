"""
Porazdelitev reklamacijskih pozicij in postavk servisnih posegov po družini
izdelkov – primerjalni vodoravni stolpčni graf (grupirano).
Akademska vizualizacija za diplomsko nalogo (slovenščina).

Enota analize je POZICIJA (reklamacija_pozicija) oz. POSTAVKA
(servisni_poseg_postavka), ne dokument. En dokument (reklamacija /
servisni poseg) lahko vsebuje več pozicij/postavk iz različnih družin,
zato bi štetje na ravni dokumenta isti dokument prištelo k več družinam
hkrati in bi se deleži sešteli v precej več kot 100 %. Na ravni
pozicije/postavke vsaka vrstica pripada natanko eni družini, zato
deleži tvorijo pravo porazdelitev (vsota = 100 %) in sta seriji
medsebojno primerljivi.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from sqlalchemy import create_engine, text

from anonimizacija_druzin import anonimiziraj_seznam

# ─────────────────────────────────────────────────────────────────────────────
# 1. KONFIGURACIJA
# ─────────────────────────────────────────────────────────────────────────────

# Nastavitve povezave so v ../.env (glej db_common.py v korenu projekta)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from db_common import DB

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'rezultati', 'porazdelitev_po_druzini.png')

TOP_N = 8   # število družin, prikazanih posamično; ostale se združijo

BLUE   = '#2c6fad'   # barva stolpcev – reklamacije
ORANGE = '#d9822b'   # barva stolpcev – servisni posegi

# ─────────────────────────────────────────────────────────────────────────────
# 2. PRIDOBIVANJE PODATKOV
# ─────────────────────────────────────────────────────────────────────────────

def load_data(db: dict) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """
    Vrne (df_rek, df_sp, total_rek, total_sp):
      df_rek, df_sp – DataFrame s stolpci druzina, stevilo, delez
                       (stevilo = št. pozicij oz. postavk z znano družino)
      total_rek     – skupno število pozicij z znano družino (imenovalec za delez_rek)
      total_sp      – skupno število postavk z znano družino (imenovalec za delez_sp)
    """
    url = (
        "mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
        .format(**db)
    )
    engine = create_engine(url, echo=False)

    # Raven POZICIJE: vsaka vrstica reklamacija_pozicija šteje enkrat,
    # natanko v eno družino.
    query_rek = """
        SELECT
            n.druzina_izdelka AS druzina,
            COUNT(*) AS stevilo
        FROM reklamacija_pozicija rp
        JOIN predmet p          ON p.sifra_predmeta = rp.sifra_predmeta
        JOIN nadrejen_izdelek n ON n.ident_nadr_izdelka = p.ident_nadr_izdelka
        WHERE n.druzina_izdelka IS NOT NULL AND n.druzina_izdelka <> ''
        GROUP BY n.druzina_izdelka
        ORDER BY stevilo DESC
    """

    # Raven POSTAVKE: vsaka vrstica servisni_poseg_postavka šteje enkrat,
    # natanko v eno družino (en dokument ima lahko več postavk iz različnih
    # družin, zato štetje na ravni dokumenta ni primerno).
    query_sp = """
        SELECT
            n.druzina_izdelka AS druzina,
            COUNT(*) AS stevilo
        FROM servisni_poseg_postavka spp
        JOIN predmet p          ON p.sifra_predmeta = spp.sifra_predmeta
        JOIN nadrejen_izdelek n ON n.ident_nadr_izdelka = p.ident_nadr_izdelka
        WHERE n.druzina_izdelka IS NOT NULL AND n.druzina_izdelka <> ''
        GROUP BY n.druzina_izdelka
        ORDER BY stevilo DESC
    """

    with engine.connect() as conn:
        df_rek = pd.read_sql(text(query_rek), conn)
        df_sp  = pd.read_sql(text(query_sp), conn)

    # Imenovalec = vsota vseh ujemanih vrstic (deleži se sestejejo v 100 %)
    total_rek = int(df_rek['stevilo'].sum())
    total_sp  = int(df_sp['stevilo'].sum())

    df_rek['delez'] = df_rek['stevilo'] / total_rek * 100
    df_sp['delez']  = df_sp['stevilo'] / total_sp * 100
    return df_rek, df_sp, total_rek, total_sp

# ─────────────────────────────────────────────────────────────────────────────
# 3. PRIPRAVA PRIMERJALNE TABELE
# ─────────────────────────────────────────────────────────────────────────────

def pripravi_primerjavo(df_rek: pd.DataFrame, df_sp: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Združi obe porazdelitvi po družini; manj pomembne družine strne v 'Preostale družine'."""
    merged = pd.merge(
        df_rek[['druzina', 'stevilo', 'delez']].rename(columns={'stevilo': 'stevilo_rek', 'delez': 'delez_rek'}),
        df_sp[['druzina', 'stevilo', 'delez']].rename(columns={'stevilo': 'stevilo_sp', 'delez': 'delez_sp'}),
        on='druzina', how='outer',
    ).fillna(0)

    merged['max_delez'] = merged[['delez_rek', 'delez_sp']].max(axis=1)
    merged = merged.sort_values('max_delez', ascending=False).reset_index(drop=True)

    top = merged.iloc[:top_n].copy()
    rest = merged.iloc[top_n:]

    if not rest.empty:
        preostalo = pd.DataFrame([{
            'druzina':    'Preostale družine',
            'stevilo_rek': rest['stevilo_rek'].sum(),
            'delez_rek':   rest['delez_rek'].sum(),
            'stevilo_sp':  rest['stevilo_sp'].sum(),
            'delez_sp':    rest['delez_sp'].sum(),
        }])
        top = pd.concat([top, preostalo], ignore_index=True)

    return top.sort_values('delez_rek', ascending=False).reset_index(drop=True)

# ─────────────────────────────────────────────────────────────────────────────
# 4. POMOŽNE FUNKCIJE – SLOVENSKA TIPOGRAFIJA
# ─────────────────────────────────────────────────────────────────────────────

def si_delez(x: float, dec: int = 1) -> str:
    """Delež z decimalno vejico: 19,9 %"""
    return f"{x:.{dec}f}".replace('.', ',') + ' %'   # nedeljivi presledek pred %

def si_stevilo(n: int) -> str:
    """Celo število s piko kot tisočico: 9.493"""
    return f"{int(n):,}".replace(',', '.')

# ─────────────────────────────────────────────────────────────────────────────
# 5. IZRIS
# ─────────────────────────────────────────────────────────────────────────────

def plot_primerjavo(df: pd.DataFrame, total_rek: int, total_sp: int, output: str) -> None:
    df = df[::-1].reset_index(drop=True)   # narašcajoče, da je najvišja vrednost zgoraj
    n = len(df)
    height = 0.35
    y = list(range(n))

    _, ax = plt.subplots(figsize=(10, max(4, n * 0.65 + 1)))

    bars_rek = ax.barh(
        [i + height / 2 for i in y], df['delez_rek'],
        height=height, color=BLUE, edgecolor='white', label='Reklamacije',
    )
    bars_sp = ax.barh(
        [i - height / 2 for i in y], df['delez_sp'],
        height=height, color=ORANGE, edgecolor='white', label='Servisni posegi',
    )

    ax.set_yticks(y)
    ax.set_yticklabels(df['druzina'], fontsize=10)

    # Oznake desno od vsakega stolpca
    for bar, delez in zip(bars_rek, df['delez_rek']):
        ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height() / 2,
                 si_delez(delez), va='center', ha='left', fontsize=9, color='#333333')
    for bar, delez in zip(bars_sp, df['delez_sp']):
        ax.text(bar.get_width() + 0.4, bar.get_y() + bar.get_height() / 2,
                 si_delez(delez), va='center', ha='left', fontsize=9, color='#333333')

    max_delez = max(df['delez_rek'].max(), df['delez_sp'].max())
    ax.set_xlim(0, max_delez + max_delez * 0.25 + 3)

    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: si_delez(x, dec=0))
    )
    ax.set_xlabel('Delež (%)', fontsize=11, labelpad=8)

    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='x', labelsize=9)
    ax.legend(loc='lower right', frameon=False, fontsize=10)

    ax.text(
        1, -0.07 - 0.012 * n,
        f'n(pozicije reklamacij) = {si_stevilo(total_rek)}    '
        f'n(postavke posegov) = {si_stevilo(total_sp)}',
        transform=ax.transAxes, ha='right', fontsize=9, color='#666666',
    )

    plt.tight_layout()
    plt.savefig(output, dpi=300, bbox_inches='tight')
    plt.show()
    print(f'Shranjeno: {output}')

# ─────────────────────────────────────────────────────────────────────────────
# 6. ZAGON
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    df_rek, df_sp, total_rek, total_sp = load_data(DB)
    df_primerjava = pripravi_primerjavo(df_rek, df_sp, TOP_N)
    df_primerjava['druzina'] = anonimiziraj_seznam(df_primerjava['druzina'])
    plot_primerjavo(df_primerjava, total_rek, total_sp, OUTPUT)
