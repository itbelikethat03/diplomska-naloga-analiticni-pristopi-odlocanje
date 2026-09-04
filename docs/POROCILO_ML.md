# Poročilo o modelih strojnega učenja

**Projekt:** analiza reklamacij in servisnih posegov (Fotona), diplomska naloga
**Vir podatkov:** lokalna MySQL baza `servis_db`
**Datum analize:** 17. 7. 2026
**Okolje:** Python 3.11, scikit-learn 1.9.0, pandas 2.2.3

> Vse metrike v tem poročilu izhajajo iz zagonov po metodoloških popravkih
> (odprava uhajanja podatkov pri izboru modela, časovno pravilna validacija,
> rekonstrukcija stolpca `kategorija`). Starejši rezultati v mapi
> `_stari_rezultati/` teh popravkov ne vsebujejo in so deloma optimistično
> pristranski.

---

## 0. Podatkovna osnova in skupne opombe

| Vir | Obseg |
|---|---|
| `reklamacija` | 11.039 zapisov |
| `analiza_reklamacije` | 10.759 zapisov (6 rekonstruiranih kategorij napak) |
| `servisni_poseg` | 4.078 zapisov (datum prevzema od 2020 naprej) |
| `fotona_revenue` | letni prihodki 2012–2024 |
| Časovno obdobje analiz | 2013–2024 (reklamacije), 2020–2024 (posegi) |

**Rekonstrukcija ciljne kategorije.** Trenutna shema baze nima stolpca
`kategorija`; ta je rekonstruiran iz `vrsta_napake` (modul `db_common.py`).
Preslikava ~30 starih prosto-besedilnih oznak je kalibrirana proti
zgodovinskim rezultatom in se za leta 2017–2019 ujema na reklamacijo natančno,
zato rekonstrukcija ne vnaša merljive napake.

**Prelom taksonomije 2019/2020.** Kategoriji *enota za sprej* in *ni tehnična
napaka* po letu 2019 strmo padeta (s ~50–150 na ~1–44 letno), ker so bile
stare oznake (npr. »okvara polnilca«, »drugo«) opuščene. Del »trenda« teh dveh
kategorij je torej artefakt spremembe klasifikacije, kar je treba upoštevati
pri interpretaciji vseh napovednih modelov.

**Opomba o klasifikacijskih metrikah.** Projekt ne vsebuje nobenega
klasifikacijskega modela, zato metrike *Accuracy, Precision, Recall, F1,
ROC-AUC* in *confusion matrix* **niso izračunljive** za nobeno skripto. Vsi
napovedni modeli so regresijski (metrike MAE, RMSE, R²), detekcija anomalij pa
je nenadzorovana — za njene metrike bi potrebovali ročno označene anomalije
(ground truth), ki ne obstajajo.

---

## 1. Walk-forward napoved letnih reklamacij po kategorijah

**Datoteka:** `backtest_kategorije.py`
**Namen:** napovedati letno število reklamacij za vsako od 6 kategorij napak
(podpora načrtovanju servisnih kapacitet in zalog).

### Podatki

- **Vhod:** agregirana tabela leto × kategorija × število (do 72 vrstic:
  12 let × 6 kategorij); na kategorijo časovna vrsta 12 letnih vrednosti.
- **Ciljna spremenljivka:** letno število reklamacij v kategoriji.
- **Značilke:** samo koledarsko leto (univariatna regresija na trend).
- **Čiščenje:** izločeni zapisi brez datuma prejema ali brez določljive
  kategorije; manjkajoča leta dopolnjena z 0.

### Modeli in validacija

Linearna regresija, Ridge (α = 1,0) in polinomska regresija 2. stopnje.
Validacija: *walk-forward* z rastočim oknom (minimalno 4 leta treninga,
8 testnih let 2017–2024 na kategorijo, skupaj 48 testnih točk). Izbor
»najboljšega« modela poteka na zadnjem trening letu (validacija), **brez
pogleda v testno leto** — prejšnja različica je izbirala po dejanski testni
vrednosti, kar je uhajanje podatkov.

### Rezultati

