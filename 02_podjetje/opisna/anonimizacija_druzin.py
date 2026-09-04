"""
Zemljevid dejanskih imen družin izdelkov v anonimizirana imena
("Naprava A", "Naprava B", ...) za uporabo v javno objavljenih grafih
(diplomska naloga).

Zemljevid je ROČNO VZDRŽEVAN in FIKSEN: ko se družini enkrat dodeli
anonimizirano ime, to ime ostane enako v vseh prihodnjih vizualizacijah
(tudi če se doda nova družina ali se spremeni TOP_N), da so grafi med
seboj primerljivi in dosledni.

Ko se v podatkih pojavi nova, še ne preslikana družina, jo funkcija
anonimiziraj_druzino() samodejno doda na konec seznama ANONIMNA_IMENA
in izpiše opozorilo – takrat je treba to novo dodeljitev prekopirati
nazaj v DRUZINA_V_ANONIM spodaj, da ostane trajna.
"""

# Zaporedje anonimiziranih imen, ki se dodeljujejo po vrsti (A, B, C, ...).
# Ko zmanjka črk, se nadaljuje z AA, AB, ...
ANONIMNA_IMENA = [
    'Naprava A', 'Naprava B', 'Naprava C', 'Naprava D', 'Naprava E',
    'Naprava F', 'Naprava G', 'Naprava H', 'Naprava I', 'Naprava J',
    'Naprava K', 'Naprava L', 'Naprava M', 'Naprava N', 'Naprava O',
]

# Fiksna preslikava: dejansko ime družine -> anonimizirano ime.
# POMEMBNO: ko se doda nova družina, jo dopiši SEM (ne samo v izpis),
# da se dodeljeno ime ne spremeni med poganjanji/skriptami.
DRUZINA_V_ANONIM: dict[str, str] = {
    # 'Dejansko ime družine': 'Naprava A',
}

# Posebni, nespremenljivi vnosi, ki niso prava družina in se ne anonimizirajo.
NEANONIMIZIRANO = {'Preostale družine', 'Drugo'}


def anonimiziraj_druzino(ime: str) -> str:
    """Vrne anonimizirano ime družine; nespremenljive posebne vrednosti pusti pri miru."""
    if ime in NEANONIMIZIRANO:
        return ime

    if ime not in DRUZINA_V_ANONIM:
        naslednji_indeks = len(DRUZINA_V_ANONIM)
        if naslednji_indeks < len(ANONIMNA_IMENA):
            anonim = ANONIMNA_IMENA[naslednji_indeks]
        else:
            anonim = f'Naprava {naslednji_indeks + 1}'
        DRUZINA_V_ANONIM[ime] = anonim
        print(
            f"[anonimizacija_druzin] Nova družina '{ime}' -> '{anonim}'. "
            f"Dodaj ta vnos v DRUZINA_V_ANONIM v anonimizacija_druzin.py, "
            f"da ostane dodelitev trajna."
        )

    return DRUZINA_V_ANONIM[ime]


def anonimiziraj_seznam(imena) -> list[str]:
    """Anonimizira seznam/serijo imen družin, ohranja vrstni red."""
    return [anonimiziraj_druzino(ime) for ime in imena]
