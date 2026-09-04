# Tehnično poročilo: analiza čakalnih dob NIJZ (faza 2)

**Projekt:** primerjalni test prenosljivosti analitičnega pristopa Fotona → NIJZ (RV4)
**Vir podatkov:** tedenska poročila NIJZ o čakalnih dobah (javni arhiv .xlsx)
**Datum analize:** 21. 7. 2026
**Okolje:** Python 3.11.3, pandas, statsmodels 0.14.6, scikit-learn 1.9.0

> Delovno tehnično poročilo (ne besedilo naloge). Vse metrike izhajajo iz
> walk-forward validacije z rastočim oknom brez uhajanja podatkov; metrike se
> računajo izključno na dejansko opazovanih tednih (interpolirani manjkajoči
> tedni so iz ocenjevanja izločeni). Zaporedje skript in izhodov je
> dokumentirano v `README.md`.

---

## 0. Podatkovna osnova

| Postavka | Vrednost |
|---|---|
| Surove datoteke | 112 tedenskih .xlsx (4. 4. 2024 – 15. 7. 2026), `data/raw/` |
| Panel | 41.767 vrstic (teden × VZS), `data/panel_vzs.parquet` |
| Različnih VZS | 376 (367–375 na teden) |
| VZS s popolno vrsto števila čakajočih | 282 |
| Redna tedenska mreža | 120 tednov, od tega 8 manjkajočih (interpolirani, izločeni iz metrik) |

**Ciljna spremenljivka:** število čakajočih (`cak_skupaj`); čakalna doba na
prvi prosti termin (`cd_redno`) kot sekundarna spremenljivka (sklep 1.4
načrta). **Izbrane storitve** (merila 1.4: popolnost, raven, raznolikost):

| Šifra | Storitev | Vloga v izboru |
|---|---|---|
| 1010P | Dermatološki pregled - prvi | ambulantni pregled, največ čakajočih (~29.400) |
| 1018P | Kardiološki pregled - prvi | ambulantni pregled, internistika; edina vrsta s padajočim trendom |
| 1941 | UZ vratnih žil | slikovna diagnostika (UZ), največja diagnostična vrsta |
| 1755 | MR glave brez kontrasta | slikovna diagnostika (MR) |
| 1195 | Operacija sive mrene (katarakte) | operativna storitev z največ čakajočimi |
| 1626 | Endoproteza kolena | operativna storitev z najdaljšo ČD (mediana 678 dni) |
| AGREGAT | vsota čez 282 VZS s popolnimi vrstami | vzporednica »skupnemu številu reklamacij« pri Fotoni |

---

## 1. A1 — kakovost in struktura podatkov (N-RV1)

- **Format se je spreminjal aditivno**: 23 stolpcev (apr. 2024) → 25 → 27
  (jan. 2025, dodani preklici) → 30 (jun. 2025, dodana realizirana ČD) → 32
  (feb. 2026, enkratno). Jedrni kazalniki (ČD na prvi prosti termin, število
  čakajočih po stopnjah nujnosti) so prisotni v vseh 112 datotekah, zato
  združevanje v panel ni zahtevalo revizije načrta.
- **Nekonsistentno besedilno kodiranje:** oznaka tipa VZS je sredi arhiva
  spremenila zapis (»Kurativni pregled- Prvi« → »Kurativni pregled - Prvi«),
  kar brez normalizacije razcepi časovne vrste. Neposredna vzporednica
  prosto-besedilnim oznakam vrste napake pri Fotoni.
- **Manjkajoči podatki:** ČD (redno) je popolna (0,0 % NaN), število
  čakajočih ima 11,5 % NaN; manjkanje je vezano na storitve (93 VZS z
  nepopolnimi vrstami), ne na tedne — za modeliranje je na voljo 282 popolnih
  vrst. 8 manjkajočih tednov v arhivu sovpada s prazniki (božič ×2, novo
  leto ×2, dan državnosti ×2, velika noč, prvomajski teden).
- **Spremembe nabora VZS:** 37 dogodkov (15 vstopov, 22 izstopov) — nabor ni
  fiksen, zato agregat računamo samo čez stabilnih 282 VZS.
- Izhodi: `rezultati/a1_*.csv`, `visualizations/a1_pokritost.png`.

## 2. A2–A3 — opisna statistika, trendi, sezonskost (N-RV2)

- **Agregat je v 2,3 letih zrasel za 15,9 %** (294.560 → 358.335 ob vrhu;
  linearni naklon +589 čakajočih/teden, R² = 0,91, p < 0,001). Rast se je
  ustavila spomladi 2026 (zadnje ~3 mesece rahel padec).