| Kategorija | MAE | MAPE | RMSE | Prevladujoči model | Naivni baseline (MAE) | Izboljšava |
|---|---:|---:|---:|---|---:|---:|
| Optične komponente | 41,1 | 10,1 % | 48,5 | Linearna | 67,5 | **+39 %** |
| Elektronske komponente | 36,5 | 12,0 % | 45,9 | Ridge | 47,8 | **+24 %** |
| Mehanske komponente | 31,1 | 34,3 % | 41,2 | Ridge | 21,6 | −44 % |
| Ni tehnična napaka | 49,8 | 102,2 % | 60,1 | Linearna | 24,0 | −108 % |
| Enota za sprej | 26,2 | 627,0 % | 31,6 | Linearna | 14,5 | −81 % |
| Hladilni sistem | 11,0 | 68,6 % | 12,8 | Linearna | 9,0 | −22 % |

*Baseline: naivna napoved (vrednost prejšnjega leta), izračunana na istih
testnih letih v `backtest_kategorije_multivariant.py`.*

![Walk-forward backtest po kategorijah](fotona_backtest_kategorije.png)

### Interpretacija

- MAE 41 pri optičnih pomeni povprečno zgrešitev ~41 reklamacij pri letnih
  vrednostih 345–637, kar je ~10 % — za letno načrtovanje kapacitet povsem
  uporabno.
- Pri velikih kategorijah s stabilnim trendom (optične, elektronske) linearni
  trend **izrazito premaga naivni pristop** (+39 % oz. +24 %).
- Pri majhnih in nestabilnih kategorijah je model **slabši od naivnega**:
  vrednosti blizu nič (sprej: 1–26 reklamacij letno po 2019) napihnejo MAPE
  v nesmiselne odstotke (627 %), padec kategorije *ni tehnična napaka* pa je
  artefakt preloma taksonomije, ki mu trend iz preteklosti ne more slediti.
- MAPE je za kategorije z majhnimi vrednostmi **napačna metrika**; smiselna je
  samo absolutna napaka.

### Ocena uporabnosti

- **Produkcija: DA — pogojno**, samo za optične in elektronske komponente.
  Za ostale kategorije je naivna napoved boljša in bistveno enostavnejša.
- **Poslovna vrednost:** letno načrtovanje servisnih kapacitet in zalog
  rezervnih delov za dve največji kategoriji (skupaj ~70 % vseh reklamacij)
  z napako ~10–12 %.
- **Preprileganje:** polinomska regresija 2. stopnje na 4–11 točkah je
  strukturno nagnjena k preprileganju in po odpravi uhajanja praktično nikoli
  ni izbrana kot najboljša. Linearna/Ridge na tako kratkih vrstah nista
  preprilegani, sta pa **premalo prilagojeni** (underfitting) za kategorije s
  strukturnim prelomom.

---

## 2. Multivariantna primerjava napovednih modelov

**Datoteka:** `backtest_kategorije_multivariant.py`
**Namen:** preveriti, ali eksterni prediktorji (prihodki podjetja, pretekle
reklamacije, servisni posegi) izboljšajo napoved letnih reklamacij glede na
naivni baseline.

### Podatki

- Isti agregat leto × kategorija kot model 1; dodatno letni prihodki
  (13 vrstic) in letni servisni posegi (5 vrstic, samo 2020–2024).
- **Značilke po modelih:** leto; prihodki(t−1); reklamacije(t−1);
  reklamacije(t−1, t−2); posegi(t−1) in kombinacije — vsi lagi so znani pred
  testnim letom (brez uhajanja).

### Rezultati (48 testnih točk, 2017–2024)

| Model | MAE | RMSE | R² | vs. naivni |
|---|---:|---:|---:|---:|
| **Naivni (t−1)** | **30,7** | 44,0 | 0,935 | — |
| Lin(leto) | 32,3 | 42,4 | 0,940 | −5,2 % |
| Lin(rek_lag1) | 33,4 | 44,5 | 0,933 | −8,8 % |
| Lin(leto+rek) | 35,7 | 49,0 | 0,919 | −16,1 % |
| AR2 | 45,0 | 65,5 | 0,870 | −46,4 % |
| Lin(leto+prihodki) | 50,9 | 75,3 | 0,810 | −65,7 % |
| Poisson(leto+prihodki) | 120,0 | 322,3 | −2,485 | −290,4 % |
| Modeli s posegi (4×) | N/A | N/A | N/A | ni napovedi |

