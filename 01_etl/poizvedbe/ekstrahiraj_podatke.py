"""
Ekstrakcija analitičnih podatkov iz servis_db -> rezultati_analiza.txt
Zahteva: pip install pymysql
"""

import pymysql
import pymysql.cursors
from datetime import datetime

# --- NASTAVITVE ---------------------------------------------------------------
# Poverilnice se berejo iz datoteke .env v korenu repozitorija (glej .env.example),
# da geslo ni zapisano v skripti.
import os

_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, '.env')
if os.path.exists(_ENV):
    for _vrstica in open(_ENV, encoding='utf-8'):
        _vrstica = _vrstica.strip()
        if _vrstica and not _vrstica.startswith('#') and '=' in _vrstica:
            _k, _v = _vrstica.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

MYSQL_USER     = os.environ.get('SERVIS_DB_USER', 'root')
MYSQL_PASSWORD = os.environ.get('SERVIS_DB_PASSWORD', '')
MYSQL_HOST     = os.environ.get('SERVIS_DB_HOST', 'localhost')
MYSQL_PORT     = int(os.environ.get('SERVIS_DB_PORT', '3306'))
MYSQL_DB       = os.environ.get('SERVIS_DB_NAME', 'servis_db')

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'rezultati_analiza.txt')
# ──────────────────────────────────────────────────────────────────────────────

