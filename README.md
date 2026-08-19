# Blue Team Simulator - symulator KQL

Modularna aplikacja treningowa dla analityków SOC do nauki pisania prawdziwych
zapytań KQL (Kusto Query Language) na syntetycznych danych w stylu Microsoft
Sentinel / Defender Advanced Hunting.

**Uwaga o autorstwie:** cała aplikacja - kod, silnik KQL, dane syntetyczne,
treści ćwiczeń/lekcji/scenariuszy oraz ta dokumentacja - jest pisana przez
Claude (Anthropic) w Claude Code, pod nadzorem i kierunkiem Maciej Gorzny.
Zakres, priorytety i akceptację każdej zmiany ustala człowiek; implementację
generuje asystent AI.

## Struktura

```
core/kql_engine/
  errors.py       błędy z lokalizacją (linia/kolumna) w zapytaniu
  tokenizer.py    tekst zapytania -> lista tokenów
  ast_nodes.py    definicje węzłów AST (Query, Stage, Expr, LetStatement, ListExpr, ...)
  parser.py       tokeny -> AST
  eval.py         ewaluacja wyrażeń (where/extend/project) na wierszu danych
  executor.py     wykonuje AST na tabelach (list[dict]) krok po kroku, w tym `let`
  operators/      po jednym pliku na operator + rejestr w __init__.py
  functions/      funkcje skalarne (string/datetime/logiczne) + rejestr
core/datasets/
  schema.py                    ColumnSchema/TableSchema (metadane, nieegzekwowane przez silnik)
  device_process_events.py     syntetyczny DeviceProcessEvents (najbardziej rozbudowany)
  device_logon_events.py       syntetyczny DeviceLogonEvents
  device_network_events.py     syntetyczny DeviceNetworkEvents
  device_file_events.py        syntetyczny DeviceFileEvents
  signin_logs.py                syntetyczny SigninLogs (Entra ID)
  email_events.py               syntetyczny EmailEvents (Defender for Office 365)
  office_activity.py            syntetyczny OfficeActivity
  __init__.py                  rejestr datasetów (DATASETS)
core/scenarios/
  schema.py       model danych ćwiczenia (Scenario, kryteria walidacji)
  loader.py       wczytuje ćwiczenia z plików JSON
  validator.py    sprawdza zapytanie użytkownika wg kryteriów ćwiczenia
  importer.py     import/usuwanie ćwiczeń przez UI (JSON -> plik w imported/)
  log_store.py    wspólna, wciąż rosnąca pula logów (wbudowane + zaimportowane)
  kql_basics/     pliki *.json - jedno ćwiczenie na plik, ponumerowane (30 sztuk)
  imported/       ćwiczenia zaimportowane przez UI (gitignored, tworzone w locie)
core/lessons/
  schema.py, loader.py, __init__.py
  basics/         pliki *.json - jedna lekcja na plik (16 sztuk), uczą pojedynczych
                  poleceń KQL (where, join, let, dynamic()+in, ...)
core/incidents/
  schema.py, loader.py, __init__.py
  basics/         pliki *.json - jeden scenariusz na plik (9 sztuk), każdy to
                  uporządkowana lista kroków (ćwiczenie KQL albo checklista
                  reakcji IR bez oceniania), opowiadająca pełną historię incydentu
app/
  main.py               instancja FastAPI, montuje static/, podpina routery
  routers/               pages.py (strony HTML) i api.py (JSON API, niezależne od frontendu)
  scenario_registry.py   pomocnicze funkcje do odczytu ćwiczeń
  lesson_registry.py     pomocnicze funkcje do odczytu lekcji
  incident_registry.py   pomocnicze funkcje do odczytu scenariuszy
  templates/             Jinja2 (jeden wspólny szkielet strony, scenario_shell.html)
  static/                style.css (dark theme), app.js (edytor, podświetlanie,
                          fetch, cały routing bez przeładowania strony)
tests/            testy pytest, jeden plik na temat/operator/warstwę
examples/         małe, samodzielne przykłady bez potrzeby znajomości pytest ani przeglądarki
```

`core/` nie importuje niczego z `app/` - silnik/datasety/ćwiczenia pozostają
reużywalne przez przyszłe moduły, które mogą w ogóle nie mieć frontendu
webowego.

