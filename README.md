# Blue Team Simulator — symulator KQL (Fazy 1-4)

Modularna aplikacja treningowa dla analityków SOC. Ten katalog zawiera **Fazy 1-4**:
silnik KQL, syntetyczne datasety, scenariusze treningowe i działającą
aplikację webową (FastAPI + Jinja2) do ich rozwiązywania w przeglądarce.

## Struktura

```
core/kql_engine/
  errors.py       błędy z lokalizacją (linia/kolumna) w zapytaniu
  tokenizer.py    tekst zapytania -> lista tokenów
  ast_nodes.py    definicje węzłów AST (Query, Stage, Expr, ...)
  parser.py       tokeny -> AST
  eval.py         ewaluacja wyrażeń (where/extend/project) na wierszu danych
  executor.py     wykonuje AST na tabelach (list[dict]) krok po kroku
  operators/      po jednym pliku na operator + rejestr w __init__.py
  functions/      funkcje skalarne (string/datetime/logiczne) + rejestr
core/datasets/
  schema.py                    ColumnSchema/TableSchema (metadane, nieegzekwowane przez silnik)
  device_process_events.py     syntetyczny DeviceProcessEvents (dane + wstrzyknięte anomalie)
  device_logon_events.py       syntetyczny DeviceLogonEvents (do scenariusza z join)
  __init__.py                  rejestr datasetów (get_tables())
core/scenarios/
  schema.py       model danych scenariusza (Scenario, kryteria walidacji)
  loader.py       wczytuje scenariusze z plików JSON
  validator.py    sprawdza zapytanie użytkownika wg kryteriów scenariusza
  kql_basics/     pliki *.json - jeden scenariusz na plik, ponumerowane
app/
  main.py         instancja FastAPI, montuje static/, podpina routery
  routers/        pages.py (strony HTML) i api.py (JSON API - niezależne od frontendu)
  templates/      Jinja2 (base/scenario_list/scenario_detail)
  static/         style.css (dark theme, system 3-kolorowy), app.js (podświetlanie + fetch)
tests/            testy pytest, jeden plik na temat/operator/warstwę
examples/         małe, samodzielne przykłady bez potrzeby znajomości pytest ani przeglądarki
```

`core/` nie importuje niczego z `app/` — silnik/datasety/scenariusze pozostają
reużywalne przez przyszłe moduły Blue Team Simulator, które mogą w ogóle nie
mieć frontendu webowego.

## Jak to uruchomić (krok po kroku)

Ten projekt ma teraz prawdziwe zależności uruchomieniowe (FastAPI), więc
zamiast instalować pakiety globalnie, używamy **wirtualnego środowiska**
(`.venv`) — to standardowa, bezpieczna praktyka w Pythonie, izolowana od
reszty systemu.

1. Sprawdź wersję Pythona: `python3 --version` (potrzeba 3.11+).
2. Utwórz wirtualne środowisko (raz, w katalogu głównym projektu):
   `python3 -m venv .venv`
3. Zainstaluj zależności do środowiska:
   `.venv/bin/pip install -r requirements.txt -r requirements-dev.txt`
4. Uruchom testy: `.venv/bin/python -m pytest`
   — powinno pokazać `135 passed`.
5. Uruchom aplikację webową: `.venv/bin/uvicorn app.main:app --reload`
   i otwórz w przeglądarce **http://127.0.0.1:8000/** — przekieruje na listę
   scenariuszy. `--reload` sprawia, że zmiany w kodzie/szablonach są widoczne
   od razu, bez restartu.
6. Żeby zobaczyć sam silnik "na żywo" (bez przeglądarki):
   `.venv/bin/python -m examples.run_demo`
7. Żeby zobaczyć pełny przepływ scenariusza w terminalu (zadanie -> błędna
   próba z feedbackiem -> poprawna próba):
   `.venv/bin/python -m examples.run_scenario_demo`

Od teraz zawsze używaj `.venv/bin/python`, `.venv/bin/pytest` itd. zamiast
gołego `python3`/`pytest` — inaczej trafisz w system Pythona bez FastAPI.

## Co już działa (Fazy 1-2)

**Operatory:** `where`, `project`, `extend`, `sort by`/`order by` (domyślnie
malejąco, zgodnie z prawdziwym Kusto), `take`/`limit`, `distinct` (w tym
`distinct *`), `count`, `summarize` (z `by` i agregacjami `count()`, `sum()`,
`avg()`, `dcount()`, `min()`, `max()`), `join` (`kind=inner`, `kind=leftouter`
— `kind=` jest wymagane jawnie, bo prawdziwy Kusto ma tu domyślny, nietrywialny
tryb `innerunique`, którego ten silnik nie obsługuje).

**Funkcje skalarne:** `contains`, `startswith`, `endswith`, `has` (dopasowanie
po całych tokenach, nie substring!), `matches regex` (silnik regex Pythona —
bliski, ale nie identyczny z RE2 z prawdziwego Kusto), `tolower`, `toupper`,
`strcat`, `split`, `ago()`, `now()`, `bin()`, `not()`.

