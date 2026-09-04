"""
ETL pipeline: CSV → normalizirana MySQL baza
Zahteve:
    pip install pandas sqlalchemy pymysql

MySQL Workbench — pred zagonom skripte:
    CREATE DATABASE servis_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"""

import pandas as pd
import re
from sqlalchemy import create_engine, text, Integer, BigInteger, SmallInteger, String, Date, Text, Float

# --- NASTAVITVE ---------------------------------------------------------------
MYSQL_USER     = 'root'
MYSQL_PASSWORD = '***'
MYSQL_HOST     = 'localhost'
MYSQL_PORT     = 3306
MYSQL_DB       = 'servis_db'

SP_CSV  = r'D:\Diplomska\Servis podatkiu\pregled_servisnih_posegov.csv'
REK_CSV = r'D:\Diplomska\Servis podatkiu\pregled_reklamacij.csv'

# --- POVEZAVA -----------------------------------------------------------------
ENGINE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    f"?charset=utf8mb4"
)
engine = create_engine(ENGINE_URL, echo=False)

# Test povezave
try:
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    print("Povezava z MySQL uspešna")
except Exception as e:
    print(f"Napaka pri povezavi: {e}")
    print("   Preveriti je treba: MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DB")
    exit(1)

# --- POMOZNE FUNKCIJE ---------------------------------------------------------
def clean_str(s):
    if pd.isna(s): return None
    s = str(s).strip()
    return s if s else None

def clean_date(s):
    if pd.isna(s): return None
    s = str(s).strip()
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    return None

def clean_bool(s):
    if pd.isna(s): return None
    s = str(s).strip().upper()
    if s.startswith('DA'): return 1
    if s.startswith('NE'): return 0
    return None

def strip_num_prefix(s):
    if pd.isna(s): return None
    s = str(s).strip()
    m = re.match(r'^\d+\s+(.+)$', s)
    return m.group(1).strip() if m else s

def strip_num_prefix_rek(s):
    if pd.isna(s): return None
    s = str(s).strip()
    m = re.match(r'^\d+\s+(.+)$', s)
    return m.group(1).strip() if m else s

def parse_podjetje_id(raw):
    if pd.isna(raw): return None, None
    raw = str(raw).strip()
    m = re.match(r'^(\d+)\s+(.+)$', raw)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, raw

def split_multi(val):
    if pd.isna(val): return []
    val = str(val).strip()
    val = re.sub(r'<br>', ',', val, flags=re.IGNORECASE)
    parts = re.split(r',', val)
    return [p.strip() for p in parts if p.strip() and p.strip() not in ('-', '0', '')]

def safe_int(x):
    try: return int(float(x))
    except: return None

def save(name, df, dtype=None):
    """Shrani DataFrame v MySQL tabelo."""
    if df.empty:
        print(f"   OPOZORILO: {name}: prazna tabela, preskočena")
        return
    df = df.where(pd.notnull(df), None)
    kwargs = {'index': False, 'if_exists': 'replace', 'chunksize': 1000}
    if dtype:
        kwargs['dtype'] = dtype
    try:
        with engine.begin() as conn:
            df.to_sql(name, conn, **kwargs)
        print(f"   {name}: {len(df)} vrstic")
    except Exception as e:
        print(f"   NAPAKA pri {name}: {e}")
        for col in df.select_dtypes(include='object').columns:
            mx = df[col].dropna().astype(str).str.len().max()
            if pd.notna(mx) and mx:
                print(f"      {col}: max {int(mx)} znakov")
        raise

# --- BRANJE IZVORNIH DATOTEK --------------------------------------------------
print("Branje izvornih datotek")
sp  = pd.read_csv(SP_CSV,  encoding='cp1250', sep=';', on_bad_lines='skip')
rek = pd.read_csv(REK_CSV, encoding='cp1250', sep=';', on_bad_lines='skip', low_memory=False)
print(f"   Servisni posegi: {sp.shape[0]} vrstic")
print(f"   Reklamacije:     {rek.shape[0]} vrstic")

# --- 1. ISKALNIŠKE (LOOKUP) TABELE --------------------------------------------
print("\nLookup tabele")

def build_lookup(series_list, strip_fn=None):
    vals = set()
    for s in series_list:
        v = strip_fn(s) if strip_fn else clean_str(s)
        if v: vals.add(v)
    df = pd.DataFrame(sorted(vals), columns=['naziv'])
    df.insert(0, 'id', range(1, len(df) + 1))
    return df

df_status_posega   = build_lookup(sp['Status'].dropna(), strip_num_prefix)
df_status_posega.columns = ['status_posega_id', 'naziv']

df_vrsta_popravila = build_lookup(sp['Vrsta popravila'].dropna(), strip_num_prefix)
df_vrsta_popravila.columns = ['vrsta_popravila_id', 'naziv']

df_status_rek      = build_lookup(rek['Status reklamacije'].dropna(), strip_num_prefix_rek)
df_status_rek.columns = ['status_reklamacije_id', 'naziv']

df_vrsta_rek       = build_lookup(rek['Vrsta reklamacije'].dropna())
df_vrsta_rek.columns = ['vrsta_reklamacije_id', 'naziv']

vrsta_pred_vals    = sorted(sp['Vrsta predmeta'].dropna().unique().tolist())
df_vrsta_pred      = pd.DataFrame({
    'vrsta_predmeta_id': range(1, len(vrsta_pred_vals) + 1),
    'oznaka': [str(int(float(v))) for v in vrsta_pred_vals],
    'opis': [None] * len(vrsta_pred_vals)
})