## Jak to uruchomić

1. Sprawdź wersję Pythona: `python3 --version` (potrzeba 3.11+).
2. Utwórz wirtualne środowisko (raz, w katalogu głównym projektu):
   `python3 -m venv .venv`
3. Zainstaluj zależności do środowiska:
   `.venv/bin/pip install -r requirements.txt -r requirements-dev.txt`
4. Uruchom testy: `.venv/bin/python -m pytest`
   - powinno pokazać `301 passed`.
5. Uruchom aplikację webową: `./run.sh` (domyślnie port 8731, można nadpisać
   zmienną środowiskową `PORT`) i otwórz w przeglądarce
   **http://127.0.0.1:8731/** - przekieruje na listę ćwiczeń.
6. Żeby zobaczyć sam silnik "na żywo" (bez przeglądarki):
   `.venv/bin/python -m examples.run_demo`
7. Żeby zobaczyć pełny przepływ ćwiczenia w terminalu (zadanie -> błędna
   próba z feedbackiem -> poprawna próba):
   `.venv/bin/python -m examples.run_scenario_demo`

Od teraz zawsze używaj `.venv/bin/python`, `.venv/bin/pytest` itd. zamiast
gołego `python3`/`pytest` - inaczej trafisz w system Pythona bez FastAPI.

## Silnik KQL

**Operatory:** `where`, `project`, `extend`, `sort by`/`order by` (domyślnie
malejąco, zgodnie z prawdziwym Kusto), `take`/`limit`, `distinct` (w tym
`distinct *`), `count`, `summarize` (z `by` i agregacjami `count()`, `sum()`,
`avg()`, `dcount()`, `min()`, `max()`), `join` (`kind=inner`, `kind=leftouter`
- `kind=` jest wymagane jawnie, bo prawdziwy Kusto ma tu domyślny, nietrywialny
tryb `innerunique`, którego ten silnik nie obsługuje), `let` (wiązanie nazwanych
stałych/list przed właściwym zapytaniem tabelarycznym).

**Funkcje skalarne:** `contains`, `startswith`, `endswith`, `has` (dopasowanie
po całych tokenach, nie substring!), `matches regex` (silnik regex Pythona -
bliski, ale nie identyczny z RE2 z prawdziwego Kusto), `tolower`, `toupper`,
`strcat`, `split`, `ago()`, `now()`, `bin()`, `not()`, `dynamic()` (tworzy
listę do użytku z operatorem `in`).

**Operatory logiczne/arytmetyczne:** `and`, `or`, `not(...)`, `==`, `!=`, `<`,
`<=`, `>`, `>=`, `+`, `-`, `*`, `/`, `%`, `in` (przynależność do listy).
Literały timespan (`1d`, `30m`, `2h`, `500ms`) do użytku z `ago()`/`bin()`.

Błędy parsera i wykonania wskazują dokładne miejsce w zapytaniu (linia, kolumna,
fragment z podkreśleniem `^^^`) - przykład:

```
Nieznana kolumna 'FileNamee'.
  linia 1, kolumna 29:
  DeviceProcessEvents | where FileNamee == 'cmd.exe'
                              ^^^^^^^^^
```

**Ważna niuansa semantyczna:** `has` dopasowuje tylko całe tokeny
alfanumeryczne, więc np. `CommandLine has "-enc"` **nie zadziała** (myślnik nie
jest częścią tokenu) - trzeba użyć `contains "-enc"`. To zachowanie jest zgodne
z prawdziwym Kusto, nie jest błędem silnika.

**Składnia `join`:**

```
LeftTable | join kind=inner (RightTable) on KolumnaWspólna
LeftTable | join kind=leftouter (RightTable | where X == 1) on $left.A == $right.B
```

Prawa strona joina to dowolne wyrażenie tabelaryczne (może mieć własne `where`/
`project`/itd. w nawiasach). `on Kolumna` to skrót, gdy nazwa kolumny jest taka
sama po obu stronach - w wyniku pojawia się tylko raz (z lewej tabeli). Jeśli
inna kolumna (nie klucz) koliduje nazwą w obu tabelach, kolumna z prawej strony
dostaje sufiks `1` (np. `AccountName` i `AccountName1`) - zamiast cicho
nadpisywać lewą. Dla `kind=leftouter` niedopasowane wiersze z lewej tabeli
dostają `None` na kolumnach z prawej strony.

