"""Recursive-descent parser: token stream -> Query AST.

Grammar (informal), lowest to highest precedence for expressions:

    query      := let_stmt* tabular_expr EOF
    let_stmt   := "let" IDENT "=" expr ";"
    tabular_expr := IDENT ("|" stage)*
    stage      := "where" expr
                | "project" column_list
                | "extend" column_list
                | ("sort"|"order") "by" sort_key ("," sort_key)*
                | ("take"|"limit") NUMBER
                | "distinct" ("*" | IDENT ("," IDENT)*)
                | "count"
                | "summarize" agg_spec ("," agg_spec)* ("by" column_list)?
                | "join" "kind" "=" ("inner"|"leftouter") "(" tabular_expr ")" "on" on_clause ("," on_clause)*
    agg_spec   := (IDENT "=")? ("count"|"sum"|"avg"|"dcount"|"min"|"max") "(" expr? ")"
    on_clause  := IDENT | "$left" "." IDENT "==" "$right" "." IDENT
    column_list:= column_spec ("," column_spec)*
    column_spec:= IDENT "=" expr | IDENT
    expr       := or_expr
    or_expr    := and_expr ("or" and_expr)*
    and_expr   := comparison ("and" comparison)*
    comparison := additive (comp_op additive)?
    comp_op    := "==" | "!=" | "<" | "<=" | ">" | ">="
                | "contains" | "startswith" | "endswith" | "has" | "matches" "regex"
                | "in" in_operand
    in_operand := "(" expr ("," expr)* ")"   # 1 item: passed through as-is
                                              # (e.g. a `let`-bound dynamic
                                              # list); 2+: becomes a list
                | additive
    additive   := multiplicative (("+"|"-") multiplicative)*
    multiplicative := unary (("*"|"/"|"%") unary)*
    unary      := "-" unary | primary
    primary    := NUMBER | STRING | TIMESPAN | "true" | "false"
                | IDENT "(" (expr ("," expr)*)? ")"   # function call
                | IDENT                                # column reference
                | "(" expr ")"
                | "[" (expr ("," expr)*)? "]"          # list literal (`dynamic([...])`)

Negation is the `not(...)` function (real KQL has no `not` prefix keyword),
so it falls out of the function-call rule above rather than needing its own
grammar rule. There's likewise no dedicated `!in` - negate with `not(x in (...))`.
"""
from __future__ import annotations

from . import ast_nodes as ast
from .errors import KqlParseError, Span
from .timespan import parse_timespan
from .tokenizer import Token, TokenType, tokenize

_COMPARISON_TOKEN_OPS = {
    TokenType.EQ: "==",
    TokenType.NEQ: "!=",
    TokenType.LT: "<",
    TokenType.LE: "<=",
    TokenType.GT: ">",
    TokenType.GE: ">=",
}

_STRING_INFIX_KEYWORDS = {"contains", "startswith", "endswith", "has"}
_AGG_FUNCS = {"count", "sum", "avg", "dcount", "min", "max"}
_JOIN_KINDS = {"inner", "leftouter"}


def _default_agg_name(func: str, arg: ast.Expr | None) -> str:
    if func == "count":
        return "Count"
    if isinstance(arg, ast.ColumnRef):
        return f"{func}_{arg.name}"
    return func


def parse(query_text: str) -> ast.Query:
    tokens = tokenize(query_text)
    return _Parser(tokens, query_text).parse_query()


