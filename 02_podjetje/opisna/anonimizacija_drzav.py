"""
Zemljevid dejanskih imen držav (trgov) v anonimizirana imena
("Trg 1", "Trg 2", ...) za uporabo v javno objavljenih grafih
(diplomska naloga).

Zemljevid je ROČNO VZDRŽEVAN in FIKSEN: ko se državi enkrat dodeli
anonimizirano ime, to ime ostane enako v vseh prihodnjih vizualizacijah
(tudi če se doda nova država ali se spremeni TOP_N), da so grafi med
seboj primerljivi in dosledni.

Spodnjih 15 držav je preslikanih v vrstnem redu padajočega deleža
servisnih posegov (glej porazdelitev_servisnih_posegov_po_drzavi.py).

Ko se v podatkih pojavi nova, še ne preslikana država, jo funkcija
anonimiziraj_drzavo() samodejno doda na konec seznama ANONIMNA_IMENA
in izpiše opozorilo – takrat je treba to novo dodeljitev prekopirati
nazaj v DRZAVA_V_ANONIM spodaj, da ostane trajna.
"""

# Zaporedje anonimiziranih imen, ki se dodeljujejo po vrsti (Trg 1, Trg 2, ...).
ANONIMNA_IMENA = [f'Trg {i}' for i in range(1, 43)]   # do 42 (celoten nabor držav)

# Fiksna preslikava: dejansko ime države -> anonimizirano ime.
# POMEMBNO: ko se doda nova država, jo dopiši SEM (ne samo v izpis),
# da se dodeljeno ime ne spremeni med poganjanji/skriptami.
DRZAVA_V_ANONIM: dict[str, str] = {
    # V javni objavi kode je preslikava namenoma PRAZNA.
    # Diplomska naloga trge prikazuje anonimizirano ("Trg 1" ... "Trg 15");
    # objava dejanskih imen držav bi grafikon 5 razkrila nazaj.
    # Ob ponovnem zagonu funkcija anonimiziraj_drzavo() imena dodeli sama,
    # po padajocem delezu servisnih posegov, kar da isti vrstni red kot v
    # nalogi. Za trajno preslikavo se vnosi zapisejo sem (lokalno, ne v repo).
    # 'Dejansko ime drzave': 'Trg 1',
}

# Posebni, nespremenljivi vnosi, ki niso prava država in se ne anonimizirajo.
NEANONIMIZIRANO = {'Preostale države', 'Drugo'}


def anonimiziraj_drzavo(ime: str) -> str:
    """Vrne anonimizirano ime države; nespremenljive posebne vrednosti pusti pri miru."""
    if ime in NEANONIMIZIRANO:
        return ime

    if ime not in DRZAVA_V_ANONIM:
        naslednji_indeks = len(DRZAVA_V_ANONIM)
        if naslednji_indeks < len(ANONIMNA_IMENA):
            anonim = ANONIMNA_IMENA[naslednji_indeks]
        else:
            anonim = f'Trg {naslednji_indeks + 1}'
        DRZAVA_V_ANONIM[ime] = anonim
        print(
            f"[anonimizacija_drzav] Nova država '{ime}' -> '{anonim}'. "
            f"Dodaj ta vnos v DRZAVA_V_ANONIM v anonimizacija_drzav.py, "
            f"da ostane dodelitev trajna."
        )

    return DRZAVA_V_ANONIM[ime]


def anonimiziraj_seznam(imena) -> list[str]:
    """Anonimizira seznam/serijo imen držav, ohranja vrstni red."""
    return [anonimiziraj_drzavo(ime) for ime in imena]