- **Rast je koncentrirana v slikovni diagnostiki**: UZ vratnih žil +60 %,
  MR glave +59 %, MR kolena +81 % (največje absolutne rasti); kardiološki
  pregled −11,6 % je edina velika vrsta z izboljšanjem.
- **Stopnje nujnosti:** čakajoči »redno« prevladujejo; razmerja so skozi
  čas stabilna (graf `a2_nujnost.png`).
- **Sezonskost je šibka in nepotrjena:** STL (opisno, 2 cikla) pripiše
  sezonski komponenti ~33 % st. odklona vrste, a medletna primerjava
  istoležnih tednov pokaže, da razlike med leti prevladujejo nad
  znotrajletnim vzorcem; poletje/zima se ne razlikujeta konsistentno.
  Prevlada trenda nad znotrajletnim vzorcem je skladna z napovednim delom
  (A5), kjer trend ni izkoristljiv za boljšo napoved.
- Izhodi: `rezultati/a2_*.csv`, `visualizations/a2_*.png`, `a3_*.png`.

## 3. A4 — detekcija anomalij (N-RV2)

Konsenz Z-score (na tedenskih razlikah) + Isolation Forest, kot pri Fotoni:
777 testiranih točk, 27 Z-označb, 42 IF-označb, **22 konsenznih anomalij**.

- **Največja anomalija je podatkovna, ne procesna:** 11. 6. 2025 padec
  agregata za −32.669 (z = −6,7) s simetričnim odbojem +31.161 teden
  pozneje — datum natanko sovpada s spremembo formata poročila (27 → 30
  stolpcev). Interpretacija: izpad/nepopolnost poročanja ob prehodu, ne
  dejanski skok čakalnih vrst. Vzporednica prelomu taksonomije 2019/2020
  pri Fotoni: administrativna sprememba, ki se v vrsti kaže kot »dogodek«.
- Preostale anomalije so pretežno pari padec–odboj okoli praznikov
  (jun. 2025, avg. 2025, apr. 2026) — izpadi poročanja, ne procesne
  spremembe. Pri Fotoni je bila edina »resnična« procesna anomalija COVID
  2020-04; v arhivu NIJZ (po 2024) primerljivo velikega procesnega šoka ni.
- Izhodi: `rezultati/a4_anomalije*.csv`, `visualizations/a4_anomalije.png`.

## 4. A5 — napovedni modeli (N-RV3)

Walk-forward z rastočim oknom (min. 52 tednov treninga, 62 opazovanih
testnih tednov pri h = 1, 59 pri h = 4). Za konsistentnost s Fotono
(poglavje 5.3) se primerjajo trije modeli: **naivni** (t−1) kot obvezno
izhodišče, **linearna regresija** (linearni trend čez tedenski indeks,
OLS `y ~ const + t`) in **AR(1)** (napoved iz pretekle vrednosti same
vrste). Metrike se računajo samo na opazovanih tednih.

**Izboljšava MAE proti naivnemu (v %; pozitivno = boljše od naivnega):**

| Vrsta | Lin. regresija (h = 1) | AR(1) (h = 1) | Lin. regresija (h = 4) | AR(1) (h = 4) |
|---|---:|---:|---:|---:|
| Agregat | −131,2 | −16,8 | −57,3 | −56,0 |
| Dermatološki pregled | −341,0 | −3,7 | −160,6 | −12,9 |
| Kardiološki pregled | −521,3 | −1,3 | −176,9 | −2,6 |
| UZ vratnih žil | −398,0 | **+3,8** | −199,3 | −2,2 |
| MR glave brez kontrasta | −773,6 | −1,2 | −246,7 | −2,3 |
| Operacija sive mrene | −162,1 | −0,8 | −66,3 | **+2,3** |
| Endoproteza kolena | −40,8 | −28,4 | **+5,0** | −7,8 |

**Ključne ugotovitve:**

- **Naivni model je praktično nepremagljiv na obeh horizontih.** Število
  čakajočih je zelo persistentno stanje (zaloga, ne tok): tedenska sprememba
  agregata je v povprečju < 1 % ravni, zato je stanje prejšnjega tedna
  izvrstna napoved. Relativna napaka naivnega modela na agregatu je MAE 2.561
  pri ravni ~327.000, tj. **0,8 %** — vrsto je mogoče napovedati z majhno
  napako, a to napovedljivost v celoti zajame že trivialni model.
- **AR(1) se naivnemu le približa, a ga praviloma ne premaga:** pri h = 1 je
  od naivnega slabši pri šestih od sedmih vrst (za 0,8–28 %) in ga premaga le
  pri UZ vratnih žil (+3,8 %); pri h = 4 je slika enaka (premaga le pri
  operaciji sive mrene, +2,3 %). Blago vračanje k povprečju, ki ga AR(1)
  vgradi, na persistentni vrsti ne prinaša dodane vrednosti nad prenosom
  zadnje vrednosti.
