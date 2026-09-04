# PRILOGA 3: IZSEK CEVOVODA ETL
#
# Prikazani so trije reprezentativni deli skripte etl_servis_original.py
# (skupaj 805 vrstic). Izsek zajema poenotenje formatov, razčlembo
# večvrednostnih celic in nalaganje tabel v podatkovno bazo. Celotna skripta
# je na voljo pri avtorju naloge.
#
# ---------------------------------------------------------------------------
# A) POENOTENJE DATUMSKIH IN LOGIČNIH POLJ (poglavje 4.1.2)
#    Regularni izraz prepozna pričakovana zapisa datuma in ju preslika v
#    ISO 8601; neustrezne vrednosti se preslikajo v NULL.
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# B) RAZČLEMBA VEČVREDNOSTNIH CELIC (poglavje 4.1.2 in 4.1.3)
#    Ena celica lahko vsebuje vec serijskih številk, ločenih z vejico ali
#    značko <br>. Funkcija je pogoj za prehod v prvo normalno obliko.
# ---------------------------------------------------------------------------
def split_multi(val):
    if pd.isna(val): return []
    val = str(val).strip()
    val = re.sub(r'<br>', ',', val, flags=re.IGNORECASE)
    parts = re.split(r',', val)
    return [p.strip() for p in parts if p.strip() and p.strip() not in ('-', '0', '')]

# ---------------------------------------------------------------------------
# C) NALAGANJE TABEL V PODATKOVNO BAZO (poglavje 4.2.1)
#    Vrstni red seznama tables_to_save upošteva odvisnosti med tujimi ključi,
#    zato se nadrejene tabele vedno zapišejo pred podrejenimi.
# ---------------------------------------------------------------------------
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
    ('serijska_številka',        df_ser_rek),
    ('servisni_poseg',           df_posegi),
    ('poseg_reklamacija',        df_poseg_rek),
    ('servisni_poseg_postavka',  df_postavke),
    ('servisni_poseg_serijska',  df_ser_sp),
    ('servisni_poseg_izpeljani', df_izpeljani),

]
    # … preostalih 13 tabel …
]

for name, df in tables_to_save:
    save(name, df, dtype=dtypes.get(name))

# --- 21. POMOŽNA FUNKCIJA ZA ALTER --------------------------------------------