def norm_nacin(s):
    if pd.isna(s): return None
    return str(s).strip().lower()

df_nacin = build_lookup(rek['Način prejema'].dropna(), norm_nacin)
df_nacin.columns = ['nacin_prejema_id', 'naziv']
nacin_map = {r['naziv']: r['nacin_prejema_id'] for _, r in df_nacin.iterrows()}

# Lookup maps
status_posega_map = {r['naziv']: r['status_posega_id']      for _, r in df_status_posega.iterrows()}
vrsta_pop_map     = {r['naziv']: r['vrsta_popravila_id']     for _, r in df_vrsta_popravila.iterrows()}
status_rek_map    = {r['naziv']: r['status_reklamacije_id']  for _, r in df_status_rek.iterrows()}
vrsta_rek_map     = {r['naziv']: r['vrsta_reklamacije_id']   for _, r in df_vrsta_rek.iterrows()}
vrsta_pred_map    = {r['oznaka']: r['vrsta_predmeta_id']     for _, r in df_vrsta_pred.iterrows()}

# --- 2. PODJETJA --------------------------------------------------------------
print("\nTabela podjetje")
podjetja = {}

for _, r in rek.iterrows():
    pid = safe_int(r['Šifra pritožnika'])
    if pid is None: continue
    naziv  = clean_str(r['Naziv pritožnika'])
    drzava = clean_str(r['Država pritožnika'])
    if pid not in podjetja:
        podjetja[pid] = {'naziv': naziv, 'drzava': drzava}
    elif drzava and not podjetja[pid]['drzava']:
        podjetja[pid]['drzava'] = drzava

for col in ['Naročnik', 'Prejemnik']:
    for _, r in sp.iterrows():
        pid, naziv = parse_podjetje_id(r[col])
        if pid is None: continue
        if pid not in podjetja:
            podjetja[pid] = {'naziv': naziv, 'drzava': None}

df_podjetja = pd.DataFrame([
    {'podjetje_id': k, 'naziv': v['naziv'], 'drzava': v['drzava']}
    for k, v in sorted(podjetja.items())
])

# --- 3. ZAPOSLENI -------------------------------------------------------------
print("\nTabela zaposleni")
zaposleni = {}

def add_zaposleni(sifra, naziv_raw):
    sifra = safe_int(sifra)
    if sifra is None: return
    naziv = clean_str(naziv_raw)
    if sifra not in zaposleni:
        if naziv and ' ' in naziv:
            parts = naziv.strip().split(' ', 1)
            ime, priimek = parts[0], parts[1]
        else:
            ime, priimek = None, naziv
        zaposleni[sifra] = {'ime': ime, 'priimek': priimek}
    else:
        existing = zaposleni[sifra]
        if naziv and ' ' in naziv and existing['ime'] is None:
            parts = naziv.strip().split(' ', 1)
            zaposleni[sifra]['ime']     = parts[0]
            zaposleni[sifra]['priimek'] = parts[1]

for _, r in sp.iterrows():
    add_zaposleni(r['Šifra ref.'], r['Naziv referenta'])
for _, r in rek.iterrows():
    add_zaposleni(r['Šif.odg.os. za reš.'], r['Naziv odg.os. za rešitev'])
    add_zaposleni(r['Šifra prej.'],          r['Naziv prejemnika'])
    add_zaposleni(r['Šifra predst. IK'],     r['Naziv predstavnika IK'])

df_zaposleni_full = pd.DataFrame([
    {'zaposleni_id': idx + 1, 'sifra_iz_sistema': k,
     'ime': v['ime'], 'priimek': v['priimek']}
    for idx, (k, v) in enumerate(sorted(zaposleni.items()))
])
zap_map = {int(r['sifra_iz_sistema']): r['zaposleni_id'] for _, r in df_zaposleni_full.iterrows()}

# V bazo se zapiše samo anonimni identifikator (GDPR: brez imen in šifer)
df_zaposleni = df_zaposleni_full[['zaposleni_id']].copy()

# --- 4. NADREJENI IZDELKI -----------------------------------------------------
print("\nTabela nadrejen_izdelek")
nadr = {}
for _, r in rek.iterrows():
    ident = clean_str(r['Ident nadr.izdelka'])
    if not ident: continue
    if ident not in nadr:
        nadr[ident] = {
            'ident_nadr_izdelka': ident,
            'naziv_nadr_izdelka': clean_str(r['Naziv nadr.izdelka']),
            'druzina_izdelka':    clean_str(r['Družina izdelka']),
        }
df_nadr = pd.DataFrame(list(nadr.values()))

# --- 5. PREDMETI --------------------------------------------------------------
print("\nTabela predmet")
predmeti = {}

def add_predmet(sifra, naziv, vrsta=None, nadr_ident=None):
    key = clean_str(str(sifra)) if pd.notna(sifra) else None
    if not key: return
    vrsta_str = str(int(float(vrsta))) if pd.notna(vrsta) else None
    nadr_key = clean_str(str(nadr_ident)) if pd.notna(nadr_ident) else None
    if key not in predmeti:
        predmeti[key] = {
            'sifra_predmeta':     key,
            'naziv_predmeta':     clean_str(naziv),
            'vrsta_predmeta_id':  vrsta_pred_map.get(vrsta_str),
            'ident_nadr_izdelka': nadr_key,
        }
    else:
        if nadr_key and predmeti[key]['ident_nadr_izdelka'] is None:
            predmeti[key]['ident_nadr_izdelka'] = nadr_key
        if vrsta_str and predmeti[key]['vrsta_predmeta_id'] is None:
            predmeti[key]['vrsta_predmeta_id'] = vrsta_pred_map.get(vrsta_str)