- **Linearni trend na tej vrsti odpove:** čeprav je trend statistično močan
  (agregat R² = 0,91), globalni linearni model napoveduje vrednost na
  regresijski premici in ne sledi trenutni ravni, zato je pri h = 1 slabši od
  naivnega za 131 % (agregat) do 774 % (MR glave). To je neposredna
  ilustracija ugotovitve iz gospodarstva: na persistentnem stanju je
  prilagajanje trenda slabše od trivialnega prenosa zadnje vrednosti —
  odločilna ni izbira algoritma, temveč narava vrste.
- MASE naivnega modela na testu je 0,85–1,39 (za večino vrst > 1), ker je
  testno obdobje (2025–2026, pospešena rast + artefakt junija 2025) bolj
  volatilno od trening obdobja — še en pokazatelj, da napake ni smiselno
  ocenjevati in-sample.
- Izhodi: `rezultati/a5_metrike.csv`, `a5_napovedi_dolge.csv`,
  `visualizations/a5_mae_primerjava.png`, `a5_agregat_h1.png`.

## 5. A6 — intervalne napovedi (N-RV3/RV4)

- **Empirični intervali P10–P90 iz preteklih walk-forward ostankov AR(1)**
  (brez uhajanja: kvantili samo iz ostankov pred ocenjevano točko): pri
  h = 1 pokritost 71–88 % ob nazivni 80 % (42 testnih točk, standardna
  napaka ocene ~6 o. t.) — intervali so približno pošteni. Pri h = 4
  pokritost pade pri vrstah s spremembo režima (dermatologija 44 %,
  MR glave 56 %) — intervali veljajo ob predpostavki stabilnega režima,
  kar je treba v poročilu izrecno navesti.
- **Kvantilni GB za čakalno dobo** (sekundarna spremenljivka, h = 1):
  pokritost 53–81 %; podpokritost pri operaciji sive mrene (53 %) kaže, da
  kvantilna regresija na 112 točkah ne ujame repov. Kvalitativno enako kot
  pri Fotoni: intervalna informacija je uporabnejša od točkovne, a jo je
  treba prikazovati s pridržkom majhnega vzorca.
- Izhodi: `rezultati/a6_pokritost.csv`, `visualizations/a6_intervali_agregat.png`,
  `a6_kvantilni_cd.png`.

## 6. A7 — zamiki med številom čakajočih in čakalno dobo (N-RV2/3)

- Križne korelacije na tedenskih razlikah (zamiki 0–8 tednov): **nobena ni
  statistično značilna** (|r| < 2/√n) pri nobeni od 7 vrst.
- Test z modelom: AR-X (ΔČakajoči t−1, t−2 kot dodatni značilki) **poslabša**
  napoved čakalne dobe pri vseh vrstah (−0,7 do −10,0 % proti čistemu AR).
- Sklep: na tedenski ravni znotraj ene VZS število čakajočih ne »vodi«
  čakalne dobe; obe vrsti sta persistentni in njuna kratkoročna dinamika je
  pretežno šum poročanja. Čakalno dobo je torej smiselno modelirati
  neodvisno, ne kot izpeljanko iz čakajočih. Enak epilog kot pri Fotoni na
  letni ravni (posegi/prihodki niso izboljšali napovedi reklamacij) — z isto
  metodološko pastjo (korelacija na nivojih bi bila navidezno visoka).
- Izhodi: `rezultati/a7_ccf.csv`, `a7_arx_primerjava.csv`,
  `visualizations/a7_ccf.png`.

## 7. A8 — sinteza: prenosljivost pristopa Fotona → NIJZ (RV4)

