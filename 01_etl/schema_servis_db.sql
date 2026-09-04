-- ============================================================
--  SHEMA BAZE: servis_db
--  Sistem za podporo odločanju — servisna enota Fotona d.o.o.
--  Normalizacija: 3NF (z dokumentiranimi izjemami)
--  Nabor znakov: utf8mb4 / utf8mb4_unicode_ci
-- ============================================================
--  Tabele so razvrščene po odvisnostih (starši pred otroki).
--  Pred ponovnim izvajanjem izprazni obstoječo bazo:
--    DROP DATABASE IF EXISTS servis_db;
--    CREATE DATABASE servis_db
--      CHARACTER SET utf8mb4
--      COLLATE utf8mb4_unicode_ci;
--    USE servis_db;
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;


-- ────────────────────────────────────────────────────────────
--  SLOJ 1: LOOKUP TABELE  (šifranti)
--  Vsaka lookup tabela hrani unikaten nabor vrednosti z
--  nadomestnim numeričnim ključem — prepreči podvajanje nizov
--  v dejstvenih tabelah in zagotavlja 1NF.
-- ────────────────────────────────────────────────────────────

CREATE TABLE vrsta_predmeta_lookup (
    vrsta_predmeta_id   INT          NOT NULL AUTO_INCREMENT,
    oznaka              VARCHAR(20)  NOT NULL,
    opis                VARCHAR(255)     NULL,
    PRIMARY KEY (vrsta_predmeta_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Šifrant vrst predmetov (rezervni deli, potrošni material …)';

-- ──────────────────────────────────────────────────────────

CREATE TABLE vrsta_reklamacije_lookup (
    vrsta_reklamacije_id    INT          NOT NULL AUTO_INCREMENT,
    naziv                   VARCHAR(255) NOT NULL,
    PRIMARY KEY (vrsta_reklamacije_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Šifrant vrst reklamacij';

-- ──────────────────────────────────────────────────────────

CREATE TABLE status_reklamacije_lookup (
    status_reklamacije_id   INT          NOT NULL AUTO_INCREMENT,
    naziv                   VARCHAR(255) NOT NULL,
    PRIMARY KEY (status_reklamacije_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Šifrant statusov reklamacije (odprta, zaprta …)';

-- ──────────────────────────────────────────────────────────

CREATE TABLE status_posega_lookup (
    status_posega_id    INT          NOT NULL AUTO_INCREMENT,
    naziv               VARCHAR(255) NOT NULL,
    PRIMARY KEY (status_posega_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Šifrant statusov servisnega posega';

-- ──────────────────────────────────────────────────────────

CREATE TABLE vrsta_popravila_lookup (
    vrsta_popravila_id  INT          NOT NULL AUTO_INCREMENT,
    naziv               VARCHAR(255) NOT NULL,
    PRIMARY KEY (vrsta_popravila_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Šifrant vrst popravil (garancijsko, komercialno …)';

-- ──────────────────────────────────────────────────────────
--  nacin_prejema_lookup — dodan po analizi podatkov
--  (vrednosti: e-mail 8 242, telefon 2 120, osebno 258,
--   drugo 179, pismo 48; 267 NULL vrednosti ohranjenih)
-- ──────────────────────────────────────────────────────────

CREATE TABLE nacin_prejema_lookup (
    nacin_prejema_id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    naziv               VARCHAR(50)      NOT NULL,
    PRIMARY KEY (nacin_prejema_id),
    UNIQUE KEY uq_nacin_naziv (naziv)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Šifrant načinov prejema reklamacije';

INSERT INTO nacin_prejema_lookup (naziv)
VALUES ('e-mail'), ('telefon'), ('osebno'), ('drugo'), ('pismo');


-- ────────────────────────────────────────────────────────────
--  SLOJ 2: ENTITETNE TABELE  (neodvisne entitete)
-- ────────────────────────────────────────────────────────────

CREATE TABLE podjetje (
    podjetje_id     BIGINT       NOT NULL,
    naziv           VARCHAR(255)     NULL,
    drzava          VARCHAR(100)     NULL,
    PRIMARY KEY (podjetje_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Stranke, naročniki in prejemniki (interni in zunanji)';

-- ──────────────────────────────────────────────────────────
--  Tabela zaposleni hrani le anonimni identifikator.
--  Odločitev je arhitekturna (GDPR / ZVOP-2): osebni podatki
--  se ne shranjujejo v bazo, zato tabela nima vsebinskih atributov.
-- ──────────────────────────────────────────────────────────

CREATE TABLE zaposleni (
    zaposleni_id    INT NOT NULL AUTO_INCREMENT,
    PRIMARY KEY (zaposleni_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Anonimni identifikatorji zaposlenih (GDPR — brez imen)';

-- ──────────────────────────────────────────────────────────

CREATE TABLE nadrejen_izdelek (
    ident_nadr_izdelka  VARCHAR(100) NOT NULL,
    naziv_nadr_izdelka  VARCHAR(500)     NULL,
    druzina_izdelka     VARCHAR(255)     NULL,
    PRIMARY KEY (ident_nadr_izdelka)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Laser sistemi (nadrejeni izdelki) — skupaj z družino';

-- ──────────────────────────────────────────────────────────

CREATE TABLE predmet (
    sifra_predmeta      VARCHAR(50)  NOT NULL,
    naziv_predmeta      VARCHAR(255)     NULL,
    vrsta_predmeta_id   INT              NULL,
    ident_nadr_izdelka  VARCHAR(100)     NULL,
    PRIMARY KEY (sifra_predmeta),
    CONSTRAINT fk_predmet_vrsta
        FOREIGN KEY (vrsta_predmeta_id)
        REFERENCES vrsta_predmeta_lookup (vrsta_predmeta_id),
    CONSTRAINT fk_predmet_nadr
        FOREIGN KEY (ident_nadr_izdelka)
        REFERENCES nadrejen_izdelek (ident_nadr_izdelka)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Rezervni deli, potrošni material in komponente';

-- ──────────────────────────────────────────────────────────

CREATE TABLE tuji_kontakt (
    kontakt_id          INT          NOT NULL AUTO_INCREMENT,
    podjetje_id         BIGINT           NULL,
    kont_oseba_ime      VARCHAR(255)     NULL,
    kont_oseba_email    VARCHAR(255)     NULL,
    kont_oseba_telefon  VARCHAR(50)      NULL,
    PRIMARY KEY (kontakt_id),
    CONSTRAINT fk_kontakt_podjetje
        FOREIGN KEY (podjetje_id)
        REFERENCES podjetje (podjetje_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Kontaktne osebe pri zunanjih podjetjih';


-- ────────────────────────────────────────────────────────────
--  SLOJ 3A: REKLAMACIJSKI SKLOP
--  Jedro: reklamacija (1) → podrejene entitete (0..*)
-- ────────────────────────────────────────────────────────────

CREATE TABLE reklamacija (
    stevilka_reklamacije    VARCHAR(255) NOT NULL,
    pritoznik_id            BIGINT           NULL,
    -- OPOMBA 3NF-1: pritoznik_id je tranzitivno odvisen prek
    -- kontakt_id → tuji_kontakt.podjetje_id. Hranjen direktno
    -- ker del reklamacij nima kontaktne osebe (kontakt_id = NULL).
    kontakt_id              INT              NULL,
    opis_reklamacije        TEXT             NULL,
    vrsta_reklamacije_id    INT              NULL,
    garancija               TINYINT(1)       NULL,   -- 1 = DA, 0 = NE
    status_reklamacije_id   INT              NULL,
    naziv_dokumenta         VARCHAR(255)     NULL,
    PRIMARY KEY (stevilka_reklamacije),
    CONSTRAINT fk_rek_pritoznik
        FOREIGN KEY (pritoznik_id)
        REFERENCES podjetje (podjetje_id),
    CONSTRAINT fk_rek_kontakt
        FOREIGN KEY (kontakt_id)
        REFERENCES tuji_kontakt (kontakt_id),
    CONSTRAINT fk_rek_vrsta
        FOREIGN KEY (vrsta_reklamacije_id)
        REFERENCES vrsta_reklamacije_lookup (vrsta_reklamacije_id),
    CONSTRAINT fk_rek_status
        FOREIGN KEY (status_reklamacije_id)
        REFERENCES status_reklamacije_lookup (status_reklamacije_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Reklamacija — osrednja entiteta reklamacijskega sklopa';

-- ──────────────────────────────────────────────────────────

CREATE TABLE prejem_reklamacije (
    id                      INT              NOT NULL AUTO_INCREMENT,
    reklamacija_id          VARCHAR(255)     NOT NULL,
    prejemnik_id            INT                  NULL,
    datum_prejema           DATE                 NULL,
    nacin_prejema_id        TINYINT UNSIGNED     NULL,
    dodatni_opis_prejema    TEXT                 NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_prejem_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije),
    CONSTRAINT fk_prejem_prejemnik
        FOREIGN KEY (prejemnik_id)
        REFERENCES zaposleni (zaposleni_id),
    CONSTRAINT fk_prejem_nacin
        FOREIGN KEY (nacin_prejema_id)
        REFERENCES nacin_prejema_lookup (nacin_prejema_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Podatki o prejemu posamezne reklamacije';

-- ──────────────────────────────────────────────────────────

CREATE TABLE nevarnost (
    reklamacija_id              VARCHAR(255) NOT NULL,
    ali_obstaja_nevarnost       TINYINT(1)       NULL,
    obrazlozitev_nevarnosti     TEXT             NULL,
    PRIMARY KEY (reklamacija_id),
    CONSTRAINT fk_nevarnost_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Ocena nevarnosti za reklamacijo (1:0..1 z reklamacijo)';

-- ──────────────────────────────────────────────────────────

CREATE TABLE ukrepi (
    id                          INT          NOT NULL AUTO_INCREMENT,
    reklamacija_id              VARCHAR(255) NOT NULL,
    ukrepi_za_resitev           TEXT             NULL,
    potrebni_dodatni_ukrepi     TINYINT(1)       NULL,
    komentar_dod_ukrep          TEXT             NULL,
    datum_izvedbe_ukrepa        DATE             NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_ukrepi_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Ukrepi za rešitev reklamacije (1:0..N z reklamacijo)';

-- ──────────────────────────────────────────────────────────

CREATE TABLE analiza_reklamacije (
    id                          INT          NOT NULL AUTO_INCREMENT,
    reklamacija_id              VARCHAR(255) NOT NULL,
    odg_oseba_id                INT              NULL,
    datum_analize_otps          DATE             NULL,
    predstavnik_ik_id           INT              NULL,
    datum_analize_ik            DATE             NULL,
    predhna_analiza_ustrezna    TINYINT(1)       NULL,
    vrsta_napake                VARCHAR(255)     NULL,
    potrebna_analiza_vrnjenega  TINYINT(1)       NULL,
    ugot_vzrok_reklamacije      TINYINT(1)       NULL,
    opis_ugotovljenega_vzroka   TEXT             NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_analiza_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije),
    CONSTRAINT fk_analiza_odg
        FOREIGN KEY (odg_oseba_id)
        REFERENCES zaposleni (zaposleni_id),
    CONSTRAINT fk_analiza_ik
        FOREIGN KEY (predstavnik_ik_id)
        REFERENCES zaposleni (zaposleni_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Tehnična analiza vzroka reklamacije';

-- ──────────────────────────────────────────────────────────

CREATE TABLE zakljucek_reklamacije (
    reklamacija_id          VARCHAR(255) NOT NULL,
    datum_zakljucka_rekl    DATE             NULL,
    datum_zaprtja_dn        DATE             NULL,
    PRIMARY KEY (reklamacija_id),
    CONSTRAINT fk_zakljucek_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Datumi zaključka reklamacije in zaprtja delovnega naloga';

-- ──────────────────────────────────────────────────────────

CREATE TABLE reklamacija_pozicija (
    pozicija_id         INT          NOT NULL AUTO_INCREMENT,
    reklamacija_id      VARCHAR(255) NOT NULL,
    sifra_predmeta      VARCHAR(50)      NULL,
    kolicina            FLOAT            NULL,
    PRIMARY KEY (pozicija_id),
    CONSTRAINT fk_pozicija_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije),
    CONSTRAINT fk_pozicija_predmet
        FOREIGN KEY (sifra_predmeta)
        REFERENCES predmet (sifra_predmeta)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Pozicije (artikli) znotraj reklamacije';

-- ──────────────────────────────────────────────────────────

CREATE TABLE serijska_stevilka (
    id              INT          NOT NULL AUTO_INCREMENT,
    pozicija_id     INT          NOT NULL,
    serijska_st     VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_serijska_pozicija
        FOREIGN KEY (pozicija_id)
        REFERENCES reklamacija_pozicija (pozicija_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Serijske številke reklamiranih artiklov (1:N za pozicijo)';


-- ────────────────────────────────────────────────────────────
--  SLOJ 3B: SERVISNI POSEG SKLOP
-- ────────────────────────────────────────────────────────────

CREATE TABLE servisni_poseg (
    dokument            VARCHAR(50)  NOT NULL,
    status_posega_id    INT              NULL,
    narocnik_id         BIGINT           NULL,
    prejemnik_id        BIGINT           NULL,
    program             VARCHAR(100)     NULL,
    sm                  VARCHAR(100)     NULL,
    delovni_nalog       VARCHAR(100)     NULL,
    vrsta_popravila_id  INT              NULL,
    referent_id         INT              NULL,
    datum_prevzema      DATE             NULL,
    rok_izvedbe         DATE             NULL,
    datum_resitve       DATE             NULL,
    -- OPOMBA 3NF-2: vezni_dokument je de-normalizacijski bližnjič —
    -- hrani samo PRVO vezano reklamacijo. Polno M:N razmerje je
    -- shranjeno v poseg_reklamacija. Ohranjeno za hitrejše DAX
    -- poizvedbe v Power BI brez sestavljenih joinov.
    vezni_dokument      VARCHAR(255)     NULL,
    izpeljani_dokument  TEXT             NULL,
    PRIMARY KEY (dokument),
    CONSTRAINT fk_poseg_status
        FOREIGN KEY (status_posega_id)
        REFERENCES status_posega_lookup (status_posega_id),
    CONSTRAINT fk_poseg_narocnik
        FOREIGN KEY (narocnik_id)
        REFERENCES podjetje (podjetje_id),
    CONSTRAINT fk_poseg_prejemnik
        FOREIGN KEY (prejemnik_id)
        REFERENCES podjetje (podjetje_id),
    CONSTRAINT fk_poseg_vrsta_pop
        FOREIGN KEY (vrsta_popravila_id)
        REFERENCES vrsta_popravila_lookup (vrsta_popravila_id),
    CONSTRAINT fk_poseg_referent
        FOREIGN KEY (referent_id)
        REFERENCES zaposleni (zaposleni_id),
    CONSTRAINT fk_poseg_vezni
        FOREIGN KEY (vezni_dokument)
        REFERENCES reklamacija (stevilka_reklamacije)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Servisni poseg (delovni nalog servisne enote)';

-- ──────────────────────────────────────────────────────────
--  M:N vezna tabela med servisnim posegom in reklamacijo
-- ──────────────────────────────────────────────────────────

CREATE TABLE poseg_reklamacija (
    dokument_id     VARCHAR(50)  NOT NULL,
    reklamacija_id  VARCHAR(255) NOT NULL,
    PRIMARY KEY (dokument_id, reklamacija_id),
    CONSTRAINT fk_pr_poseg
        FOREIGN KEY (dokument_id)
        REFERENCES servisni_poseg (dokument),
    CONSTRAINT fk_pr_rek
        FOREIGN KEY (reklamacija_id)
        REFERENCES reklamacija (stevilka_reklamacije)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='M:N razmerje med servisnim posegom in reklamacijo';

-- ──────────────────────────────────────────────────────────

CREATE TABLE servisni_poseg_postavka (
    id              INT          NOT NULL AUTO_INCREMENT,
    dokument_id     VARCHAR(50)  NOT NULL,
    sifra_predmeta  VARCHAR(50)      NULL,
    kolicina        VARCHAR(50)      NULL,
    tekst           TEXT             NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_postavka_poseg
        FOREIGN KEY (dokument_id)
        REFERENCES servisni_poseg (dokument),
    CONSTRAINT fk_postavka_predmet
        FOREIGN KEY (sifra_predmeta)
        REFERENCES predmet (sifra_predmeta)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Postavke (artikli) na servisnem posegu';

-- ──────────────────────────────────────────────────────────

CREATE TABLE servisni_poseg_serijska (
    id          INT          NOT NULL AUTO_INCREMENT,
    postavka_id INT          NOT NULL,
    serijska_st VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_sp_serijska_postavka
        FOREIGN KEY (postavka_id)
        REFERENCES servisni_poseg_postavka (id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Serijske številke artiklov na servisnem posegu';


-- ────────────────────────────────────────────────────────────
--  ZAKLJUČEK
-- ────────────────────────────────────────────────────────────

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
--  POVZETEK SHEME
--  Skupaj tabel:       23
--  Lookup tabel:        6  (sloj 1)
--  Entitetnih tabel:    5  (sloj 2)
--  Transakcijskih tab: 12  (sloj 3)
--  Tujih ključev:      30
--  M:N veznih tabel:    1  (poseg_reklamacija)
--
--  Dokumentirane 3NF izjeme:
--  [3NF-1] reklamacija.pritoznik_id — tranzitivna odvisnost
--          prek kontakt_id; ohranjena za NULL-varnost
-- ============================================================