for _, r in sp.iterrows():
    add_predmet(r['Šifra predmeta'], r['Naziv predmeta'], r.get('Vrsta predmeta'))
for _, r in rek.iterrows():
    add_predmet(r['Ident pozicije'], r['Naziv pozicije'],
                nadr_ident=r.get('Ident nadr.izdelka'))
df_predmeti = pd.DataFrame(list(predmeti.values()))

# --- 6. TUJI KONTAKTI ---------------------------------------------------------
print("\nTabela tuji_kontakt")
kontakti_seen = set()
kontakti = []
kontakt_id = 1
kontakt_key_map = {}  # (pid, ime, email) -> kontakt_id, za natančno preslikavo reklamacija -> njen kontakt
kontakt_psevdonim_map = {}  # kontakt_id -> realni podatki; ostane samo v pomnilniku, v bazo se ne zapiše

for _, r in rek.drop_duplicates(subset=['Šifra pritožnika','Kont.oseba ime','Kont.oseba E-naslov']).iterrows():
    pid   = safe_int(r['Šifra pritožnika'])
    if pid is None: continue
    ime   = clean_str(r['Kont.oseba ime'])
    email = clean_str(r['Kont.oseba E-naslov'])
    tel   = clean_str(r['Kont.oseba Telefon'])
    key   = (pid, ime, email)
    # Deduplikacija se izvede nad izvornimi (realnimi) vrednostmi, šele nato
    # se unikatni kontaktni osebi dodeli sintetični identifikator.
    if key in kontakti_seen: continue
    kontakti_seen.add(key)
    # V bazo se zapiše samo anonimni identifikator kontaktne osebe
    # (GDPR: brez imen, e-naslovov in telefonskih številk).
    kontakt_psevdonim_map[kontakt_id] = {'ime': ime, 'email': email, 'telefon': tel}
    kontakti.append({'kontakt_id': kontakt_id, 'podjetje_id': pid,
                     'kont_oseba_ime': f"Kontakt_{kontakt_id}",
                     'kont_oseba_email': None,
                     'kont_oseba_telefon': None})
    kontakt_key_map[key] = kontakt_id
    kontakt_id += 1
df_kontakti = pd.DataFrame(kontakti)

# --- 7. REKLAMACIJE -----------------------------------------------------------
print("\nTabela reklamacija")
REK_DEDUP = rek.drop_duplicates(subset=['Številka reklamacije'])

def build_rek(r):
    pid      = safe_int(r['Šifra pritožnika'])
    vrsta    = clean_str(r['Vrsta reklamacije'])
    status   = strip_num_prefix_rek(r['Status reklamacije'])
    kontakt_key = (pid, clean_str(r['Kont.oseba ime']), clean_str(r['Kont.oseba E-naslov']))
    return {
        'stevilka_reklamacije':  clean_str(r['Številka reklamacije']),
        'pritoznik_id':          pid,
        'kontakt_id':            kontakt_key_map.get(kontakt_key),
        'opis_reklamacije':      clean_str(r['Opis reklamacije']),
        'vrsta_reklamacije_id':  vrsta_rek_map.get(vrsta),
        'garancija':             clean_bool(r['Garancija']),
        'status_reklamacije_id': status_rek_map.get(status),
        'naziv_dokumenta':       clean_str(r['Naziv dokumenta']),
    }

df_rek = pd.DataFrame([build_rek(r) for _, r in REK_DEDUP.iterrows()])
df_rek = df_rek.dropna(subset=['stevilka_reklamacije'])
rek_ids = set(df_rek['stevilka_reklamacije'])
print("\nNajdaljše številke reklamacij")
print(df_rek['stevilka_reklamacije'].dropna().str.len().describe())
print(df_rek.loc[df_rek['stevilka_reklamacije'].str.len() > 20,
                 'stevilka_reklamacije'].head(20).tolist())
# --- 8. PREJEM REKLAMACIJE ----------------------------------------------------
print("\nTabela prejem_reklamacije")
prejem_seen = set()
prejemi = []
prejem_id = 1

for _, r in rek.iterrows():
    rek_id = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids: continue
    prej_id = zap_map.get(safe_int(r['Šifra prej.']))
    datum   = clean_date(r['Datum prejema'])
    nacin   = norm_nacin(r['Način prejema'])
    opis    = clean_str(r['Dodatni opis prejema'])
    key = (rek_id, prej_id, datum)
    if key in prejem_seen: continue
    prejem_seen.add(key)
    prejemi.append({'id': prejem_id, 'reklamacija_id': rek_id,
                    'prejemnik_id': prej_id, 'datum_prejema': datum,
                    'nacin_prejema_id': nacin_map.get(nacin), 'dodatni_opis_prejema': opis})
    prejem_id += 1
df_prejemi = pd.DataFrame(prejemi)

# --- 9. NEVARNOST -------------------------------------------------------------
print("\nTabela nevarnost")
nevarnost_seen = set()
nevarnosti = []

for _, r in REK_DEDUP.iterrows():
    rek_id = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids or rek_id in nevarnost_seen: continue
    ali = clean_bool(r['Ali obstaja nevarnost'])
    obr = clean_str(r['Obrazložitev odločitve o nevarnosti'])
    if ali is None and obr is None: continue
    nevarnost_seen.add(rek_id)
    nevarnosti.append({'reklamacija_id': rek_id,
                       'ali_obstaja_nevarnost': ali,
                       'obrazlozitev_nevarnosti': obr})