| Korak pristopa | Fotona (interni podatki) | NIJZ (javni podatki) | Prenosljivost |
|---|---|---|---|
| Zajem in sestava zbirke | rekonstrukcija kategorij iz prosto-besedilnih oznak | sestava panela iz 112 presečnih posnetkov; normalizacija nekonsistentnih oznak | **neposredna** — enaka logika, drugačen mehanizem |
| Ocena kakovosti | prelom taksonomije 2019/2020 | sprememba formata jun. 2025 z navideznim skokom; spremembe nabora VZS; prazniki = izpadi objav | **neposredna** — »umazanija« obstaja tudi v uradnih javnih podatkih, le drugačne vrste |
| Izbira granulacije | letna → mesečna raven prinesla prvi pozitiven rezultat | tedenska raven: stanje (zaloga) je persistentno, naivni model zajame skoraj vso napovedljivost na obeh horizontih | **prenosljivo z obratom**: ključna ni finejša granulacija, ampak narava vrste (tok dogodkov ↔ stanje/zaloga) |
| Naivna izhodišča | obvezna; večino modelov diskvalificirajo | enako; pri h = 1 diskvalificirajo praktično vse | **neposredna** |
| Walk-forward validacija | rastoče okno, brez uhajanja | enako + izločitev interpoliranih tednov iz metrik | **neposredna** |
| Preprosto : kompleksno | AR(1)/linearni trend > polinomska/Poisson | naivni ≥ AR(1) > linearni trend (prilagojeni trend izgubi proti trivialnemu prenosu zadnje vrednosti) | **neposredna** — ista ugotovitev na neodvisni domeni |
| Eksterni prediktorji | prihodki/posegi ne izboljšajo napovedi | Δčakajoči ne izboljša napovedi ČD (AR-X slabši) | **neposredna** (negativen rezultat na obeh domenah) |
| Kvantilni intervali | uporabni tam, kjer točkovna napoved ni | približno pošteni pri h = 1; podpokritost pri h = 4/repih | **prenosljivo s pridržkom** (kratka vrsta) |
| Detekcija anomalij | konsenz Z + IF; COVID 2020-04 | konsenz Z + IF; artefakt spremembe formata jun. 2025 | **neposredna**; nova nujna distinkcija: podatkovna ↔ procesna anomalija |

**Odgovori na raziskovalna vprašanja NIJZ dela:**

- **N-RV1:** Javni podatki so formalno urejeni (standardizirane objave,
  konsistentna frekvenca), a ne »čisti«: aditivne spremembe formata,
  nekonsistentno besedilno kodiranje, 11,5 % manjkajočih vrednosti ciljne
  spremenljivke, spremembe nabora VZS in izpadi objav ob praznikih. Priprava
  podatkov je zahtevala enak tip dela kot pri internih podatkih Fotone.
- **N-RV2:** Prevladuje trend (agregat +15,9 % v 2,3 letih, koncentriran v
  slikovni diagnostiki), sezonskost je šibka in z dvema cikloma nepotrjena;
  vse velike anomalije imajo administrativno razlago (format, prazniki).
- **N-RV3:** Da, število čakajočih je napovedljivo z majhno relativno napako
  (naivni MAE 0,8 % ravni agregata) — a **naivnega izhodišča ne premaga
  praktično noben model, na nobenem od obeh horizontov**. AR(1) se naivnemu le
  približa (premaga ga le pri eni od sedmih vrst na vsakem horizontu),
  linearni trend pa kljub statistično močnemu trendu (R² = 0,91) izgubi za
  več deset do sto odstotkov, ker ne sledi trenutni ravni. Ugotovitev iz
  gospodarstva se potrdi: odločilna ni izbira algoritma, temveč narava vrste —
  ker gre za persistentno stanje (zalogo), je trivialni prenos zadnje
  vrednosti tako rekoč optimalen, prilagajanje trenda pa škodi.
- **N-RV4 = RV4:** Prenosljivi so vsi metodološki elementi (sestava zbirke,
  poštena izhodišča, walk-forward, kvantilni pogled, konsenzna detekcija
  anomalij); prilagoditev zahtevata interpretacija (stanje/zaloga namesto
  toka dogodkov → drugačna vloga naivnega modela) in obravnava anomalij
  (ločevanje podatkovnih od procesnih); odpove pa sezonsko modeliranje,
  ker je javni arhiv prekratek — kar je samo po sebi ugotovitev o omejitvah
  javnih odprtih podatkov.

**Skupni metodološki sklep** (zrcalo sklepa pri Fotoni): tudi na javnih
zdravstvenih podatkih dobički ne pridejo iz algoritmov, temveč iz (1) pravilne
izbire ravni in horizonta napovedovanja, (2) poštenih naivnih izhodišč in
(3) čiste, časovno pravilne validacije; dodatna specifika javnih podatkov je
obvezno ločevanje administrativnih artefaktov od dejanske dinamike procesa.

---

## 8. Omejitve

- 112 opazovanih tednov (2 polna letna cikla) — sezonskih sklepov ni mogoče
  statistično potrditi; walk-forward test ima 62 (h = 1) oz. 59 (h = 4) točk.
- Presečna narava: napoveduje se stanje čakalnih seznamov, ne prilivi/odlivi;
  popolnosti poročanja izvajalcev navzgor ni mogoče preveriti, zato je del
  trenda lahko artefakt spreminjanja poročanja.
- Rezultati veljajo za 6 izbranih storitev in agregat 282 VZS, ne nujno za
  vseh ~400 VZS.
- Interpolacija 8 manjkajočih tednov vpliva na trening modelov (ne na
  metrike, ki so računane samo na opazovanih tednih).
