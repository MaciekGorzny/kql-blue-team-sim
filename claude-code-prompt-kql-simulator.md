# Initial Prompt dla Claude Code: KQL Simulator (moduł Blue Team Simulator)

## Kontekst projektu

Buduję **Blue Team Simulator** — modularną aplikację treningową dla analityków SOC/threat detection engineerów. Pierwszy moduł to **symulator zapytań KQL** (Kusto Query Language, jak w Microsoft Sentinel / Defender XDR Advanced Hunting). Architektura ma od początku wspierać dokładanie kolejnych modułów (np. Sigma rule builder, phishing triage, log parsing) bez przepisywania rdzenia.

Jestem threat detection engineerem (Sentinel, Defender XDR, KQL na co dzień), więc oczekuję poprawnej semantyki KQL, nie uproszczonej zabawki.

## Cel pierwszej iteracji

Pełnoprawna aplikacja w Pythonie (backend + prosty frontend webowy) realizująca:
1. Silnik wykonujący **podzbiór realnego KQL** na danych tabelarycznych (JSON/dict-based datasety wzorowane na schemach Sentinel/Defender: `DeviceProcessEvents`, `SecurityEvent`, `SigninLogs`).
2. Zestaw scenariuszy treningowych (zadanie → dataset źródłowy → walidacja rozwiązania → feedback).
3. Prosty interfejs do wpisywania zapytań i widzenia wyniku + oceny poprawności.

## Wymagania architektoniczne (priorytet — to ma być rozbudowywalne)

**Rozdziel trzy warstwy, każda z jasnym kontraktem (interfejsem):**

1. **Silnik KQL** (`kql_engine/`)
   - Tokenizer → parser → executor dla pipeline'owej składni KQL (`TableName | operator1 args | operator2 args | ...`).
   - Operatory w wersji 1: `where`, `project`, `extend`, `summarize` (z `by` i podstawowymi agregacjami: `count()`, `sum()`, `avg()`, `dcount()`, `min()`, `max()`), `sort by` / `order by`, `top`, `take`/`limit`, `distinct`, `count`, `join` (przynajmniej `inner` i `leftouter`).
   - Operatory nie mogą być hardkodowane w jednym switchu — użyj rejestru: `operator_name -> handler(pipeline_state, args) -> pipeline_state`, żeby dodanie nowego operatora nie ruszało reszty parsera.
   - Podstawowe funkcje skalarne używane w `where`/`extend`/`project`: string (`contains`, `startswith`, `endswith`, `has`, `matches regex`, `tolower`/`toupper`, `strcat`, `split`), datetime (`ago()`, `now()`, `bin()`), logiczne/arytmetyczne.
   - Silnik ma działać na strukturach Python (list of dicts) — nie wymaga bazy danych do działania samego parsera.
   - Testy jednostkowe dla każdego operatora (pytest) — to jest część "pełnoprawności" aplikacji, nie opcja.

2. **Warstwa datasetów** (`datasets/`)
   - Każdy dataset to osobny plik (JSON lub Python moduł generujący dane) + schema (nazwy kolumn, typy).
   - Dataset startowy: uproszczony `DeviceProcessEvents` (kilkadziesiąt-kilkaset syntetycznych rekordów, w tym kilka "wstrzykniętych" anomalii do wykrycia w scenariuszach — np. proces LOLBin z podejrzaną linią komend).
   - Dodanie nowego datasetu = nowy plik, zero zmian w silniku ani w warstwie scenariuszy.

3. **Warstwa scenariuszy** (`scenarios/`)
   - Scenariusz to dane, nie kod: treść zadania, referencja do datasetu, kryterium walidacji.
   - Kryterium walidacji wspiera co najmniej dwa tryby:
     a) porównanie wyniku zapytania użytkownika z oczekiwanym wynikiem (dokładność zbioru wierszy/kolumn),
     b) opcjonalnie: sprawdzenie czy użyto określonych operatorów/pól (dla zadań uczących konkretnej techniki, nie tylko konkretnego wyniku).
   - Metadane scenariusza: poziom trudności, kategoria (np. mapowanie do MITRE ATT&CK techniki), hint (opcjonalna podpowiedź).
   - Docelowo scenariusze mają być łatwe do importu/generowania — zaprojektuj format (JSON schema) z myślą o tym już teraz, nawet jeśli import z zewnątrz nie jest w zakresie MVP.