**Składnia `let` + `dynamic()` + `in`:**

```
let suspicious = dynamic(['powershell.exe', 'cmd.exe', 'mshta.exe']);
DeviceProcessEvents | where FileName in (suspicious) | count
```

`let` wiąże nazwaną wartość (skalar albo listę z `dynamic()`) obliczaną raz,
przed przetworzeniem tabeli - odwołanie wewnątrz `let` do prawdziwej kolumny
jest błędem (bindingi liczą się względem pustego wiersza). `in` wymaga listy
po prawej stronie: `x in ('a')` traktuje pojedynczy literał jako
jednoelementowy zbiór, a `x in (nazwa)` odwołuje się do listy związanej przez
`let`. Nie ma dedykowanego `!in` - neguj przez `not(x in (...))`.

## Datasety

7 modułów w `core/datasets/`, każdy w pełni deterministyczny (bez modułu
`random`), żeby "poprawna odpowiedź" nigdy się nie rozjechała z danymi:

- `device_process_events.py` - DeviceProcessEvents, najbardziej rozbudowany:
  dziesiątki wstrzykniętych anomalii, każda zmapowana na technikę MITRE
  ATT&CK, wiele powiązanych w spójne, wieloetapowe łańcuchy ataku
- `device_logon_events.py` - DeviceLogonEvents
- `device_network_events.py` - DeviceNetworkEvents, C2 beacony skorelowane
  czasowo z odpowiadającymi anomaliami procesów
- `device_file_events.py` - DeviceFileEvents
- `signin_logs.py` - SigninLogs (Entra ID): password spray, przejęcie tokenu
  (AiTM), rejestracja urządzenia przez device-code phishing
- `email_events.py` - EmailEvents (Defender for Office 365): kilka
  niezależnych kampanii phishingowych
- `office_activity.py` - OfficeActivity

Wszystkie tabele razem tworzą jedną wspólną, stale rosnącą "pulę logów"
(`core/scenarios/log_store.py`), do której zapytania odwołują się niezależnie
od tego, które ćwiczenie/scenariusz jest aktualnie otwarte - "Wolne
zapytania" (sandbox) też pyta o dokładnie tę samą pulę.

Dodanie nowego datasetu = nowy plik z `SCHEMA` i `ROWS`, plus jedna linia w
`core/datasets/__init__.py`. Zero zmian w silniku czy ćwiczeniach.

## Ćwiczenia

30 ćwiczeń w `core/scenarios/kql_basics/`, rosnącej trudności - od gołego
`where` po `join` + `summarize`. Kilkanaście z nich odtwarza techniki z
prawdziwych, publicznych analiz malware autora - link do oryginalnego
writeupu pojawia się dopiero po poprawnym rozwiązaniu, jako nagroda, nie
ściąga. Format JSON ćwiczenia (`core/scenarios/schema.py`):

```json
{
  "id": "...", "title": "...", "prompt": "...",
  "datasets": ["DeviceProcessEvents"],
  "difficulty": "beginner|intermediate|advanced",
  "mitre_techniques": ["T1218.011"],
  "hint": "...",
  "source_url": "https://...",
  "sc200_area": "Microsoft Defender for Endpoint (MDE)",
  "validation": {
    "result_match": {"reference_query": "...", "ordered": false},
    "required_usage": {"required_operators": ["SummarizeStage"], "required_columns": ["DeviceName"]}
  }
}
```

Dwa niezależne tryby walidacji (mogą wystąpić razem):
- **`result_match`** - wynik zapytania użytkownika musi zgadzać się z wynikiem
  `reference_query` uruchomionego *na żywo* na tym samym datasecie. Oczekiwany
  wynik nigdy nie jest zapisany na sztywno w JSON-ie, więc dataset i "poprawna
  odpowiedź" nigdy się nie rozjadą.
- **`required_usage`** - AST zapytania użytkownika musi używać wskazanych
  operatorów i/lub odwoływać się do wskazanych kolumn (dla zadań uczących
  konkretnej techniki, nie tylko konkretnego wyniku).