df_nevarnost = pd.DataFrame(nevarnosti)

# --- 10. UKREPI ---------------------------------------------------------------
print("\nTabela ukrepi")
ukrepi_seen = set()
ukrepi = []
ukrep_id = 1

for _, r in REK_DEDUP.iterrows():
    rek_id  = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids: continue
    ukrep   = clean_str(r['Ukrepi za rešitev reklamacije'])
    dodatni = clean_bool(r['Potrebni dodatni ukrepi'])
    komentar = clean_str(r['Komentar k dod.ukrep./Obrazložitev garancije'])
    datum   = clean_date(r['Datum izvedbe ukrepa'])
    if all(v is None for v in [ukrep, dodatni, komentar, datum]): continue
    key = (rek_id, ukrep, datum)
    if key in ukrepi_seen: continue
    ukrepi_seen.add(key)
    ukrepi.append({'id': ukrep_id, 'reklamacija_id': rek_id,
                   'ukrepi_za_resitev': ukrep, 'potrebni_dodatni_ukrepi': dodatni,
                   'komentar_dod_ukrep': komentar, 'datum_izvedbe_ukrepa': datum})
    ukrep_id += 1
df_ukrepi = pd.DataFrame(ukrepi)

# --- 11. ANALIZA REKLAMACIJE --------------------------------------------------
print("\nTabela analiza_reklamacije")
analize = []
analiza_id = 1

for _, r in REK_DEDUP.iterrows():
    rek_id = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids: continue
    odg    = zap_map.get(safe_int(r['Šif.odg.os. za reš.']))
    ik     = zap_map.get(safe_int(r['Šifra predst. IK']))
    d_otps = clean_date(r['Datum analize OTPS'])
    d_ik   = clean_date(r['Datum analize IK'])
    if all(v is None for v in [odg, ik, d_otps, d_ik]): continue

    ugot_raw = clean_str(r['Ugot. vzrok reklamacije'])
    if ugot_raw and '<br>' in ugot_raw:
        parts = ugot_raw.split('<br>', 1)
        ugot_bool  = clean_bool(parts[0])
        opis_vzrok = clean_str(parts[1])
    else:
        ugot_bool  = clean_bool(ugot_raw)
        opis_vzrok = clean_str(r.get('Opis ugotovljega vzroka'))

    analize.append({
        'id': analiza_id, 'reklamacija_id': rek_id,
        'odg_oseba_id': odg, 'datum_analize_otps': d_otps,
        'predstavnik_ik_id': ik, 'datum_analize_ik': d_ik,
        'predhna_analiza_ustrezna':   clean_bool(r['Predhodna analiza ustrezna?']),
        'vrsta_napake':               clean_str(r['Vrsta napake']),
        'potrebna_analiza_vrnjenega': clean_bool(r['Potrebna analiza vrnjenega dela?']),
        'ugot_vzrok_reklamacije':     ugot_bool,
        'opis_ugotovljenega_vzroka':  opis_vzrok,
    })
    analiza_id += 1
df_analize = pd.DataFrame(analize)

# --- 12. ZAKLJUCEK REKLAMACIJE ------------------------------------------------
print("\nTabela zakljucek_reklamacije")
zakljucki = []
for _, r in REK_DEDUP.iterrows():
    rek_id = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids: continue
    d_zakl = clean_date(r['Datum zaklj. rekl.'])
    d_dn   = clean_date(r['Datum zaprtja DN'])
    if d_zakl is None and d_dn is None: continue
    zakljucki.append({'reklamacija_id': rek_id,
                      'datum_zakljucka_rekl': d_zakl,
                      'datum_zaprtja_dn': d_dn})
df_zakljucki = pd.DataFrame(zakljucki)

# --- 13. REKLAMACIJA POZICIJA -------------------------------------------------
print("\nTabela reklamacija_pozicija")
pozicije = []
pozicija_id = 1
pozicija_map = {}

for _, r in rek.iterrows():
    rek_id = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids: continue
    sifra = clean_str(str(r['Ident pozicije'])) if pd.notna(r['Ident pozicije']) else None
    kol   = r['Količina pozicije'] if pd.notna(r['Količina pozicije']) else None
    key   = (rek_id, sifra)
    if key not in pozicija_map:
        pozicija_map[key] = pozicija_id
        pozicije.append({'pozicija_id': pozicija_id, 'reklamacija_id': rek_id,
                         'sifra_predmeta': sifra, 'kolicina': kol})
        pozicija_id += 1
df_pozicije = pd.DataFrame(pozicije)

# --- 14. SERIJSKA STEVILKA (REK) ----------------------------------------------
print("\nTabela serijska_stevilka")
ser_rek = []
ser_rek_id = 1

for _, r in rek.iterrows():
    rek_id = clean_str(r['Številka reklamacije'])
    if not rek_id or rek_id not in rek_ids: continue
    sifra  = clean_str(str(r['Ident pozicije'])) if pd.notna(r['Ident pozicije']) else None
    pos_id = pozicija_map.get((rek_id, sifra))
    if pos_id is None: continue
    for sn in split_multi(r['Ser. št. pozicije']):
        ser_rek.append({'id': ser_rek_id, 'pozicija_id': pos_id, 'serijska_st': sn})
        ser_rek_id += 1