4. **Warstwa aplikacji / API** (`app/`)
   - Backend: FastAPI.
   - Frontend: prosty, ale przyjemny w użyciu — edytor zapytania (textarea z monospace, dark theme), przycisk "Uruchom", tabela wyniku, panel z treścią scenariusza i feedbackiem (poprawnie/niepoprawnie + czemu). Jinja2 templates + minimalny JS wystarczy w MVP, nie potrzeba SPA.
   - Endpointy API mają być niezależne od konkretnego frontendu — założenie, że frontend może zostać wymieniony później (np. na React) bez zmian w silniku/scenariuszach.
   - Struktura projektu ma jasno wydzielać "core" (silnik + dataset + scenariusze — reużywalne w innych modułach Blue Team Simulator) od "app" (obecny frontend/API).

## Styl wizualny (jeśli i kiedy dojdziemy do frontendu)

Dark theme, trzy-kolorowy system semantyczny:
- `--accent` — identyfikacja/nagłówki/neutralne IoC
- `--red` — zagrożenie/malicious/critical
- `--green` — defense/mitigation/done
- Reszta: `--text` / `--text-dim` / `--border`
- Podświetlanie składni w polu KQL jest wyjątkiem od reguły trzech kolorów (jak w moich writeupach technicznych).
- Fonty: JetBrains Mono w treści/kodzie.

## Co NIE jest w zakresie pierwszej iteracji

- Pełna zgodność z KQL (nie potrzebuję `mv-expand`, `make-series`, subquery, `let` na start — to kolejne fazy).
- Autoryzacja/multi-user.
- Trwała baza danych — pliki JSON/w pamięci wystarczą na start.
- Warstwa "trybu gry" (punktacja, progres) wspólna dla przyszłych modułów Blue Team Simulator — zaprojektuj pod to miejsce w strukturze (np. pusty interfejs/folder `progress/`), ale nie implementuj teraz.

## Struktura repo (propozycja wyjściowa, możesz zaproponować lepszą)

```
blue-team-simulator/
  core/
    kql_engine/
      tokenizer.py
      parser.py
      executor.py
      operators/
        __init__.py      # rejestr operatorów
        where.py
        project.py
        extend.py
        summarize.py
        sort.py
        join.py
        ...
      functions/          # funkcje skalarne (string/datetime/itd.)
    datasets/
      schema.py
      device_process_events.py
    scenarios/
      schema.py
      loader.py
      kql_basics/
        001_find_lolbin.json
        ...
  modules/
    kql_simulator/        # ten moduł - łączy core w konkretną funkcjonalność
      module.py            # kontrakt modułu dla przyszłego rejestru modułów Blue Team Simulator
  app/
    main.py                # FastAPI
    routers/
    templates/
    static/
  tests/
    test_kql_engine/
    test_scenarios/
  README.md
```

## Plan pracy — chcę to fazami, nie jednym wielkim commitem

**Faza 1:** Silnik KQL: tokenizer + parser + executor dla `where`, `project`, `extend`, `sort by`, `take`, `count`, `distinct`. Testy pytest. Bez UI — na start wystarczy uruchamianie z CLI/skryptu testowego.

**Faza 2:** `summarize` z agregacjami + `join`. Rozszerzenie testów.

**Faza 3:** Dataset `DeviceProcessEvents` + 5-8 pierwszych scenariuszy o rosnącej trudności (od prostego `where` po scenariusz wymagający `summarize` + `join`).

**Faza 4:** FastAPI + minimalny frontend (edytor + wynik + feedback), podłączenie do silnika i scenariuszy.

**Faza 5 (opcjonalna, po ocenie MVP):** kolejne operatory/funkcje na podstawie tego, czego faktycznie zabraknie w praktyce.

Na start: zacznij od **Fazy 1**. Zaproponuj konkretny design tokenizer/parser (np. czy budujesz właściwe AST, czy prostszą reprezentację pipeline'u kroków) i skonsultuj się ze mną przed napisaniem dużej ilości kodu — wolę krótką iterację projektową niż duży diff do poprawek.

## Standardy jakości

- Python 3.11+, type hints wszędzie, `pytest` do testów.
- Czytelne błędy parsera (komunikat wskazujący gdzie i dlaczego zapytanie jest niepoprawne — to część wartości edukacyjnej narzędzia, nie tylko wewnętrzny detal).
- Docstringi na poziomie modułów i publicznych funkcji/klas.
- Brak zbędnych zależności — jeśli coś da się zrobić w stdlib, nie ciągnij biblioteki dla jednej funkcji.