Po kategorijah pa Lin(leto) premaga naivnega pri elektronskih (MAE 36,0,
+25 %) in optičnih (MAE 38,6, +43 %) — skladno z modelom 1.

![Multivariantna primerjava](fotona_backtest_final.png)

### Interpretacija in manjkajoči rezultati

- **Visok R² (0,94) je zavajajoč:** izračunan je čez vse kategorije skupaj,
  kjer varianco dominirajo razlike *med* kategorijami (optične ~600 vs.
  hladilni ~20), ki jih »pojasni« vsak model. Prava mera je MAE proti naivnemu.
- **Prihodki kot prediktor škodijo** (−66 %): rast prihodkov 2021–2023 se ne
  prenaša linearno v reklamacije.
- **Poisson se ni uspešno naučil:** log-povezava s surovim koledarskim letom
  (~2020) v eksponentu povzroči eksplozivno ekstrapolacijo (napoved 352 pri
  dejanskih 38). Model bi zahteval centrirano leto in ekspozicijo.
- **Modeli s posegi nimajo nobene napovedi (N/A):** posegi obstajajo šele od
  2020, skripta pa ob manjkajočih vrednostih v trening oknu napoved izpusti —
  vsa trening okna pred 2020 vsebujejo manjkajoče vrednosti.

### Ocena uporabnosti

- **Produkcija: NE** za vse multivariantne različice — nobena ne premaga
  naivnega baselina. Vrednost skripte je **dokazna**: pošteno pokaže, da
  letna granulacija ne omogoča izboljšave z eksternimi prediktorji.
- **Preprileganje:** AR2 (2 parametra na 5–9 učnih točkah) in Poisson sta
  šolska primera preprileganja oz. nestabilne ekstrapolacije na premajhnem
  vzorcu.

---

## 3. Servisni posegi kot prediktor reklamacij — letna raven

**Datoteka:** `koleracije_posegi_reklamacijami.py`
**Namen:** test hipoteze, da število servisnih posegov napoveduje reklamacije
naslednjega leta.

### Podatki

- Na kategorijo: 12 vrstic (leta 2013–2024) × 5 stolpcev (leto, reklamacije,
  posegi, svc_lag1, rekl_lag1); lagi ustvarjeni s `shift(1)`, manjkajoče
  vrednosti se ne imputirajo.
- Posegi so na voljo **samo od 2020**, zato imata modela A/B po kategoriji
  le 2 veljavni testni točki (2023, 2024) — skupaj 12.

### Rezultati

| Model | N | MAE | RMSE | R² | vs. naivni |
|---|---:|---:|---:|---:|---:|
| Naivni | 48 | 30,7 | 44,0 | 0,935 | — |
| A: Lin(svc_lag1) | 12 | 30,9 | 45,3 | 0,961 | −0,6 % |
| B: Lin(rekl+svc) | 12 | 42,7 | 55,0 | 0,943 | −38,8 % |

Korelacija na letni ravni: r = 0,880 (p = 0,049) sočasno; r = 0,874
(p = 0,126) z zamikom enega leta — na samo 5 letih podatkov.

![Letna analiza svc](fotona_backtest_svc_clean.png)

### Interpretacija

- Rezultat je **neodločen, ne negativen**: 12 testnih točk (2 na kategorijo)
  ne zadošča za noben statistično veljaven sklep. Posamezne kategorije
  (npr. *ni tehnična napaka*: MAE 4,0 proti naivnim 24,0) kažejo obetavne
  vrednosti, a na n = 2 to ni dokaz.
- Visoka sočasna korelacija je pričakovana (obe vrsti rasteta s prodajo) in
  sama po sebi ne dokazuje napovedne moči.

### Ocena uporabnosti

- **Produkcija: NE** — premalo podatkov na letni ravni. Prava rešitev je
  mesečna granulacija (model 4). Skripta je metodološko zgledna (pošten
  baseline, brez uhajanja, eksplicitne omejitve) in kot taka primerna za
  prikaz metode v nalogi.