df_ser_rek = pd.DataFrame(ser_rek)

# --- 15. SERVISNI POSEG -------------------------------------------------------
print("\nTabela servisni_poseg")
sp_header = sp.drop_duplicates(subset=['Dokument'])
posegi = []

for _, r in sp_header.iterrows():
    dok = clean_str(r['Dokument'])
    if not dok: continue
    narc_id, _ = parse_podjetje_id(r['Naročnik'])
    prej_id, _ = parse_podjetje_id(r['Prejemnik'])
    status_raw = strip_num_prefix(r['Status'])
    vp_raw     = strip_num_prefix(r['Vrsta popravila'])
    posegi.append({
        'dokument':           dok,
        'status_posega_id':   status_posega_map.get(status_raw),
        'narocnik_id':        narc_id,
        'prejemnik_id':       prej_id,
        'program':            clean_str(str(r['Program'])) if pd.notna(r['Program']) else None,
        'sm':                 clean_str(str(r['SM'])) if pd.notna(r['SM']) else None,
        'delovni_nalog':      clean_str(str(r['Delovni nalog'])),
        'vrsta_popravila_id': vrsta_pop_map.get(vp_raw),
        'referent_id':        zap_map.get(safe_int(r['Šifra ref.'])),
        'datum_prevzema':     clean_date(r['Datum prevzema']),
        'rok_izvedbe':        clean_date(r['Rok izvedbe']),
        'datum_resitve':      clean_date(r['Datum rešitve']),
    })
df_posegi = pd.DataFrame(posegi)


print("\nTabela servisni_poseg_izpeljani")
izpeljani = []
izp_seen = set()
izp_id = 1
for _, r in sp_header.iterrows():
    dok = clean_str(r['Dokument'])
    if not dok: continue
    for d in split_multi(r['Izpeljani dokument']):
        key = (dok, d)
        if key in izp_seen: continue
        izp_seen.add(key)
        izpeljani.append({'id': izp_id, 'dokument_id': dok, 'izpeljani_dokument': d})
        izp_id += 1
df_izpeljani = pd.DataFrame(izpeljani)
# --- 16. POSEG → REKLAMACIJA (M:N) --------------------------------------------
print("\nVezna tabela poseg_reklamacija")
poseg_rek = []
pr_seen = set()

for _, r in sp.iterrows():
    dok = clean_str(r['Dokument'])
    if not dok: continue
    vezni_raw = clean_str(r['Vezni dokument'])
    if not vezni_raw: continue
    for srn in split_multi(vezni_raw):
        if srn in rek_ids:
            key = (dok, srn)
            if key not in pr_seen:
                pr_seen.add(key)
                poseg_rek.append({'dokument_id': dok, 'reklamacija_id': srn})
df_poseg_rek = pd.DataFrame(poseg_rek)

# --- 17. SERVISNI POSEG POSTAVKA ----------------------------------------------
print("\nTabela servisni_poseg_postavka")
postavke = []
postavka_id = 1
postavka_map = {}

for _, r in sp.iterrows():
    dok   = clean_str(r['Dokument'])
    if not dok: continue
    sifra = clean_str(str(r['Šifra predmeta'])) if pd.notna(r['Šifra predmeta']) else None
    kol   = r['Količina'] if pd.notna(r['Količina']) else None
    tekst = clean_str(r['Tekst'])
    key   = (dok, sifra)
    if key not in postavka_map:
        postavka_map[key] = postavka_id
        postavke.append({'id': postavka_id, 'dokument_id': dok,
                         'sifra_predmeta': sifra, 'kolicina': kol, 'tekst': tekst})
        postavka_id += 1
df_postavke = pd.DataFrame(postavke)

# --- 18. SERVISNI POSEG SERIJSKA ----------------------------------------------
print("\nTabela servisni_poseg_serijska")
ser_sp = []
ser_sp_id = 1

for _, r in sp.iterrows():
    dok   = clean_str(r['Dokument'])
    if not dok: continue
    sifra = clean_str(str(r['Šifra predmeta'])) if pd.notna(r['Šifra predmeta']) else None
    post_id = postavka_map.get((dok, sifra))
    if post_id is None: continue
    for sn in split_multi(r['Serijska št.']):
        ser_sp.append({'id': ser_sp_id, 'postavka_id': post_id, 'serijska_st': sn})
        ser_sp_id += 1
df_ser_sp = pd.DataFrame(ser_sp)