QUERIES = {

    "1. OBSEG IN ZANESLJIVOST": {
        "sql": """
SELECT
  (SELECT COUNT(*) FROM reklamacija)                                  AS reklamacije_skupaj,
  (SELECT COUNT(*) FROM servisni_poseg)                               AS posegi_skupaj,
  ROUND(100.0 *
    (SELECT COUNT(*) FROM reklamacija r
       LEFT JOIN zakljucek_reklamacije z ON z.reklamacija_id = r.stevilka_reklamacije
       WHERE z.reklamacija_id IS NULL)
    / (SELECT COUNT(*) FROM reklamacija), 1)                          AS pct_brez_zakljucka,
  ROUND(100.0 *
    (SELECT COUNT(*) FROM servisni_poseg s
       LEFT JOIN reklamacija r ON r.stevilka_reklamacije = s.vezni_dokument
       WHERE r.stevilka_reklamacije IS NULL)
    / (SELECT COUNT(*) FROM servisni_poseg), 1)                       AS pct_posegov_brez_reklamacije
""",
        "note": None,
    },

    "2a. VRSTA REKLAMACIJE": {
        "sql": """
SELECT l.naziv,
       COUNT(*) AS stevilo,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS delez_pct
FROM reklamacija r
JOIN vrsta_reklamacije_lookup l ON l.vrsta_reklamacije_id = r.vrsta_reklamacije_id
GROUP BY l.naziv
ORDER BY stevilo DESC
""",
        "note": None,
    },

    "2b. VRSTA PREDMETA": {
        "sql": """
SELECT l.oznaka AS naziv,
       COUNT(DISTINCT r.stevilka_reklamacije) AS stevilo,
       ROUND(100.0 * COUNT(DISTINCT r.stevilka_reklamacije)
             / SUM(COUNT(DISTINCT r.stevilka_reklamacije)) OVER (), 1) AS delez_pct
FROM reklamacija r
JOIN reklamacija_pozicija rp ON rp.reklamacija_id = r.stevilka_reklamacije
JOIN predmet pr              ON pr.sifra_predmeta  = rp.sifra_predmeta
JOIN vrsta_predmeta_lookup l ON l.vrsta_predmeta_id = pr.vrsta_predmeta_id
GROUP BY l.oznaka
ORDER BY stevilo DESC
""",
        "note": "Stevilo = razlicne reklamacije, ki vsebujejo ta tip predmeta",
    },

    "2c. VRSTA POPRAVILA": {
        "sql": """
SELECT l.naziv,
       COUNT(*) AS stevilo,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS delez_pct
FROM servisni_poseg s
JOIN vrsta_popravila_lookup l ON l.vrsta_popravila_id = s.vrsta_popravila_id
GROUP BY l.naziv
ORDER BY stevilo DESC
""",
        "note": None,
    },

    "2d. NACIN PREJEMA": {
        "sql": """
SELECT COALESCE(l.naziv, 'neznan') AS nacin_prejema,
       COUNT(*) AS stevilo,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS delez_pct
FROM prejem_reklamacije p
LEFT JOIN nacin_prejema_lookup l ON l.nacin_prejema_id = p.nacin_prejema_id
GROUP BY COALESCE(l.naziv, 'neznan')
ORDER BY stevilo DESC
""",
        "note": "LEFT JOIN — vkljucuje vnose brez navedenega nacina (prikazano kot 'neznan')",
    },

    "3a. REKLAMACIJE PO LETIH": {
        "sql": """
SELECT YEAR(p.datum_prejema) AS leto,
       COUNT(*) AS stevilo
FROM reklamacija r
JOIN prejem_reklamacije p ON p.reklamacija_id = r.stevilka_reklamacije
WHERE p.datum_prejema IS NOT NULL
GROUP BY YEAR(p.datum_prejema)
ORDER BY leto
""",
        "note": None,
    },

    "3b. SERVISNI POSEGI PO MESECIH": {
        "sql": """
SELECT DATE_FORMAT(datum_prevzema, '%Y-%m') AS mesec,
       COUNT(*) AS stevilo
FROM servisni_poseg
WHERE datum_prevzema IS NOT NULL
GROUP BY mesec
ORDER BY mesec
""",
        "note": "Uporabljen datum_prevzema (datum sprejema v servis)",
    },

    "4. GEOGRAFSKA PORAZDELITEV": {
        "sql": """
SELECT
    po.drzava,
    COUNT(s.dokument)                                                     AS stevilo_posegov,
    ROUND(100.0 * COUNT(s.dokument) / SUM(COUNT(s.dokument)) OVER (), 1) AS delez_pct
FROM servisni_poseg s
JOIN podjetje po ON po.podjetje_id = s.narocnik_id
WHERE po.drzava IS NOT NULL
GROUP BY po.drzava
HAVING stevilo_posegov >= 20
ORDER BY stevilo_posegov DESC
""",
        "note": "Direktna zamenjava pogleda v_drzave_analiza; prag >= 20 posegov",
    },

    "5. CASI RESEVANJA (dni)": {
        "sql": """
WITH casi AS (
  SELECT
    DATEDIFF(
      COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn),
      MIN(p.datum_prejema)
    ) AS dni,
    ROW_NUMBER() OVER (ORDER BY DATEDIFF(
      COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn),
      MIN(p.datum_prejema)
    )) AS rn,
    COUNT(*) OVER () AS n
  FROM reklamacija r
  JOIN prejem_reklamacije    p ON p.reklamacija_id = r.stevilka_reklamacije
  JOIN zakljucek_reklamacije z ON z.reklamacija_id = r.stevilka_reklamacije
  WHERE p.datum_prejema BETWEEN '2013-01-01' AND '2026-12-31'
    AND COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn) BETWEEN '2013-01-01' AND '2026-12-31'
    AND COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn) >= p.datum_prejema
  GROUP BY r.stevilka_reklamacije, z.datum_zakljucka_rekl, z.datum_zaprtja_dn
)
SELECT
  (SELECT COUNT(*) FROM casi)                                    AS n_veljavnih,
  (SELECT ROUND(AVG(dni), 1) FROM casi)                          AS povprecje_dni,
  (SELECT ROUND(AVG(dni), 1) FROM casi
     WHERE rn IN (FLOOR((n+1)/2), CEIL((n+1)/2)))               AS mediana_dni,
  (SELECT MIN(dni) FROM casi)                                    AS min_dni,
  (SELECT MAX(dni) FROM casi)                                    AS max_dni
""",
        "note": "Filter: datumi med 2013-2026 in zakljucek >= prejem; COALESCE na obeh datumih zakljucka",
    },

    "6a. VRSTA PREDMETA x POGOSTOST REKLAMACIJ": {
        "sql": """
SELECT COALESCE(l.opis, l.oznaka) AS naziv,
       COUNT(DISTINCT r.stevilka_reklamacije) AS reklamacije,
       ROUND(100.0 * COUNT(DISTINCT r.stevilka_reklamacije)
             / SUM(COUNT(DISTINCT r.stevilka_reklamacije)) OVER (), 1) AS delez_pct
FROM reklamacija r
JOIN reklamacija_pozicija rp ON rp.reklamacija_id = r.stevilka_reklamacije
JOIN predmet pr              ON pr.sifra_predmeta  = rp.sifra_predmeta
JOIN vrsta_predmeta_lookup l ON l.vrsta_predmeta_id = pr.vrsta_predmeta_id
GROUP BY COALESCE(l.opis, l.oznaka)
ORDER BY reklamacije DESC
""",
        "note": "oznaka je sifra, opis je besedilni naziv (COALESCE vzame opis, ce obstaja)",
    },

    "6b. NACIN PREJEMA x POVPRECNI CAS RESEVANJA": {
        "sql": """
SELECT COALESCE(n.naziv, 'neznan') AS nacin_prejema,
       COUNT(DISTINCT r.stevilka_reklamacije)                                    AS stevilo,
       ROUND(AVG(DATEDIFF(
           COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn),
           p.datum_prejema
       )), 1)                                                                     AS povp_dni
FROM reklamacija r
JOIN prejem_reklamacije    p  ON p.reklamacija_id  = r.stevilka_reklamacije
JOIN zakljucek_reklamacije z  ON z.reklamacija_id  = r.stevilka_reklamacije
LEFT JOIN nacin_prejema_lookup n ON n.nacin_prejema_id = p.nacin_prejema_id
WHERE p.datum_prejema BETWEEN '2013-01-01' AND '2026-12-31'
  AND COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn) BETWEEN '2013-01-01' AND '2026-12-31'
  AND COALESCE(z.datum_zakljucka_rekl, z.datum_zaprtja_dn) >= p.datum_prejema
GROUP BY COALESCE(n.naziv, 'neznan')
ORDER BY povp_dni DESC
""",
        "note": "Isti datumski filter kot query 5; LEFT JOIN pokaze 'neznan' ce nacin_prejema_id prazen",
    },

    "8a. REKLAMACIJE PO DRUZINI IZDELKOV": {
        "sql": """
SELECT COALESCE(ni.druzina_izdelka, 'neznan') AS druzina,
       COUNT(DISTINCT r.stevilka_reklamacije)                          AS reklamacije,
       ROUND(100.0 * COUNT(DISTINCT r.stevilka_reklamacije)
             / SUM(COUNT(DISTINCT r.stevilka_reklamacije)) OVER (), 1) AS delez_pct
FROM reklamacija r
JOIN reklamacija_pozicija rp ON rp.reklamacija_id    = r.stevilka_reklamacije
JOIN predmet pr              ON pr.sifra_predmeta    = rp.sifra_predmeta
JOIN nadrejen_izdelek ni     ON ni.ident_nadr_izdelka = pr.ident_nadr_izdelka
GROUP BY COALESCE(ni.druzina_izdelka, 'neznan')
ORDER BY reklamacije DESC
""",
        "note": "Pot: reklamacija -> reklamacija_pozicija -> predmet -> nadrejen_izdelek",
    },

    "8b. POKRITOST REKLAMACIJ Z DRUZINO": {
        "sql": """
SELECT
    (SELECT COUNT(*) FROM reklamacija)          AS skupaj_reklamacij,
    COUNT(DISTINCT r.stevilka_reklamacije)       AS z_druzino,
    (SELECT COUNT(*) FROM reklamacija)
      - COUNT(DISTINCT r.stevilka_reklamacije)  AS brez_druzine,
    ROUND(100.0 * COUNT(DISTINCT r.stevilka_reklamacije)
      / (SELECT COUNT(*) FROM reklamacija), 1)  AS pct_pokritih
FROM reklamacija r
JOIN reklamacija_pozicija rp ON rp.reklamacija_id    = r.stevilka_reklamacije
JOIN predmet pr              ON pr.sifra_predmeta    = rp.sifra_predmeta
JOIN nadrejen_izdelek ni     ON ni.ident_nadr_izdelka = pr.ident_nadr_izdelka
""",
        "note": "Koliko od 11039 reklamacij ima vezan nadrejen_izdelek",
    },

    "8c. SERVISNI POSEGI PO DRUZINI IZDELKOV": {
        "sql": """
SELECT COALESCE(ni.druzina_izdelka, 'neznan') AS druzina,
       COUNT(DISTINCT s.dokument)                                       AS posegi,
       ROUND(100.0 * COUNT(DISTINCT s.dokument)
             / SUM(COUNT(DISTINCT s.dokument)) OVER (), 1)             AS delez_pct
FROM servisni_poseg s
JOIN servisni_poseg_postavka spp ON spp.dokument_id       = s.dokument
JOIN predmet pr                  ON pr.sifra_predmeta     = spp.sifra_predmeta
JOIN nadrejen_izdelek ni         ON ni.ident_nadr_izdelka  = pr.ident_nadr_izdelka
GROUP BY COALESCE(ni.druzina_izdelka, 'neznan')
ORDER BY posegi DESC
""",
        "note": "Pot: servisni_poseg -> servisni_poseg_postavka -> predmet -> nadrejen_izdelek",
    },

    "8d. POKRITOST POSEGOV Z DRUZINO": {
        "sql": """
SELECT
    (SELECT COUNT(*) FROM servisni_poseg)       AS skupaj_posegov,
    COUNT(DISTINCT s.dokument)                   AS z_druzino,
    (SELECT COUNT(*) FROM servisni_poseg)
      - COUNT(DISTINCT s.dokument)              AS brez_druzine,
    ROUND(100.0 * COUNT(DISTINCT s.dokument)
      / (SELECT COUNT(*) FROM servisni_poseg), 1) AS pct_pokritih
FROM servisni_poseg s
JOIN servisni_poseg_postavka spp ON spp.dokument_id       = s.dokument
JOIN predmet pr                  ON pr.sifra_predmeta     = spp.sifra_predmeta
JOIN nadrejen_izdelek ni         ON ni.ident_nadr_izdelka  = pr.ident_nadr_izdelka
""",
        "note": "Koliko od 4078 posegov ima vezan nadrejen_izdelek",
    },

    "DIAG-A: VSEBINA vrsta_predmeta_lookup": {
        "sql": """
SELECT vrsta_predmeta_id, oznaka, opis
FROM vrsta_predmeta_lookup
ORDER BY vrsta_predmeta_id
""",
        "note": "Diagnostika: preveri, ali je stolpec 'opis' napolnjen ali prazen",
    },

    "DIAG-B: POLNJENOST nacin_prejema_id": {
        "sql": """
SELECT
  COUNT(*)              AS skupaj_vnosov,
  COUNT(nacin_prejema_id) AS napolnjenih,
  COUNT(*) - COUNT(nacin_prejema_id) AS praznih
FROM prejem_reklamacije
""",
        "note": "Diagnostika: ce je napolnjenih = 0, ETL ni preslikal nacin_prejema v transakcijsko tabelo",
    },

    "7. ANOMALIJE — OSAMELCI PO MESECIH": {
        "sql": """
SELECT DATE_FORMAT(p.datum_prejema, '%Y-%m') AS mesec,
       COUNT(*) AS stevilo
FROM reklamacija r
JOIN prejem_reklamacije p ON p.reklamacija_id = r.stevilka_reklamacije
WHERE p.datum_prejema IS NOT NULL
GROUP BY mesec
HAVING stevilo > (
  SELECT AVG(c) + 2 * STDDEV(c)
  FROM (
    SELECT COUNT(*) AS c
    FROM prejem_reklamacije
    WHERE datum_prejema IS NOT NULL
    GROUP BY DATE_FORMAT(datum_prejema, '%Y-%m')
  ) t
)
ORDER BY mesec
""",
        "note": "Meseci nad mejo povprecje + 2*std",
    },
}