Każde ćwiczenie ma test regresyjny (`tests/test_scenarios/test_scenario_files.py`),
który uruchamia jego własny `reference_query` jako "odpowiedź użytkownika" i
sprawdza, że wypada poprawnie - więc zepsute ćwiczenie wywali się w testach,
zanim trafi na kogokolwiek trenującego.

Ćwiczenia można też importować przez UI (przycisk "Importuj ćwiczenie z
JSON") - format JSON obsługuje `custom_datasets`, więc zaimportowane
ćwiczenie może przynieść własne wiersze logów zamiast (albo obok) tabel
wbudowanych. Zaimportowane ćwiczenia da się usunąć z poziomu UI; wbudowanych
usunąć nie można. Zaimportowane pliki lądują w `core/scenarios/imported/`,
które jest w `.gitignore` (i tworzone w locie przy pierwszym imporcie) -
patrz sekcja o tym repo niżej.

## Lekcje

16 lekcji w `core/lessons/basics/`, osobno od ćwiczeń - uczą pojedynczego
polecenia/operatora KQL (opis + przykładowe, zwalidowane zapytanie), bez
oceniania. Przykład można wstawić jednym kliknięciem do tego samego, trwałego
edytora, w którym rozwiązuje się ćwiczenia i scenariusze, i samodzielnie go
uruchomić - po prostu bez sprawdzania poprawności.

## Scenariusze

9 scenariuszy w `core/incidents/basics/` (w kodzie i adresach URL wciąż pod
nazwą `Incident`/`/incidents/*` - patrz sekcja o nazewnictwie niżej). Każdy
scenariusz to uporządkowana lista kroków opowiadająca pełną historię
incydentu, łącząca dwa rodzaje kroków:

- **`investigation`** - odwołanie do istniejącego ćwiczenia po id;
  rozwiązanie kroku to dokładnie to samo, co rozwiązanie tego ćwiczenia z
  listy Ćwiczeń (współdzielą stan "rozwiązano").
- **`action`** - checklisty reakcji IR, których nie da się wykonać
  zapytaniem KQL (zablokuj konto, odwołaj sesję, sprawdź zarejestrowane
  urządzenia...); bez oceniania, odhaczane checkboxy zapamiętywane lokalnie
  w przeglądarce.

Kilka scenariuszy jest zbudowanych na bazie prawdziwych, publicznych analiz
incydentów autora (linki w `source_url` poszczególnych ćwiczeń), reszta to
warianty/kompozycje tych samych technik.

## Aplikacja webowa

FastAPI + Jinja2: strony HTML renderowane po stronie serwera + osobne, w
pełni niezależne od frontendu **JSON API**, żeby dało się je podpiąć pod
cokolwiek innego w przyszłości (np. React) bez zmian w silniku/danych.
Jedno wspólne okno (sidebar + trwały panel edytora) - przełączanie między
ćwiczeniem/lekcją/scenariuszem nigdy nie resetuje treści edytora ani wyniku,
tylko podmienia pasek informacyjny nad nim.

**Styl:** dark theme, system trzykolorowy (`--accent` = identyfikacja/nagłówki/
neutralne IoC, `--red` = zagrożenie/critical, `--green` = defense/gotowe),
JetBrains Mono w treści/kodzie (jeśli masz font zainstalowany lokalnie -
CSS nie ściąga go z sieci, żeby nie było zależności od CDN). Podświetlanie
składni w polu KQL jest jedynym wyjątkiem od reguły trzech kolorów -
zaimplementowane bez żadnej biblioteki: `app/static/app.js` nakłada
przezroczystą `<textarea>` na podświetlony `<pre>` (ten sam tekst,
zsynchronizowany scroll), a tokenizacja do podświetlenia jest prostym
regexem po stronie JS. Podświetlanie jest **case-sensitive** tak samo jak
prawdziwy parser silnika (`where` się podświetli, `Where` nie) - celowo, żeby
nie sugerować, że coś zadziała, gdy silnik by to odrzucił.

**Feedback przy błędnej odpowiedzi:** panel wyników zawsze pokazuje to, co
faktycznie zwróciło zapytanie użytkownika (nie oczekiwaną odpowiedź - to
byłoby ściągą, nie treningiem). Sam błąd parsowania/wykonania trafia do pola
`error` z pełnym komunikatem ze strzałką `^^^`, żeby dało się precyzyjnie
zlokalizować literówkę. Po poprawnym rozwiązaniu (jeśli ćwiczenie ma
`source_url`) pojawia się link do oryginalnego writeupu.

**Inne funkcje UI:** import/usuwanie ćwiczeń z poziomu przeglądarki, lokalne
(w `localStorage`) śledzenie "rozwiązano" i odhaczonych checklist reakcji
IR, ręcznie regulowana szerokość sidebaru, kolorowe odznaki trudności,
tagowanie obszaru SC-200 (dla osób przygotowujących się do egzaminu
Microsoft SC-200), tryb "Wolne zapytania" (sandbox) bez przypisanego
ćwiczenia.

Przetestowane automatycznie (`tests/test_app/`, FastAPI `TestClient`, 301
testów w całym repo) oraz ręcznie przez `curl` na realnie odpalonym
serwerze. Interfejs w prawdziwej przeglądarce testował wyłącznie człowiek
nadzorujący projekt - jeśli coś w UI wygląda nie tak, zgłoś to jako feedback
do kolejnej iteracji.

## Nazewnictwo w UI vs. w kodzie (celowa niespójność)

Sidebar ma trzy sekcje: "Ćwiczenia" (pojedyncze zadanie, jedno zapytanie do
napisania), "Lekcje" i "Scenariusze" (wieloetapowe symulacje pełnego
incydentu, łączące kilka ćwiczeń z krokami reakcji IR). Etykiety
"Ćwiczenia"/"Scenariusze" to zmiana z późniejszego etapu rozwoju - pierwotnie
(i wciąż w całym kodzie) to, co UI teraz nazywa "Ćwiczeniem", nosi nazwę
**Scenario** (`core/scenarios/`, klasa `Scenario`, trasy `/scenarios/*` i
`/api/scenarios/*`), a to, co UI nazywa "Scenariuszem", nosi nazwę
**Incident** (`core/incidents/`, klasa `Incident`, trasy `/incidents/*` i
`/api/incidents/*`).

Zmieniono tylko widoczne etykiety (szablon `scenario_shell.html`, teksty w
`app/static/app.js`, komunikaty błędów zwracane przez API) - nie
przemianowano klas, adresów URL ani struktury API, bo `Scenario`/`Incident`
są nazwami domenowymi używanymi w kilkunastu plikach w całym projekcie, a
pełne przemianowanie byłoby dużym, ryzykownym refaktorem czysto
kosmetycznym. Efekt: URL `/scenarios/{id}` prowadzi do czegoś, co sidebar
podpisuje "Ćwiczenia", a URL `/incidents/{id}` do czegoś, co sidebar
podpisuje "Scenariusze". Jeśli kiedyś to będzie doskwierać, pełne
przemianowanie trzeba będzie zrobić jako osobne zadanie.

## Czego celowo brakuje

W silniku: `mv-expand`, `make-series`, negowane formy operatorów tekstowych
(`!contains`, `!has`, ...).

W warstwie danych: autoryzacja/multi-user, trwała baza danych (dane
zaimportowane przez UI żyją tylko na dysku lokalnym, w pamięci procesu
niczego nie ma na stałe - restart serwera nie kasuje zaimportowanych
ćwiczeń, ale nic poza plikami JSON nie jest "bazą danych" w żadnym sensie),
historia poprzednich prób, punktacja/progres poza lokalnym "rozwiązano" i
odhaczonymi checklistami w przeglądarce.

To wszystko kolejne kierunki rozwoju, do ustalenia w miarę potrzeb.

## O tym repo

Kod źródłowy jest publiczny, ale `core/scenarios/imported/` jest celowo
wyłączone z repozytorium (`.gitignore`) - to katalog na ćwiczenia
zaimportowane lokalnie przez autora z osobnego narzędzia do analizy
malware, mogące zawierać prawdziwe wskaźniki włamania (hashe, domeny C2)
z realnych próbek, a nie tylko syntetyczne dane treningowe jak reszta
repozytorium.
