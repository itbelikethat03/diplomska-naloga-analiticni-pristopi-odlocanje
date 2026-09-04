"""
Skupne nastavitve za dostop do baze servis_db in rekonstrukcija stolpca
`kategorija`, ki ga trenutna shema baze nima več.

POVEZAVA
    Nastavitve se berejo iz datoteke .env v tej mapi (SERVIS_DB_USER,
    SERVIS_DB_PASSWORD, SERVIS_DB_HOST, SERVIS_DB_PORT, SERVIS_DB_NAME),
    da geslo ni zapisano v skriptah. Gonilnik je PyMySQL, ker se
    mysql-connector-python 9.x na tem sistemu ob connect() sesuje
    (access violation 0xC0000005).

REKONSTRUKCIJA KATEGORIJE
    Starejša verzija baze je imela stolpec analiza_reklamacije.kategorija
    s 6 kategorijami napak. Trenutna shema ima samo vrsta_napake:
      - novi zapisi (od ~2019): kategorija je prefiks pred '<br>',
      - starejši zapisi (2013-2019): prosto besedilo ('okvara ročnika' ...).
    Preslikava legacy vrednosti spodaj je kalibrirana proti zgodovinskim
    rezultatom (fotona_backtest_kategorije.csv iz prejšnjih zagonov) in se
    za leta 2017, 2018 in 2019 ujema NA REKLAMACIJO NATANČNO za vseh
    6 kategorij — gre torej za rekonstrukcijo, ne za približek.
"""

import os

_MAPA = os.path.dirname(os.path.abspath(__file__))

# Datoteka .env se išče najprej v korenu repozitorija, nato v tej mapi.
_ENV_PATH = next(
    (p for p in (os.path.join(_MAPA, os.pardir, '.env'),
                 os.path.join(_MAPA, '.env'))
     if os.path.exists(p)),
    os.path.join(_MAPA, os.pardir, '.env'),
)


def _nalozi_env(path: str = _ENV_PATH) -> None:
    """Preprost bralnik .env — brez zunanjih odvisnosti."""
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


_nalozi_env()

DB_USER     = os.environ.get('SERVIS_DB_USER', 'root')
DB_PASSWORD = os.environ.get('SERVIS_DB_PASSWORD', '')
DB_HOST     = os.environ.get('SERVIS_DB_HOST', 'localhost')
DB_PORT     = int(os.environ.get('SERVIS_DB_PORT', '3306'))
DB_NAME     = os.environ.get('SERVIS_DB_NAME', 'servis_db')

# Za skripte, ki gradijo URL same (vizualizacije)
DB = dict(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT, db=DB_NAME)


def get_engine():
    """SQLAlchemy engine s PyMySQL gonilnikom."""
    from sqlalchemy import create_engine
    return create_engine(
        f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        '?charset=utf8mb4'
    )


# Podpoizvedba, ki tabeli analiza_reklamacije doda rekonstruiran stolpec
# `kategorija`. V SQL jo uporabiš namesto imena tabele:
#     FROM {ANALIZA_REKLAMACIJE_KAT} ar
# Zapisi, ki jih ni mogoče uvrstiti (716 NULL vrednosti), dobijo NULL —
# obstoječi filtri "kategorija IS NOT NULL" jih izločijo enako kot prej
# vrednost 'Nerazporejeno'.
ANALIZA_REKLAMACIJE_KAT = """(
    SELECT ar0.*,
        CASE
            WHEN ar0.vrsta_napake LIKE 'Neskladnost opti%' THEN 'Neskladnost optičnih komponent'
            WHEN ar0.vrsta_napake LIKE 'Neskladnost elektronskih%' THEN 'Neskladnost elektronskih komponent'
            WHEN ar0.vrsta_napake LIKE 'Neskladnost mehanskih%' THEN 'Neskladnost mehanskih komponent'
            WHEN ar0.vrsta_napake LIKE 'Neskladnost hladilnega%' THEN 'Neskladnost hladilnega sistema'
            WHEN ar0.vrsta_napake LIKE 'Neskladnost enote za sprej%' THEN 'Neskladnost enote za sprej'
            WHEN ar0.vrsta_napake LIKE 'Ni tehni%' THEN 'Ni tehnična napaka'
            WHEN ar0.vrsta_napake IN ('drugo', 'napaka pakiranja') THEN 'Ni tehnična napaka'
            WHEN ar0.vrsta_napake IN ('okvara pršila', 'okvara kompresorja',
                                      'okvara polnilca') THEN 'Neskladnost enote za sprej'
            WHEN ar0.vrsta_napake = 'okvara hladilnega sistema' THEN 'Neskladnost hladilnega sistema'
            WHEN ar0.vrsta_napake IN ('okvara ročnika', 'neustrezen del', 'izrabljen del',
                                      'poškodba ohišja', 'neustrezna zaščitna očala')
                THEN 'Neskladnost mehanskih komponent'
            WHEN ar0.vrsta_napake IN ('poškodba optike', 'poškodba fibra', 'okvara laserja',
                                      'okvara artikulirane roke', 'poškodba laserske palice',
                                      'okvara bliskavke', 'poškodba laserskega zrcala',
                                      'okvara skenerja', 'neustrezen energometer')
                THEN 'Neskladnost optičnih komponent'
            WHEN ar0.vrsta_napake IN ('okvara napajalnika', 'okvara PFM', 'okvara krmilnika',
                                      'okvara kontrolerja', 'okvara tiskanega vezja',
                                      'okvara nožne stopalke', 'okvara prikazovalnika',
                                      'napaka FW', 'okvara tipkovnice')
                THEN 'Neskladnost elektronskih komponent'
            ELSE NULL
        END AS kategorija
    FROM analiza_reklamacije ar0
)"""
