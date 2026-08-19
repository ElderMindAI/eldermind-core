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

Wymagany Python 3.11+.

```bash
pip install -e .          # tryb deweloperski
pip install .             # zwykła instalacja
```

`pyswisseph` na Windowsie wymaga kompilatora MSVC albo gotowego koła. Jeśli nie
masz Build Tools, `uv pip install` załatwia sprawę bez nich — jego cache trzyma
skompilowane koło.

## Testy

```bash
pytest          # 122 testy, w tym 29 złotych
```

Testy złote (`tests/golden/`) przypinają wyniki do zapisanych wartości
referencyjnych. Ruszenie choćby jednej liczby wywala build — to jest mechanizm,
który utrzymuje determinizm opisany wyżej, a nie deklaracja o dobrych intencjach.

## Wersjonowanie

`ENGINE_VERSION` w `eldermind_core/__init__.py` opisuje **semantykę obliczeń**,
nie sposób pakowania. Dwie instalacje o tym samym `ENGINE_VERSION` muszą zwrócić
identyczne wyniki dla identycznych danych wejściowych — pilnują tego testy złote.
Zmiana, która rusza choćby jedną liczbę, wymaga podbicia tej wartości; trafia ona
do klucza cache'u i do nagłówka `X-Engine-Version` w publicznym API.

## Kto z tego korzysta

* **[`eldermind-astro-api`](https://github.com/ElderMindAI/eldermind-astro-api)** — publiczne REST + MCP
* **`eldermind-report-backend`** — produkt raportowy (LLM, PDF, Supabase), repozytorium prywatne

Kod obliczeniowy nie może się rozjechać między tymi serwisami — dlatego żyje tutaj.

## Licencja

Kod jest **udostępniony do wglądu, nie open source**. Wolno go czytać, studiować
i oceniać; użycie w produkcie lub usłudze wymaga pisemnej zgody. Pełne warunki:
[`LICENSE`](LICENSE).

Katalog `knowledge/` opisuje systemy powstałe poza tym projektem (m.in. Human
Design, Gene Keys). Licencja nie rości sobie żadnych praw do tych systemów ani
ich nazw.