# --- 19. DEFINICIJE PODATKOVNIH TIPOV -----------------------------------------
# Ključi kot VARCHAR (TEXT ne more biti ključ), sintetični IDji kot INTEGER/BIGINT,
# logične vrednosti kot TINYINT (SmallInteger), datumi začasno kot VARCHAR(10),
# nato pretvorjeni v DATE z ALTER TABLE (zanesljiva pretvorba 'YYYY-MM-DD' -> DATE).
dtypes = {
    'nacin_prejema_lookup':       {'nacin_prejema_id': Integer(), 'naziv': String(100)},
    'vrsta_predmeta_lookup':     {'vrsta_predmeta_id': Integer(), 'oznaka': String(20), 'opis': String(255)},
    'vrsta_reklamacije_lookup':  {'vrsta_reklamacije_id': Integer(), 'naziv': String(255)},
    'status_reklamacije_lookup': {'status_reklamacije_id': Integer(), 'naziv': String(255)},
    'status_posega_lookup':      {'status_posega_id': Integer(), 'naziv': String(255)},
    'vrsta_popravila_lookup':    {'vrsta_popravila_id': Integer(), 'naziv': String(255)},
    'podjetje':                  {'podjetje_id': BigInteger(), 'naziv': String(255), 'drzava': String(100)},
    'zaposleni':                 {'zaposleni_id': Integer()},
    'nadrejen_izdelek':          {'ident_nadr_izdelka': String(100), 'naziv_nadr_izdelka': String(500), 'druzina_izdelka': String(255)},
    'predmet':                   {'sifra_predmeta': String(50), 'naziv_predmeta': String(255), 'vrsta_predmeta_id': Integer(), 'ident_nadr_izdelka': String(100)},
    'tuji_kontakt':              {'kontakt_id': Integer(), 'podjetje_id': BigInteger(), 'kont_oseba_ime': String(255), 'kont_oseba_email': String(255), 'kont_oseba_telefon': String(50)},
    'reklamacija':               {'stevilka_reklamacije': String(255), 'pritoznik_id': BigInteger(), 'kontakt_id': Integer(), 'opis_reklamacije': Text(), 'vrsta_reklamacije_id': Integer(), 'garancija': SmallInteger(), 'status_reklamacije_id': Integer(), 'naziv_dokumenta': String(255)},
    'prejem_reklamacije':        {'id': Integer(), 'reklamacija_id': String(255), 'prejemnik_id': Integer(), 'datum_prejema': String(10), 'nacin_prejema_id': Integer(), 'dodatni_opis_prejema': Text()},
    'nevarnost':                 {'reklamacija_id': String(255), 'ali_obstaja_nevarnost': SmallInteger(), 'obrazlozitev_nevarnosti': Text()},
    'ukrepi':                    {'id': Integer(), 'reklamacija_id': String(255), 'ukrepi_za_resitev': Text(), 'potrebni_dodatni_ukrepi': SmallInteger(), 'komentar_dod_ukrep': Text(), 'datum_izvedbe_ukrepa': String(10)},
    'analiza_reklamacije':       {'id': Integer(), 'reklamacija_id': String(255), 'odg_oseba_id': Integer(), 'datum_analize_otps': String(10), 'predstavnik_ik_id': Integer(), 'datum_analize_ik': String(10), 'predhna_analiza_ustrezna': SmallInteger(), 'vrsta_napake': String(255), 'potrebna_analiza_vrnjenega': SmallInteger(), 'ugot_vzrok_reklamacije': SmallInteger(), 'opis_ugotovljenega_vzroka': Text()},
    'zakljucek_reklamacije':     {'reklamacija_id': String(255), 'datum_zakljucka_rekl': String(10), 'datum_zaprtja_dn': String(10)},
    'reklamacija_pozicija':      {'pozicija_id': Integer(), 'reklamacija_id': String(255), 'sifra_predmeta': String(50), 'kolicina': Float()},
    'serijska_stevilka':         {'id': Integer(), 'pozicija_id': Integer(), 'serijska_st': String(100)},
    'servisni_poseg':            {'dokument': String(50), 'status_posega_id': Integer(), 'narocnik_id': BigInteger(), 'prejemnik_id': BigInteger(), 'program': String(100), 'sm': String(100), 'delovni_nalog': String(100), 'vrsta_popravila_id': Integer(), 'referent_id': Integer(), 'datum_prevzema': String(10), 'rok_izvedbe': String(10), 'datum_resitve': String(10)},
    'servisni_poseg_izpeljani': {'id': Integer(), 'dokument_id': String(50), 'izpeljani_dokument': String(255)},
    'poseg_reklamacija':         {'dokument_id': String(50), 'reklamacija_id': String(255)},
    'servisni_poseg_postavka':   {'id': Integer(), 'dokument_id': String(50), 'sifra_predmeta': String(50), 'kolicina': String(50), 'tekst': Text()},
    'servisni_poseg_serijska':   {'id': Integer(), 'postavka_id': Integer(), 'serijska_st': String(100)},
}

# --- 20. SHRANJEVANJE V MYSQL -------------------------------------------------
print(f"\nShranjevanje v MySQL ({MYSQL_DB})")

tables_to_save = [
    ('vrsta_predmeta_lookup',    df_vrsta_pred),
    ('vrsta_reklamacije_lookup', df_vrsta_rek),
    ('status_reklamacije_lookup',df_status_rek),
    ('status_posega_lookup',     df_status_posega),
    ('vrsta_popravila_lookup',   df_vrsta_popravila),
    ('podjetje',                 df_podjetja),
    ('zaposleni',                df_zaposleni),
    ('nadrejen_izdelek',         df_nadr),
    ('predmet',                  df_predmeti),
    ('tuji_kontakt',             df_kontakti),
    ('reklamacija',              df_rek),
    ('nacin_prejema_lookup',     df_nacin),
    ('prejem_reklamacije',       df_prejemi),
    ('nevarnost',                df_nevarnost),
    ('ukrepi',                   df_ukrepi),
    ('analiza_reklamacije',      df_analize),
    ('zakljucek_reklamacije',    df_zakljucki),
    ('reklamacija_pozicija',     df_pozicije),
    ('serijska_stevilka',        df_ser_rek),
    ('servisni_poseg',           df_posegi),
    ('poseg_reklamacija',        df_poseg_rek),
    ('servisni_poseg_postavka',  df_postavke),
    ('servisni_poseg_serijska',  df_ser_sp),
    ('servisni_poseg_izpeljani', df_izpeljani),

]