---

## 4. Servisni posegi kot prediktor reklamacij — mesečna raven

**Datoteka:** `posegi_reklamacije_mesecno.py`
**Namen:** ista hipoteza kot model 3, a na mesečni granulaciji, ki da
statistično smiseln vzorec.

### Podatki

- 60 mesecev (2020-01 do 2024-12), skupne mesečne reklamacije (povprečje
  87,3/mesec) in posegi (55,5/mesec); analiza na skupni ravni (ne po
  kategorijah) zaradi preloma taksonomije in ničelnih mesecev malih kategorij.
- **Značilke:** rekl_lag1, rekl_lag12, svc_lag1..3 (vse s `shift`, brez
  uhajanja). Walk-forward z rastočim oknom, MIN_TRAIN = 24 mesecev →
  **36 testnih mesecev** (2022-01 do 2024-12).

### Rezultati

Korelacije: posegi(t) r = +0,686 (p < 0,0001); posegi(t−1) r = +0,382
(p = 0,003); posegi(t−2) r = +0,410 (p = 0,001) — **statistično značilen
predhodni signal**.

| Model | MAE | RMSE | R² | vs. naivni | Premaga naivnega? |
|---|---:|---:|---:|---:|---|
| Naivni (t−1) | 24,4 | 31,0 | −0,882 | — | — |
| Sezonski naivni (t−12) | 22,6 | 29,5 | −0,698 | +7,4 % | ✓ |
| **AR(1)** | **21,3** | **27,4** | −0,466 | **+12,7 %** | ✓ |
| SVC(1..3) | 21,8 | 27,0 | −0,424 | +10,7 % | ✓ |
| AR+SVC | 21,6 | 27,5 | −0,480 | +11,6 % | ✓ |
| Ridge(AR+SVC) | 21,6 | 27,5 | −0,480 | +11,6 % | ✓ |

![Mesečna analiza svc](fotona_posegi_reklamacije_mesecno.png)

### Interpretacija

- **Vsi modeli premagajo naivnega** na 36 testnih točkah — prvi robusten
  pozitiven rezultat napovednega modeliranja v projektu.
- Model samo iz posegov (SVC 1..3) premaga naivnega za 10,7 %: servisna
  aktivnost **nosi napovedni signal** za reklamacije 1–2 meseca vnaprej.
  Vendar kombinacija AR+SVC (11,6 %) ne preseže AR(1) (12,7 %) — posegi
  torej ne dodajo informacije *nad* lastno zgodovino reklamacij.
- Negativni R² pri vseh modelih pove, da je napoved slabša od konstante
  povprečja *testnega obdobja* — mesečna vrsta je zelo šumna; kljub temu je
  relativna primerjava MAE med modeli veljavna in konsistentna.

### Ocena uporabnosti

- **Produkcija: DA** — AR(1) kot preprosta mesečna operativna napoved
  (napaka ~21 reklamacij pri povprečju ~100/mesec v zadnjih letih).
- **Poslovna vrednost:** zgodnje zaznavanje rasti obsega reklamacij ~1 mesec
  vnaprej; posegi kot potrditveni indikator.
- **Preprileganje:** nizko tveganje — modeli imajo 1–3 parametre na
  24–59 učnih točkah.

---

## 5. Detekcija anomalij v mesečnih reklamacijah

**Datoteka:** `anomaly_detection.py`
**Namen:** identificirati mesece z nenavadnim številom reklamacij
(nadzor kakovosti, prepoznavanje izrednih dogodkov).

### Podatki

- 144 mesečnih točk (2013-01 do 2024-12) → 132 po odstranitvi prvih 12
  (izračun medletne spremembe).
- **Značilke (IF):** število reklamacij, drseče povprečje 3M, drseči std 3M,
  sezonski indeks. Standardizacija s `StandardScaler`.

### Rezultati

| Metoda | Nastavitve | Št. anomalij | Delež |
|---|---|---:|---:|
| Z-score | prag \|z\| > 2 | 5 | 3,8 % |
| Isolation Forest | 200 dreves, contamination = 0,10 | 14 | 10,6 % |
| **Konsenz obeh** | — | **5** | 3,8 % |