# ── POMOCNE FUNKCIJE ───────────────────────────────────────────────────────────

def format_table(columns, rows):
    """Vrne tabelo s fiksno sirino stolpcev."""
    if not rows:
        return "  (ni rezultatov)\n"
    col_widths = [len(str(c)) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val) if val is not None else "NULL"))
    sep = "  +" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    def fmt_row(vals):
        return "  |" + "|".join(
            f" {str(v) if v is not None else 'NULL':<{w}} " for v, w in zip(vals, col_widths)
        ) + "|"
    lines = [sep, fmt_row(columns), sep]
    for row in rows:
        lines.append(fmt_row(row))
    lines.append(sep)
    return "\n".join(lines) + "\n"


def run_all(output_path):
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    cursor = conn.cursor()

    lines = []
    lines.append("=" * 70)
    lines.append(f"  REZULTATI ANALIZE  —  servis_db")
    lines.append(f"  Generirano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")

    for title, entry in QUERIES.items():
        lines.append("=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)
        if entry["note"]:
            lines.append(f"  Opomba: {entry['note']}")
        lines.append("")
        try:
            cursor.execute(entry["sql"])
            rows_dict = cursor.fetchall()
            if rows_dict:
                columns = list(rows_dict[0].keys())
                rows = [tuple(r.values()) for r in rows_dict]
            else:
                columns = [d[0] for d in cursor.description] if cursor.description else []
                rows = []
            lines.append(format_table(columns, rows))
            lines.append(f"  Vrstic: {len(rows)}")
        except pymysql.Error as e:
            lines.append(f"  NAPAKA: {e}")
        lines.append("")

    cursor.close()
    conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Zapisano v: {output_path}")


if __name__ == "__main__":
    run_all(OUTPUT_FILE)
