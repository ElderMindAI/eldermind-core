# eldermind-core

Deterministyczny silnik obliczeniowy stojący za produktami Eldermind.

Jedna zasada: **wszystko tutaj jest czystą funkcją swoich argumentów.** Żadnych
wywołań LLM, bazy danych, frameworka HTTP ani renderowania PDF. To właśnie ta
własność sprawia, że wyniki da się cache'ować i objąć kontraktem publicznego API.

## Osiem systemów

| Moduł | Co liczy |
|---|---|
| `services/ephemeris.py` | Astrologia zachodnia (Placidus, aspekty ptolemejskie), wedyjska (Lahiri, Whole Sign, nakszatry), karta drakoniczna, okna tranzytowe |
| `services/vedic_dasha.py` | Vimshottari Dasha (maha + antar), Avakahada Chakra |
| `services/sade_sati.py` | Sade Sati — trzy fazy, wyszukiwanie ingresów Saturna |
| `services/human_design.py` | Typ, strategia, autorytet, profil, definicja, kanały, centra, krzyż inkarnacyjny. Moment Design metodą Newtona-Raphsona (dokładne 88° Słońca) |
| `services/gene_keys.py` | Profil hologenetyczny: sekwencje Activation, Venus, Pearl |
| `services/matrix_destiny.py` | Matryca Losu: wierzchołki, linie, Personal Destiny 40, oś dekad |
| `services/bazi.py` | Cztery Filary, Day Master, Dziesięciu Bogów, bilans elementów, Na Yin, Da Yun |
| `services/numerology.py` | Numerologia pitagorejska (liczby mistrzowskie zachowane) |
| `services/animal_design.py` | Animal Design — autorski system 15 bram ssaczych |
| `services/geocoder.py` | Nazwa miejsca → lat/lon/IANA tz |

`knowledge/` zawiera ~1 MB opisów (bramy, kanały, linie, centra, typy, autorytety,
profile, Gene Keys). To materiał opisowy — nie bierze udziału w żadnym obliczeniu.

## Instalacja

```bash
pip install -e .          # tryb deweloperski
pip install .             # zwykła instalacja
```

`pyswisseph` na Windowsie wymaga kompilatora MSVC albo gotowego koła.

## Testy

```bash
pytest
```

## Wersjonowanie

`ENGINE_VERSION` w `eldermind_core/__init__.py` opisuje **semantykę obliczeń**,
nie sposób pakowania. Dwie instalacje o tym samym `ENGINE_VERSION` muszą zwrócić
identyczne wyniki dla identycznych danych wejściowych — pilnują tego testy złote.
Zmiana, która rusza choćby jedną liczbę, wymaga podbicia tej wartości; trafia ona
do klucza cache'u i do nagłówka `X-Engine-Version` w publicznym API.

## Kto z tego korzysta

* **Backend Calculator Engine** — produkt raportowy (LLM, PDF, Supabase)
* **eldermind-astro-api** — publiczne REST + MCP

Kod obliczeniowy nie może się rozjechać między tymi serwisami — dlatego żyje tutaj.