Potrjene anomalije: **2020-04** (24 reklamacij, z = −2,06 — COVID zaprtje),
**2023-06** (156, z = 3,40), **2024-01** (127, z = 2,20), **2024-03** (132,
z = 2,41), **2024-07** (154, z = 3,32).

![Detekcija anomalij](fotona_anomaly_detection.png)

### Interpretacija in manjkajoče metrike

- Klasifikacijskih metrik (Precision/Recall/F1/ROC-AUC) **ni mogoče
  izračunati**, ker ne obstaja označen seznam »resničnih« anomalij. Posredna
  validacija: obe neodvisni metodi se strinjata v vseh 5 primerih in vse
  imajo jasno domensko razlago (COVID; porast obsega 2023–2024).
- Metodološka omejitev: z-score uporablja globalno povprečje in odklon
  celotne vrste — pri naraščajočem trendu sistematično označuje novejše
  vrhove. `contamination = 0,10` je arbitraren in vsili 10 % anomalij.

### Ocena uporabnosti

- **Produkcija: DA** — kot retrospektivno orodje za nadzor in razlago
  (mesečno poročanje, opozorila). Za sprotno (online) detekcijo bi bilo
  treba statistike računati samo iz preteklih podatkov.
- **Poslovna vrednost:** hitro usmerjanje pozornosti vodstva na izredne
  mesece; kvantitativna podpora razlagi učinkov COVID in rasti 2023–2024.

---

## 6. Napoved časa reševanja reklamacije

**Datoteka:** `fotona_solution_time.py`
**Namen:** napovedati trajanje reševanja reklamacije v dnevih (upravljanje
pričakovanj strank, načrtovanje).

### Podatki

- **9.988 reklamacij** (2013–2025); tarča: dnevi od prejema do zaključka,
  omejeno na 1–730 dni. Porazdelitev izrazito asimetrična: povprečje 56,5,
  mediana 43, std 49,1 dni.
- **Značilke (6):** kategorija (LabelEncoder), garancija (0/1),
  normalizirano leto, indikatorji četrtletij Q1–Q3.
- **Transformacije:** log1p tarče (asimetrija), metrike preračunane nazaj
  v dneve.
- **Validacija:** TimeSeriesSplit (5 delitev) — podatki so urejeni po datumu
  in porazdelitev časov se s časom spreminja (2013: 81,6 dni → 2014–21: ~47
  → 2022–24: 62–75), zato bi navadni k-fold mešal prihodnost v učenje.

### Rezultati

| Model | MAE (dni) | RMSE | R² | vs. baseline mediana |
|---|---:|---:|---:|---:|
| Baseline (mediana treninga) | 31,3 | — | — | — |
| **Gradient Boosting** | **29,8** | 46,7 | −0,047 | **+4,8 %** |
| HistGB (mediana, kvantilni) | 30,1 | 46,8 | −0,050 | +3,8 % |
| Linearna / Ridge | 30,3 | 48,0 | −0,109 | +3,2 % |
| Random Forest | 30,6 | 47,2 | −0,074 | +2,2 % |

Pomembnost značilk (RF): leto 0,43 > kategorija 0,22 > garancija 0,13 >
sezona ~0,22 skupaj.

Kvantilne napovedi za 2025 (mediana [P10–P90]), izbrani primeri:
optične brez garancije **71 dni [36–112]**, optične z garancijo
**29 dni [10–67]**, elektronske brez garancije **73 dni [28–175]**.

![Model časov reševanja](fotona_casi_model.png)

### Interpretacija

- **Točkovna napoved je praktično brez vrednosti:** najboljši model premaga
  trivialno mediano le za 4,8 %, R² ≈ 0 pomeni, da razpoložljive značilke ne
  pojasnijo variance med posameznimi reklamacijami. To je **premajhna
  prilagoditev (underfitting)** zaradi prešibkih značilk, ne slabost
  algoritmov — vsi štirje algoritmi konvergirajo k isti napaki.
- **Kvantilni pogled pa je uporaben:** intervali P10–P90 se smiselno
  razlikujejo po kategorijah in garanciji (garancijske ~2× hitrejše) in so
  statistično pošteni (kvantili so invariantni na log-transformacijo).
