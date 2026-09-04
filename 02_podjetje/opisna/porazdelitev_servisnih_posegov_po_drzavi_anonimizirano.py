"""
Porazdelitev servisnih posegov po trgih – vodoravni stolpčni graf
(prvih 15 od skupno 42 trgov, urejeno padajoče po deležu).
Akademska vizualizacija za diplomsko nalogo (slovenščina).

Anonimizirana različica: imena držav so nadomeščena s fiksnimi, ročno
vzdrževanimi oznakami trgov ("Trg 1", "Trg 2", ...) iz anonimizacija_drzav.py,
da ostanejo dodelitve dosledne med vsemi grafi diplomske naloge. Absolutna
števila in deleži ostanejo nespremenjeni.
"""

import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from anonimizacija_drzav import anonimiziraj_seznam

# ─────────────────────────────────────────────────────────────────────────────
# 1. PODATKI
# ─────────────────────────────────────────────────────────────────────────────
# Trgi so anonimizirani ze v izvoru (glej anonimizacija_drzav.py):
# oznaka trga, stevilo servisnih posegov, delez med vsemi posegi v %.
# Dejanska imena drzav niso del javne objave kode.

PODATKI = [
    ('Trg 1',    360,  11.8),
    ('Trg 2',    244,   8.0),
    ('Trg 3',    230,   7.6),
    ('Trg 4',    174,   5.7),
    ('Trg 5',    133,   4.4),
    ('Trg 6',    126,   4.1),
    ('Trg 7',    110,   3.6),
    ('Trg 8',     96,   3.2),
    ('Trg 9',     94,   3.1),
    ('Trg 10',    92,   3.0),
    ('Trg 11',    86,   2.8),
    ('Trg 12',    83,   2.7),
    ('Trg 13',    81,   2.7),
    ('Trg 14',    79,   2.6),
    ('Trg 15',    66,   2.2),
]

N_SKUPAJ = 3052       # skupno število servisnih posegov (vseh 42 trgov)
N_TRGOV_SKUPAJ = 42   # skupno število trgov v celotnem naboru

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', 'rezultati', 'porazdelitev_servisnih_posegov_po_trgu_anonimizirano.png')

BLUE = '#2c6fad'   # barva stolpcev

# ─────────────────────────────────────────────────────────────────────────────
# 2. POMOŽNE FUNKCIJE – SLOVENSKA TIPOGRAFIJA
# ─────────────────────────────────────────────────────────────────────────────

def si_delez(x: float, dec: int = 1) -> str:
    """Delež z decimalno vejico: 11,8 %"""
    return f"{x:.{dec}f}".replace('.', ',') + ' %'   # nedeljivi presledek pred %

def si_stevilo(n: int) -> str:
    """Celo število s piko kot tisočico: 3.052"""
    return f"{int(n):,}".replace(',', '.')

# ─────────────────────────────────────────────────────────────────────────────
# 3. IZRIS
# ─────────────────────────────────────────────────────────────────────────────

def plot_porazdelitev(podatki: list[tuple[str, int, float]], n_skupaj: int,
                       n_trgov_skupaj: int, output: str) -> None:
    podatki = sorted(podatki, key=lambda vrstica: vrstica[2], reverse=True)
    podatki = podatki[::-1]   # obrni, da je največji delež na vrhu grafa

    trgi    = [vrstica[0] for vrstica in podatki]
    stevila = [vrstica[1] for vrstica in podatki]
    delezi  = [vrstica[2] for vrstica in podatki]

    n = len(podatki)
    y = list(range(n))

    _, ax = plt.subplots(figsize=(9, max(4, n * 0.4 + 1)))

    bars = ax.barh(y, delezi, height=0.6, color=BLUE, edgecolor='white')

    ax.set_yticks(y)
    ax.set_yticklabels(trgi, fontsize=10)

    # Nalepka ob vsakem stolpcu: delež in absolutno število, npr. "11,8 % (360)"
    for bar, delez, stevilo in zip(bars, delezi, stevila):
        ax.text(
            bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
            f'{si_delez(delez)} ({si_stevilo(stevilo)})',
            va='center', ha='left', fontsize=9, color='#333333',
        )

    ax.set_xlim(0, max(delezi) * 1.2)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: si_delez(x, dec=0)))
    ax.set_xlabel('Delež (%)', fontsize=11, labelpad=8)

    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='both', labelsize=10)

    ax.text(
        1, -0.07 - 0.012 * n,
        f'n = {si_stevilo(n_skupaj)} (prvih {n} od {n_trgov_skupaj} trgov)',
        transform=ax.transAxes, ha='right', fontsize=9, color='#666666',
    )

    plt.tight_layout()
    plt.savefig(output, dpi=300, bbox_inches='tight')
    plt.show()
    print(f'Shranjeno: {output}')

# ─────────────────────────────────────────────────────────────────────────────
# 4. ZAGON
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    trgi = anonimiziraj_seznam(vrstica[0] for vrstica in PODATKI)
    podatki_anonimni = [
        (trg, stevilo, delez)
        for trg, (_, stevilo, delez) in zip(trgi, PODATKI)
    ]
    plot_porazdelitev(podatki_anonimni, N_SKUPAJ, N_TRGOV_SKUPAJ, OUTPUT)