print("\nOdstranjevanje obstoječih tujih ključev")
with engine.connect() as c:
    c.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    res = c.execute(text(
        "SELECT TABLE_NAME, CONSTRAINT_NAME "
        "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_TYPE = 'FOREIGN KEY' AND TABLE_SCHEMA = :db"
    ), {'db': MYSQL_DB})
    fk_rows = list(res)
    for tbl, fk in fk_rows:
        try:
            c.execute(text(f"ALTER TABLE `{tbl}` DROP FOREIGN KEY `{fk}`"))
            print(f"   DROP FK {tbl}.{fk}")
        except Exception as e:
            print(f"   OPOZORILO: {tbl}.{fk} - {e}")
    c.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    c.commit()

for name, df in tables_to_save:
    save(name, df, dtype=dtypes.get(name))

# --- 21. POMOŽNA FUNKCIJA ZA ALTER --------------------------------------------
def run_sql(c, sql, label):
    try:
        c.execute(text(sql))
        print(f"   {label}")
    except Exception as e:
        print(f"   OPOZORILO: {label} - {str(e)[:130]}")

# --- 22. ODSTRANITEV POMOŽNIH (BACKUP) TABEL ----------------------------------
print("\nOdstranjevanje pomožnih (backup) tabel")
with engine.connect() as c:
    res = c.execute(text("SHOW TABLES LIKE '%backup%'"))
    backup_tabele = [row[0] for row in res]
    for t in backup_tabele:
        run_sql(c, f"DROP TABLE IF EXISTS `{t}`", f"DROP {t}")
    c.commit()

# --- 23. PRETVORBA DATUMSKIH STOLPCEV V DATE ----------------------------------
print("\nPretvorba datumskih stolpcev v tip DATE")
date_columns = {
    'prejem_reklamacije':    ['datum_prejema'],
    'ukrepi':                ['datum_izvedbe_ukrepa'],
    'analiza_reklamacije':   ['datum_analize_otps', 'datum_analize_ik'],
    'zakljucek_reklamacije': ['datum_zakljucka_rekl', 'datum_zaprtja_dn'],
    'servisni_poseg':        ['datum_prevzema', 'rok_izvedbe', 'datum_resitve'],
}
with engine.connect() as c:
    for tbl, cols in date_columns.items():
        for col in cols:
            run_sql(c, f"ALTER TABLE `{tbl}` MODIFY COLUMN `{col}` DATE NULL",
                    f"{tbl}.{col} -> DATE")
    c.commit()

# --- 24. PRIMARNI KLJUČI ------------------------------------------------------
print("\nDodajanje primarnih ključev")
primary_keys = {
    'vrsta_predmeta_lookup':     'vrsta_predmeta_id',
    'vrsta_reklamacije_lookup':  'vrsta_reklamacije_id',
    'status_reklamacije_lookup': 'status_reklamacije_id',
    'status_posega_lookup':      'status_posega_id',
    'vrsta_popravila_lookup':    'vrsta_popravila_id',
    'podjetje':                  'podjetje_id',
    'zaposleni':                 'zaposleni_id',
    'nadrejen_izdelek':          'ident_nadr_izdelka',
    'predmet':                   'sifra_predmeta',
    'tuji_kontakt':              'kontakt_id',
    'reklamacija':               'stevilka_reklamacije',
    'nacin_prejema_lookup':      'nacin_prejema_id',
    'prejem_reklamacije':        'id',
    'nevarnost':                 'reklamacija_id',
    'ukrepi':                    'id',
    'analiza_reklamacije':       'id',
    'zakljucek_reklamacije':     'reklamacija_id',
    'reklamacija_pozicija':      'pozicija_id',
    'serijska_stevilka':         'id',
    'servisni_poseg':            'dokument',
    'servisni_poseg_postavka':   'id',
    'servisni_poseg_serijska':   'id',
}
with engine.connect() as c:
    for tbl, col in primary_keys.items():
        run_sql(c, f"ALTER TABLE `{tbl}` ADD PRIMARY KEY (`{col}`)", f"PK {tbl}({col})")
    # Sestavljeni primarni ključ za vezno tabelo M:N
    run_sql(c, "ALTER TABLE `poseg_reklamacija` ADD PRIMARY KEY (`dokument_id`, `reklamacija_id`)",
            "PK poseg_reklamacija(dokument_id, reklamacija_id)")
    c.commit()