- Opisne ugotovitve so trdne: garancija 50,3 vs. negarancija 66,1 dni;
  izrazito podaljševanje časov 2022–2024.

### Ocena uporabnosti

- **Produkcija: NE za točkovne napovedi; DA za kvantilne intervale** kot
  orodje za komunikacijo pričakovanj (»80 % tovrstnih reklamacij rešimo v
  X–Y dneh«).
- **Poslovna vrednost:** realistična pričakovanja strank in interna
  diagnostika (rast časov 2022–2024 zahteva organizacijsko, ne modelsko
  ukrepanje).
- **Kaj manjka za boljši model:** značilke o vsebini reklamacije (družina
  izdelka, trg, razpoložljivost delov, obremenitev servisa) — brez njih
  varianca ostaja nepojasnjena.

---

## 7. Končni povzetek

### Razvrstitev modelov (od najboljšega do najslabšega)

| # | Model (datoteka) | Ključna številka | Ocena |
|---:|---|---|---|
| 1 | AR(1) mesečno (`posegi_reklamacije_mesecno.py`) | MAE 21,3; +12,7 % nad naivnim, n=36 | **Najbolj obetaven** — edini robustno premaga baseline |
| 2 | Lin(leto) za optične/elektronske (`backtest_kategorije.py`) | +39 % / +24 % nad naivnim | Uporaben za letno načrtovanje velikih kategorij |
| 3 | Z-score + Isolation Forest (`anomaly_detection.py`) | 5 potrjenih anomalij, konsenz obeh metod | Deluje; brez formalnih metrik (ni označb) |
| 4 | SVC(1..3) mesečno | +10,7 % nad naivnim | Dokaz signala posegov; ne preseže AR(1) |
| 5 | Kvantilni HistGB (`fotona_solution_time.py`) | intervali P10–P90 po kategorijah | Uporaben kot interval, ne kot točkovna napoved |
| 6 | GB/Lin/RF za čase reševanja | MAE 29,8; +4,8 % nad mediano; R² ≈ 0 | Premajhna prilagoditev — prešibke značilke |
| 7 | Modela A/B letno (`koleracije_...py`) | n = 12 testnih točk | Neodločeno — premalo podatkov |
| 8 | Lin(rek_lag1), Lin(leto+rek), AR2 | −9 % do −46 % pod naivnim | Slabši od trivialnega pristopa |
| 9 | Lin(leto+prihodki) | −66 % pod naivnim | Prihodki niso uporaben prediktor |
| 10 | Poisson(leto+prihodki) | MAE 120; R² = −2,49 | Neuporaben — eksplozivna ekstrapolacija |

### Modeli, priporočeni za uporabo

1. **AR(1) na mesečni ravni** — operativna mesečna napoved obsega reklamacij.
2. **Linearni trend za optične in elektronske komponente** — letno
   načrtovanje (~70 % vseh reklamacij, napaka 10–12 %).
3. **Konsenzna detekcija anomalij** — mesečni nadzor s pridržkom
   retrospektivnosti.
4. **Kvantilni intervali časov reševanja** — komunikacija pričakovanj.

### Modeli, ki niso primerni za uporabo

- **Poisson(leto+prihodki)** — napačna parametrizacija (surovo leto v
  log-povezavi); potreboval bi centrirano leto in ekspozicijo.
- **Vsi modeli s prihodki** — poslovna rast se ne prenaša linearno v
  reklamacije.
- **Točkovne napovedi časov reševanja** — R² ≈ 0; brez bogatejših značilk ni
  osnove za individualno napoved.
- **Letni modeli s posegi (A/B)** — strukturno premalo podatkov (posegi šele
  od 2020); nadomešča jih mesečna analiza.

### Skupni metodološki sklep za nalogo

Rezultati konsistentno kažejo znano lastnost kratkih poslovnih časovnih vrst:
**preprosti modeli z majhnim številom parametrov premagajo kompleksnejše**,
ključni dobički pa ne pridejo iz algoritmov, temveč iz (1) pravilne
granulacije podatkov (letna → mesečna), (2) poštenih baselinov in
(3) čiste, časovno pravilne validacije brez uhajanja podatkov.