class _Parser:
    def __init__(self, tokens: list[Token], query_text: str):
        self._tokens = tokens
        self._query = query_text
        self._pos = 0

    # -- token stream helpers -------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        idx = min(self._pos + offset, len(self._tokens) - 1)
        return self._tokens[idx]

    def _advance(self) -> Token:
        tok = self._peek()
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def _expect(self, token_type: TokenType, message: str) -> Token:
        tok = self._peek()
        if tok.type != token_type:
            raise KqlParseError(message, self._query, tok.span)
        return self._advance()

    def _expect_keyword(self, value: str) -> Token:
        tok = self._peek()
        if tok.type != TokenType.IDENT or tok.value != value:
            raise KqlParseError(f"Oczekiwano '{value}'.", self._query, tok.span)
        return self._advance()

    def _check_keyword(self, *values: str) -> bool:
        tok = self._peek()
        return tok.type == TokenType.IDENT and tok.value in values

    # -- top level --------------------------------------------------------

    def parse_query(self) -> ast.Query:
        lets: list[ast.LetStatement] = []
        while self._check_keyword("let"):
            lets.append(self._parse_let_statement())
        query = self._parse_tabular_expression()
        query.lets = lets
        if self._peek().type != TokenType.EOF:
            tok = self._peek()
            raise KqlParseError(f"Nieoczekiwany token po zapytaniu: {tok.value!r}.", self._query, tok.span)
        return query

    def _parse_let_statement(self) -> ast.LetStatement:
        """`let` is only recognized here, at the very top of the query - not
        inside a join's nested `_parse_tabular_expression()` - but a binding
        is still visible inside a join's right-hand subquery at evaluation
        time (see executor.py/operators/join.py threading `ctx.bindings`
        through)."""
        let_tok = self._advance()  # 'let'
        name_tok = self._expect(TokenType.IDENT, "Oczekiwano nazwy zmiennej po 'let'.")
        self._expect(TokenType.ASSIGN, "Oczekiwano '=' w definicji 'let'.")
        expr = self._parse_expr()
        self._expect(TokenType.SEMICOLON, "Oczekiwano ';' na końcu definicji 'let'.")
        return ast.LetStatement(name=name_tok.value, expr=expr, span=let_tok.span)

    def _parse_tabular_expression(self) -> ast.Query:
        """Parses `IDENT ("|" stage)*` - used both for the top-level query and
        for the right-hand side of a `join`, which is itself a tabular
        expression in parentheses."""
        first = self._expect(TokenType.IDENT, "Oczekiwano nazwy tabeli.")
        stages: list[ast.Stage] = []
        last_tok = first
        while self._peek().type == TokenType.PIPE:
            self._advance()
            stage = self._parse_stage()
            stages.append(stage)
            last_tok = self._tokens[self._pos - 1]

        span = Span(
            line=first.span.line,
            col=first.span.col,
            offset=first.span.offset,
            length=(last_tok.span.offset + last_tok.span.length) - first.span.offset,
        )
        return ast.Query(source_table=first.value, source_span=first.span, stages=stages, span=span)

    def _parse_stage(self) -> ast.Stage:
        tok = self._peek()
        if tok.type != TokenType.IDENT:
            raise KqlParseError("Oczekiwano nazwy operatora po '|'.", self._query, tok.span)

        name = tok.value
        if name == "where":
            self._advance()
            condition = self._parse_expr()
            return ast.WhereStage(condition=condition, span=tok.span)
        if name == "project":
            self._advance()
            columns = self._parse_column_list()
            return ast.ProjectStage(columns=columns, span=tok.span)
        if name == "extend":
            self._advance()
            columns = self._parse_column_list()
            return ast.ExtendStage(columns=columns, span=tok.span)
        if name in ("sort", "order"):
            self._advance()
            self._expect_keyword("by")
            keys = self._parse_sort_keys()
            return ast.SortStage(keys=keys, span=tok.span)
        if name in ("take", "limit"):
            self._advance()
            num_tok = self._expect(TokenType.NUMBER, "Oczekiwano liczby po 'take'/'limit'.")
            if "." in num_tok.value:
                raise KqlParseError("'take'/'limit' oczekuje liczby całkowitej.", self._query, num_tok.span)
            return ast.TakeStage(count=int(num_tok.value), span=tok.span)
        if name == "distinct":
            self._advance()
            columns = self._parse_distinct_columns()
            return ast.DistinctStage(columns=columns, span=tok.span)
        if name == "count":
            self._advance()
            return ast.CountStage(span=tok.span)
        if name == "summarize":
            self._advance()
            aggregates = self._parse_aggregate_list()
            group_by: list[ast.ColumnSpec] = []
            if self._check_keyword("by"):
                self._advance()
                group_by = self._parse_column_list()
            return ast.SummarizeStage(aggregates=aggregates, group_by=group_by, span=tok.span)
        if name == "join":
            self._advance()
            kind = self._parse_join_kind()
            self._expect(TokenType.LPAREN, "Oczekiwano '(' po 'join' - prawa strona joina musi być w nawiasach.")
            right = self._parse_tabular_expression()
            self._expect(TokenType.RPAREN, "Brakuje ')' zamykającego prawą stronę joina.")
            self._expect_keyword("on")
            on_clauses = self._parse_on_clauses()
            return ast.JoinStage(kind=kind, right=right, on=on_clauses, span=tok.span)

        raise KqlParseError(f"Nieznany operator '{name}'.", self._query, tok.span)

    # -- summarize --------------------------------------------------------

    def _parse_aggregate_list(self) -> list[ast.AggregateSpec]:
        specs = [self._parse_aggregate_spec()]
        while self._peek().type == TokenType.COMMA:
            self._advance()
            specs.append(self._parse_aggregate_spec())
        return specs

    def _parse_aggregate_spec(self) -> ast.AggregateSpec:
        start_tok = self._peek()
        explicit_name = None
        if self._peek().type == TokenType.IDENT and self._peek(1).type == TokenType.ASSIGN:
            name_tok = self._advance()
            self._advance()  # consume '='
            explicit_name = name_tok.value

        func_tok = self._expect(
            TokenType.IDENT, "Oczekiwano funkcji agregującej (count, sum, avg, dcount, min, max)."
        )
        if func_tok.value not in _AGG_FUNCS:
            raise KqlParseError(
                f"Nieznana funkcja agregująca '{func_tok.value}'. Obsługiwane: {', '.join(sorted(_AGG_FUNCS))}.",
                self._query,
                func_tok.span,
            )
        self._expect(TokenType.LPAREN, f"Oczekiwano '(' po '{func_tok.value}'.")
        arg: ast.Expr | None = None
        if self._peek().type != TokenType.RPAREN:
            arg = self._parse_expr()
        self._expect(TokenType.RPAREN, "Brakuje ')' zamykającego wywołanie funkcji agregującej.")

        if func_tok.value == "count" and arg is not None:
            raise KqlParseError("'count()' nie przyjmuje argumentu.", self._query, func_tok.span)
        if func_tok.value != "count" and arg is None:
            raise KqlParseError(
                f"'{func_tok.value}()' wymaga argumentu (nazwy kolumny).", self._query, func_tok.span
            )

        name = explicit_name or _default_agg_name(func_tok.value, arg)
        return ast.AggregateSpec(name=name, func=func_tok.value, arg=arg, span=start_tok.span)

    # -- join --------------------------------------------------------

    def _parse_join_kind(self) -> str:
        tok = self._peek()
        if not (tok.type == TokenType.IDENT and tok.value == "kind"):
            raise KqlParseError(
                "Ten silnik wymaga jawnego 'kind=inner' lub 'kind=leftouter' po 'join' "
                "(prawdziwy Kusto ma tu domyślny tryb 'innerunique', którego ten silnik nie obsługuje).",
                self._query,
                tok.span,
            )
        self._advance()
        self._expect(TokenType.ASSIGN, "Oczekiwano '=' po 'kind'.")
        kind_tok = self._expect(TokenType.IDENT, "Oczekiwano rodzaju joina po 'kind='.")
        if kind_tok.value not in _JOIN_KINDS:
            raise KqlParseError(
                f"Nieobsługiwany rodzaj joina '{kind_tok.value}'. Obsługiwane: {', '.join(sorted(_JOIN_KINDS))}.",
                self._query,
                kind_tok.span,
            )
        return kind_tok.value

    def _parse_on_clauses(self) -> list[ast.JoinKey]:
        clauses = [self._parse_on_clause()]
        while self._peek().type == TokenType.COMMA:
            self._advance()
            clauses.append(self._parse_on_clause())
        return clauses

    def _parse_on_clause(self) -> ast.JoinKey:
        tok = self._peek()
        if tok.type == TokenType.IDENT and tok.value == "$left":
            left_expr = self._parse_dollar_column_ref("$left")
            self._expect(TokenType.EQ, "Oczekiwano '==' pomiędzy '$left....' a '$right....'.")
            right_expr = self._parse_dollar_column_ref("$right")
            return ast.JoinKey(left_expr=left_expr, right_expr=right_expr, span=tok.span)

        name_tok = self._expect(TokenType.IDENT, "Oczekiwano nazwy kolumny (lub '$left.Kolumna') po 'on'.")
        col = ast.ColumnRef(name=name_tok.value, span=name_tok.span)
        return ast.JoinKey(left_expr=col, right_expr=col, span=name_tok.span)

    def _parse_dollar_column_ref(self, expected: str) -> ast.Expr:
        tok = self._expect(TokenType.IDENT, f"Oczekiwano '{expected}'.")
        if tok.value != expected:
            raise KqlParseError(f"Oczekiwano '{expected}', otrzymano '{tok.value}'.", self._query, tok.span)
        self._expect(TokenType.DOT, f"Oczekiwano '.' po '{expected}'.")
        col_tok = self._expect(TokenType.IDENT, "Oczekiwano nazwy kolumny.")
        return ast.ColumnRef(name=col_tok.value, span=col_tok.span)

    # -- column lists (project / extend) -----------------------------------

    def _parse_column_list(self) -> list[ast.ColumnSpec]:
        columns = [self._parse_column_spec()]
        while self._peek().type == TokenType.COMMA:
            self._advance()
            columns.append(self._parse_column_spec())
        return columns

    def _parse_column_spec(self) -> ast.ColumnSpec:
        if self._peek().type == TokenType.IDENT and self._peek(1).type == TokenType.ASSIGN:
            name_tok = self._advance()
            self._advance()  # consume '='
            expr = self._parse_expr()
            return ast.ColumnSpec(name=name_tok.value, expr=expr, span=name_tok.span)

        name_tok = self._expect(TokenType.IDENT, "Oczekiwano nazwy kolumny.")
        return ast.ColumnSpec(
            name=name_tok.value, expr=ast.ColumnRef(name=name_tok.value, span=name_tok.span), span=name_tok.span
        )

    # -- sort by --------------------------------------------------------

    def _parse_sort_keys(self) -> list[ast.SortKey]:
        keys = [self._parse_sort_key()]
        while self._peek().type == TokenType.COMMA:
            self._advance()
            keys.append(self._parse_sort_key())
        return keys

    def _parse_sort_key(self) -> ast.SortKey:
        expr = self._parse_expr()
        ascending = False  # KQL default sort order is descending
        if self._check_keyword("asc", "desc"):
            ascending = self._advance().value == "asc"
        return ast.SortKey(expr=expr, ascending=ascending)

    # -- distinct --------------------------------------------------------

    def _parse_distinct_columns(self) -> list[str]:
        if self._peek().type == TokenType.STAR:
            self._advance()
            return []
        names = [self._expect(TokenType.IDENT, "Oczekiwano nazwy kolumny.").value]
        while self._peek().type == TokenType.COMMA:
            self._advance()
            names.append(self._expect(TokenType.IDENT, "Oczekiwano nazwy kolumny.").value)
        return names

    # -- expressions (precedence climbing) --------------------------------

    def _parse_expr(self) -> ast.Expr:
        return self._parse_or()

    def _parse_or(self) -> ast.Expr:
        left = self._parse_and()
        while self._check_keyword("or"):
            tok = self._advance()
            right = self._parse_and()
            left = ast.BinaryExpr(op="or", left=left, right=right, span=tok.span)
        return left

    def _parse_and(self) -> ast.Expr:
        left = self._parse_comparison()
        while self._check_keyword("and"):
            tok = self._advance()
            right = self._parse_comparison()
            left = ast.BinaryExpr(op="and", left=left, right=right, span=tok.span)
        return left

    def _parse_comparison(self) -> ast.Expr:
        left = self._parse_additive()
        op, op_span = self._try_consume_comparison_op()
        if op is not None:
            right = self._parse_in_operand() if op == "in" else self._parse_additive()
            left = ast.BinaryExpr(op=op, left=left, right=right, span=op_span)
        return left

    def _parse_in_operand(self) -> ast.Expr:
        """Right-hand side of `in`. `(a, b, c)` (2+ items) becomes an
        `ast.ListExpr`. A single parenthesized item is ambiguous - `in ('z')`
        should mean "the 1-element set {'z'}", but `in (allowed)` (a `let`
        name) or `in (dynamic([...]))` should pass through unwrapped, since
        those already evaluate to a list on their own and wrapping them would
        produce a list-of-one-list instead. Disambiguate by node kind: only
        pass through unwrapped when the single item could itself evaluate to
        a list (a name reference or a call/nested list); a bare literal
        always gets wrapped."""
        if self._peek().type == TokenType.LPAREN:
            start_tok = self._advance()
            items = [self._parse_expr()]
            while self._peek().type == TokenType.COMMA:
                self._advance()
                items.append(self._parse_expr())
            self._expect(TokenType.RPAREN, "Brakuje ')' zamykającego listę dla 'in'.")
            if len(items) == 1 and isinstance(items[0], (ast.ColumnRef, ast.FunctionCall, ast.ListExpr)):
                return items[0]
            return ast.ListExpr(items=items, span=start_tok.span)
        return self._parse_additive()

    def _try_consume_comparison_op(self) -> tuple[str | None, Span | None]:
        tok = self._peek()
        if tok.type in _COMPARISON_TOKEN_OPS:
            self._advance()
            return _COMPARISON_TOKEN_OPS[tok.type], tok.span
        if tok.type == TokenType.IDENT:
            if tok.value in _STRING_INFIX_KEYWORDS:
                self._advance()
                return tok.value, tok.span
            if tok.value == "in":
                self._advance()
                return "in", tok.span
            if tok.value == "matches" and self._peek(1).type == TokenType.IDENT and self._peek(1).value == "regex":
                self._advance()
                self._advance()
                return "matches regex", tok.span
        return None, None

    def _parse_additive(self) -> ast.Expr:
        left = self._parse_multiplicative()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            tok = self._advance()
            op = "+" if tok.type == TokenType.PLUS else "-"
            right = self._parse_multiplicative()
            left = ast.BinaryExpr(op=op, left=left, right=right, span=tok.span)
        return left

    def _parse_multiplicative(self) -> ast.Expr:
        left = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            tok = self._advance()
            op = {TokenType.STAR: "*", TokenType.SLASH: "/", TokenType.PERCENT: "%"}[tok.type]
            right = self._parse_unary()
            left = ast.BinaryExpr(op=op, left=left, right=right, span=tok.span)
        return left

    def _parse_unary(self) -> ast.Expr:
        if self._peek().type == TokenType.MINUS:
            tok = self._advance()
            operand = self._parse_unary()
            return ast.UnaryExpr(op="-", operand=operand, span=tok.span)
        return self._parse_primary()

    def _parse_primary(self) -> ast.Expr:
        tok = self._peek()

        if tok.type == TokenType.NUMBER:
            self._advance()
            if "." in tok.value:
                return ast.Literal(value=float(tok.value), kql_type=ast.KqlType.REAL, span=tok.span)
            return ast.Literal(value=int(tok.value), kql_type=ast.KqlType.LONG, span=tok.span)

        if tok.type == TokenType.STRING:
            self._advance()
            return ast.Literal(value=tok.value, kql_type=ast.KqlType.STRING, span=tok.span)

        if tok.type == TokenType.TIMESPAN:
            self._advance()
            return ast.Literal(value=parse_timespan(tok.value), kql_type=ast.KqlType.TIMESPAN, span=tok.span)

        if tok.type == TokenType.IDENT:
            if tok.value in ("true", "false"):
                self._advance()
                return ast.Literal(value=tok.value == "true", kql_type=ast.KqlType.BOOL, span=tok.span)

            if self._peek(1).type == TokenType.LPAREN:
                name = self._advance().value
                self._advance()  # consume '('
                args: list[ast.Expr] = []
                if self._peek().type != TokenType.RPAREN:
                    args.append(self._parse_expr())
                    while self._peek().type == TokenType.COMMA:
                        self._advance()
                        args.append(self._parse_expr())
                self._expect(TokenType.RPAREN, "Brakuje ')' zamykającego wywołanie funkcji.")
                return ast.FunctionCall(name=name, args=args, span=tok.span)

            self._advance()
            return ast.ColumnRef(name=tok.value, span=tok.span)

        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expr()
            self._expect(TokenType.RPAREN, "Brakuje ')' zamykającego wyrażenie.")
            return expr

        if tok.type == TokenType.LBRACKET:
            self._advance()
            items: list[ast.Expr] = []
            if self._peek().type != TokenType.RBRACKET:
                items.append(self._parse_expr())
                while self._peek().type == TokenType.COMMA:
                    self._advance()
                    items.append(self._parse_expr())
            self._expect(TokenType.RBRACKET, "Brakuje ']' zamykającego listę.")
            return ast.ListExpr(items=items, span=tok.span)

        raise KqlParseError(f"Nieoczekiwany token w wyrażeniu: {tok.value!r}.", self._query, tok.span)