print("\nČiščenje osamljenih vrednosti pred dodajanjem tujih ključev")
orphan_fixes = [
    ('predmet', 'vrsta_predmeta_id', 'vrsta_predmeta_lookup', 'vrsta_predmeta_id'),
    ('predmet', 'ident_nadr_izdelka', 'nadrejen_izdelek', 'ident_nadr_izdelka'),
    ('tuji_kontakt', 'podjetje_id', 'podjetje', 'podjetje_id'),
    ('reklamacija', 'pritoznik_id', 'podjetje', 'podjetje_id'),
    ('reklamacija', 'kontakt_id', 'tuji_kontakt', 'kontakt_id'),
    ('reklamacija', 'vrsta_reklamacije_id', 'vrsta_reklamacije_lookup', 'vrsta_reklamacije_id'),
    ('reklamacija', 'status_reklamacije_id', 'status_reklamacije_lookup', 'status_reklamacije_id'),
    ('prejem_reklamacije', 'prejemnik_id', 'zaposleni', 'zaposleni_id'),
    ('prejem_reklamacije', 'nacin_prejema_id', 'nacin_prejema_lookup', 'nacin_prejema_id'),
    ('analiza_reklamacije', 'odg_oseba_id', 'zaposleni', 'zaposleni_id'),
    ('analiza_reklamacije', 'predstavnik_ik_id', 'zaposleni', 'zaposleni_id'),
    ('reklamacija_pozicija', 'sifra_predmeta', 'predmet', 'sifra_predmeta'),
    ('servisni_poseg', 'status_posega_id', 'status_posega_lookup', 'status_posega_id'),
    ('servisni_poseg', 'narocnik_id', 'podjetje', 'podjetje_id'),
    ('servisni_poseg', 'prejemnik_id', 'podjetje', 'podjetje_id'),
    ('servisni_poseg', 'vrsta_popravila_id', 'vrsta_popravila_lookup', 'vrsta_popravila_id'),
    ('servisni_poseg', 'referent_id', 'zaposleni', 'zaposleni_id'),
]
with engine.connect() as c:
    for tbl, col, ref_tbl, ref_col in orphan_fixes:
        sql = (f"UPDATE `{tbl}` SET `{col}` = NULL "
               f"WHERE `{col}` IS NOT NULL "
               f"AND `{col}` NOT IN (SELECT `{ref_col}` FROM `{ref_tbl}`)")
        run_sql(c, sql, f"NULL sirote {tbl}.{col}")
    c.commit()

# --- 25. TUJI KLJUČI ----------------------------------------------------------
print("\nDodajanje tujih ključev")
foreign_keys = [
    ('predmet', 'vrsta_predmeta_id', 'vrsta_predmeta_lookup', 'vrsta_predmeta_id'),
    ('predmet', 'ident_nadr_izdelka', 'nadrejen_izdelek', 'ident_nadr_izdelka'),
    ('tuji_kontakt', 'podjetje_id', 'podjetje', 'podjetje_id'),
    ('reklamacija', 'pritoznik_id', 'podjetje', 'podjetje_id'),
    ('reklamacija', 'kontakt_id', 'tuji_kontakt', 'kontakt_id'),
    ('reklamacija', 'vrsta_reklamacije_id', 'vrsta_reklamacije_lookup', 'vrsta_reklamacije_id'),
    ('reklamacija', 'status_reklamacije_id', 'status_reklamacije_lookup', 'status_reklamacije_id'),
    ('prejem_reklamacije', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('prejem_reklamacije', 'prejemnik_id', 'zaposleni', 'zaposleni_id'),
    ('prejem_reklamacije', 'nacin_prejema_id', 'nacin_prejema_lookup', 'nacin_prejema_id'),
    ('nevarnost', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('ukrepi', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('analiza_reklamacije', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('analiza_reklamacije', 'odg_oseba_id', 'zaposleni', 'zaposleni_id'),
    ('analiza_reklamacije', 'predstavnik_ik_id', 'zaposleni', 'zaposleni_id'),
    ('zakljucek_reklamacije', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('reklamacija_pozicija', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('reklamacija_pozicija', 'sifra_predmeta', 'predmet', 'sifra_predmeta'),
    ('serijska_stevilka', 'pozicija_id', 'reklamacija_pozicija', 'pozicija_id'),
    ('servisni_poseg', 'status_posega_id', 'status_posega_lookup', 'status_posega_id'),
    ('servisni_poseg', 'narocnik_id', 'podjetje', 'podjetje_id'),
    ('servisni_poseg', 'prejemnik_id', 'podjetje', 'podjetje_id'),
    ('servisni_poseg', 'vrsta_popravila_id', 'vrsta_popravila_lookup', 'vrsta_popravila_id'),
    ('servisni_poseg', 'referent_id', 'zaposleni', 'zaposleni_id'),
    ('poseg_reklamacija', 'dokument_id', 'servisni_poseg', 'dokument'),
    ('poseg_reklamacija', 'reklamacija_id', 'reklamacija', 'stevilka_reklamacije'),
    ('servisni_poseg_postavka', 'dokument_id', 'servisni_poseg', 'dokument'),
    ('servisni_poseg_postavka', 'sifra_predmeta', 'predmet', 'sifra_predmeta'),
    ('servisni_poseg_serijska', 'postavka_id', 'servisni_poseg_postavka', 'id'),
]
with engine.connect() as c:
    for tbl, col, ref_tbl, ref_col in foreign_keys:
        fk_name = f"fk_{tbl}_{col}"
        sql = (f"ALTER TABLE `{tbl}` ADD CONSTRAINT `{fk_name}` "
               f"FOREIGN KEY (`{col}`) REFERENCES `{ref_tbl}`(`{ref_col}`)")
        run_sql(c, sql, f"FK {tbl}.{col} -> {ref_tbl}.{ref_col}")
    c.commit()

# --- 26. KONTROLA KAKOVOSTI ---------------------------------------------------
print("\nKONTROLA KAKOVOSTI")
print(f"{'Tabela':<30} {'Vrstic':>8}")
print("-" * 40)
total = 0
with engine.connect() as c:
    for name, _ in tables_to_save:
        n = c.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar()
        total += n
        print(f"  {name:<28} {n:>8}")
print(f"\n  Skupaj vrstic: {total:,}")
print(f"  Skupaj tabel:  {len(tables_to_save)}")
print(f"\nMySQL baza '{MYSQL_DB}' zgrajena z normalizirano shemo (3NF).")
print("   Primarni in tuji ključi so vsiljeni na ravni baze.")
print(f"   Povezava za Power BI: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")