**Operatory logiczne/arytmetyczne:** `and`, `or`, `not(...)`, `==`, `!=`, `<`,
`<=`, `>`, `>=`, `+`, `-`, `*`, `/`, `%`. Literały timespan (`1d`, `30m`, `2h`,
`500ms`) do użytku z `ago()`/`bin()`.

Błędy parsera i wykonania wskazują dokładne miejsce w zapytaniu (linia, kolumna,
fragment z podkreśleniem `^^^`) — przykład:

```
Nieznana kolumna 'FileNamee'.
  linia 1, kolumna 29:
  DeviceProcessEvents | where FileNamee == 'cmd.exe'
                              ^^^^^^^^^
```

**Ważna niuansa semantyczna:** `has` dopasowuje tylko całe tokeny
alfanumeryczne, więc np. `CommandLine has "-enc"` **nie zadziała** (myślnik nie
jest częścią tokenu) — trzeba użyć `contains "-enc"`. To zachowanie jest zgodne
z prawdziwym Kusto, nie jest błędem silnika.

**Składnia `join`:**

```
LeftTable | join kind=inner (RightTable) on KolumnaWspólna
LeftTable | join kind=leftouter (RightTable | where X == 1) on $left.A == $right.B
```

Prawa strona joina to dowolne wyrażenie tabelaryczne (może mieć własne `where`/
`project`/itd. w nawiasach). `on Kolumna` to skrót, gdy nazwa kolumny jest taka
sama po obu stronach — w wyniku pojawia się tylko raz (z lewej tabeli). Jeśli
inna kolumna (nie klucz) koliduje nazwą w obu tabelach, kolumna z prawej strony
dostaje sufiks `1` (np. `AccountName` i `AccountName1`) — zamiast cicho
nadpisywać lewą. Dla `kind=leftouter` niedopasowane wiersze z lewej tabeli
dostają `None` na kolumnach z prawej strony.

## Datasety (Faza 3)

`core/datasets/device_process_events.py` — syntetyczny, w pełni deterministyczny
(bez `random`) odpowiednik tabeli `DeviceProcessEvents` z Defender Advanced
Hunting: 120 "normalnych" zdarzeń tła + 7 celowo wstrzykniętych anomalii, każda
zmapowana na technikę MITRE ATT&CK (zakodowany PowerShell, makro Office
uruchamiające cmd/PowerShell, rundll32 z DLL-em w `C:\Users\Public`, pobieranie
przez certutil, PsExec, mshta, persystencja przez schtasks). Kilka anomalii
tworzy spójny "łańcuch ataku" (ta sama komenda pobierania pojawia się w dwóch
zdarzeniach), żeby dało się je też korelować, nie tylko wyszukiwać pojedynczo.

`core/datasets/device_logon_events.py` — mały odpowiednik `DeviceLogonEvents`,
istnieje głównie po to, żeby scenariusz #7 miał z czym zrobić `join` (jedno
zdarzenie logowania `RemoteInteractive` tuż przed anomalią PsExec — klasyczny
wzorzec ruchu bocznego).

Dodanie nowego datasetu = nowy plik z `SCHEMA` i `ROWS`, plus jedna linia w
`core/datasets/__init__.py`. Zero zmian w silniku czy scenariuszach.

## Scenariusze (Faza 3)

7 scenariuszy w `core/scenarios/kql_basics/`, rosnącej trudności — od gołego
`where` po `join` + `summarize`. Format JSON scenariusza (zaprojektowany pod
przyszły import/generowanie, patrz docstring w `core/scenarios/schema.py`):

```json
{
  "id": "...", "title": "...", "prompt": "...",
  "datasets": ["DeviceProcessEvents"],
  "difficulty": "beginner|intermediate|advanced",
  "mitre_techniques": ["T1218.011"],
  "hint": "...",
  "validation": {
    "result_match": {"reference_query": "...", "ordered": false},
    "required_usage": {"required_operators": ["SummarizeStage"], "required_columns": ["DeviceName"]}
  }
}
```

Dwa niezależne tryby walidacji (mogą wystąpić razem):
- **`result_match`** — wynik zapytania użytkownika musi zgadzać się z wynikiem
  `reference_query` uruchomionego *na żywo* na tym samym datasecie. Oczekiwany
  wynik nigdy nie jest zapisany na sztywno w JSON-ie, więc dataset i "poprawna
  odpowiedź" nigdy się nie rozjadą.
- **`required_usage`** — AST zapytania użytkownika musi używać wskazanych
  operatorów i/lub odwoływać się do wskazanych kolumn (dla zadań uczących
  konkretnej techniki, nie tylko konkretnego wyniku). To bezpośredni pożytek
  z decyzji z Fazy 1, żeby budować prawdziwe AST zamiast płaskiego pipeline'u
  stringów.

Każdy scenariusz ma test regresyjny (`tests/test_scenarios/test_scenario_files.py`),
który uruchamia jego własny `reference_query` jako "odpowiedź użytkownika" i
sprawdza, że wypada poprawnie — więc zepsuty scenariusz wywali się w testach,
zanim trafi na kogokolwiek trenującego.

## Aplikacja webowa (Faza 4)

FastAPI + Jinja2, zgodnie z briefem: strony HTML server-side (bez SPA) +
osobne, w pełni niezależne od frontendu **JSON API**
(`POST /api/scenarios/{id}/run`), żeby dało się je podpiąć pod cokolwiek innego
w przyszłości (np. React) bez zmian w silniku/scenariuszach.

**Styl:** dark theme, system trzykolorowy (`--accent` = identyfikacja/nagłówki/
neutralne IoC, `--red` = zagrożenie/critical, `--green` = defense/gotowe),
JetBrains Mono w treści/kodzie (jeśli masz font zainstalowany lokalnie —
CSS nie ściąga go z sieci, żeby nie było zależności od CDN). Podświetlanie
składni w polu KQL jest jedynym wyjątkiem od reguły trzech kolorów, zgodnie
z Twoim briefem — zaimplementowane bez żadnej biblioteki: `app/static/app.js`
nakłada przezroczystą `<textarea>` na podświetlony `<pre>` (ten sam tekst,
zsynchronizowany scroll), a tokenizacja do podświetlenia jest prostym
regexem po stronie JS. Podświetlanie jest **case-sensitive** tak samo jak
prawdziwy parser silnika (`where` się podświetli, `Where` nie) — celowo, żeby
nie sugerować, że coś zadziała, gdy silnik by to odrzucił.

**Feedback przy błędnej odpowiedzi:** panel wyników zawsze pokazuje to, co
faktycznie zwróciło zapytanie użytkownika (nie oczekiwaną odpowiedź — to
byłoby ściągą, nie treningiem). Sam błąd parsowania/wykonania trafia do pola
`error` z pełnym komunikatem ze strzałką `^^^`, żeby dało się precyzyjnie
zlokalizować literówkę.

Przetestowane automatycznie (`tests/test_app/`, FastAPI `TestClient`) oraz
ręcznie przez `curl` na realnie odpalonym serwerze (strony, statyki, API,
scenariusz z `join`+`summarize` end-to-end) — **nie klikałem tego w
prawdziwej przeglądarce**, bo nie mam tu do niej dostępu. Zanim uznasz to za
gotowe, odpal `.venv/bin/uvicorn app.main:app --reload` i sam przejrzyj
przynajmniej 2-3 scenariusze w przeglądarce (dobry pierwszy test: wpisz coś
z literówką i sprawdź, czy błąd faktycznie jest czytelny na żywo, nie tylko
w terminalu).

**Nazewnictwo w UI vs. w kodzie (celowa niespójność):** sidebar ma trzy
sekcje — "Ćwiczenia" (pojedyncze zadanie, jedno zapytanie do napisania),
"Lekcje" i "Scenariusze" (wieloetapowe symulacje pełnego incydentu,
łączące kilka ćwiczeń z krokami reakcji IR). Etykiety "Ćwiczenia"/
"Scenariusze" to zmiana z późniejszego etapu — pierwotnie (i wciąż w całym
kodzie) to, co UI teraz nazywa "Ćwiczeniem", nosi nazwę **Scenario**
(`core/scenarios/`, `Scenario`, trasy `/scenarios/*` i `/api/scenarios/*`),
a to, co UI nazywa "Scenariuszem", nosi nazwę **Incident**
(`core/incidents/`, `Incident`, trasy `/incidents/*` i `/api/incidents/*`).
Zmieniono tylko widoczne etykiety (szablon `scenario_shell.html`, teksty w
`app/static/app.js`, komunikaty błędów zwracane przez API) — nie
przemianowano klas, adresów URL ani struktury API, bo `Scenario`/`Incident`
są nazwami domenowymi używanymi w kilkunastu plikach w całym projekcie i
pełne przemianowanie byłoby dużym, ryzykownym refaktorem czysto
kosmetycznym. Efekt: URL `/scenarios/{id}` prowadzi do czegoś, co sidebar
podpisuje "Ćwiczenia", a URL `/incidents/{id}` do czegoś, co sidebar
podpisuje "Scenariusze". Jeśli kiedyś to będzie doskwierać, pełne
przemianowanie trzeba będzie zrobić jako osobne zadanie.

## Czego celowo brakuje (poza zakresem Faz 1-4)

W silniku: `mv-expand`, `make-series`, `let`, `innerunique` (domyślny tryb
joina w prawdziwym Kusto), negowane formy operatorów tekstowych (`!contains`,
`!has`, ...), operator `in`.

W warstwie scenariuszy: import/generowanie scenariuszy z zewnątrz (format
JSON jest pod to zaprojektowany, ale nie ma jeszcze narzędzia importującego),
podpowiedzi wielopoziomowe, punktacja/progres (`progress/` — zaplanowane
miejsce w strukturze na przyszłość, celowo puste).

W aplikacji webowej: autoryzacja/multi-user, trwała baza danych (dane wciąż
żyją tylko w pamięci procesu), tryb "swobodnego" zapytania bez przypisanego
scenariusza, historia poprzednich prób.

To wszystko kolejne fazy, do ustalenia w miarę potrzeb.
