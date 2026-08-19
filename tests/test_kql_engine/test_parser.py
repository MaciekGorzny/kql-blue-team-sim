"""Unit tests for core.kql_engine.parser."""
import pytest

from core.kql_engine import ast_nodes as ast
from core.kql_engine.errors import KqlParseError
from core.kql_engine.parser import parse


def test_parse_source_table_and_stage_count():
    query = parse("DeviceProcessEvents | where FileName == 'cmd.exe' | take 5")
    assert query.source_table == "DeviceProcessEvents"
    assert len(query.stages) == 2
    assert isinstance(query.stages[0], ast.WhereStage)
    assert isinstance(query.stages[1], ast.TakeStage)
    assert query.stages[1].count == 5


def test_parse_project_with_computed_column():
    query = parse("T | project Name = FileName, IsCmd = FileName == 'cmd.exe'")
    stage = query.stages[0]
    assert isinstance(stage, ast.ProjectStage)
    assert [c.name for c in stage.columns] == ["Name", "IsCmd"]
    assert isinstance(stage.columns[1].expr, ast.BinaryExpr)


def test_parse_bare_project_column_is_a_column_ref():
    query = parse("T | project FileName")
    col = query.stages[0].columns[0]
    assert col.name == "FileName"
    assert isinstance(col.expr, ast.ColumnRef)


def test_parse_sort_default_descending():
    query = parse("T | sort by Count")
    stage = query.stages[0]
    assert isinstance(stage, ast.SortStage)
    assert stage.keys[0].ascending is False


def test_parse_sort_explicit_asc():
    query = parse("T | sort by Count asc")
    stage = query.stages[0]
    assert stage.keys[0].ascending is True


def test_parse_order_by_is_synonym_for_sort_by():
    query = parse("T | order by Count")
    assert isinstance(query.stages[0], ast.SortStage)


def test_parse_has_operator():
    query = parse("T | where CommandLine has 'cmd'")
    cond = query.stages[0].condition
    assert isinstance(cond, ast.BinaryExpr)
    assert cond.op == "has"


def test_parse_matches_regex_operator():
    query = parse("T | where CommandLine matches regex '^cmd'")
    cond = query.stages[0].condition
    assert cond.op == "matches regex"


def test_parse_distinct_star():
    query = parse("T | distinct *")
    assert query.stages[0].columns == []


def test_parse_distinct_columns():
    query = parse("T | distinct DeviceName, FileName")
    assert query.stages[0].columns == ["DeviceName", "FileName"]


def test_parse_unknown_operator_raises_with_span():
    with pytest.raises(KqlParseError) as exc_info:
        parse("T | bogusop X")
    assert exc_info.value.span is not None


def test_parse_unterminated_function_call_raises():
    with pytest.raises(KqlParseError):
        parse("T | where tolower(FileName")


def test_parse_function_call_with_timespan_arg():
    query = parse("T | where TimeGenerated > ago(1d)")
    cond = query.stages[0].condition
    call = cond.right
    assert isinstance(call, ast.FunctionCall)
    assert call.name == "ago"
    assert isinstance(call.args[0], ast.Literal)
    assert call.args[0].kql_type == ast.KqlType.TIMESPAN


def test_parse_take_requires_integer():
    with pytest.raises(KqlParseError):
        parse("T | take 5.5")


def test_operator_precedence_and_binds_tighter_than_or():
    # `A or B and C` should parse as `A or (B and C)`
    query = parse("T | where A == 1 or B == 2 and C == 3")
    cond = query.stages[0].condition
    assert cond.op == "or"
    assert cond.right.op == "and"


def test_parse_summarize_default_and_explicit_names():
    query = parse("T | summarize count(), Uniq = dcount(User) by Device")
    stage = query.stages[0]
    assert isinstance(stage, ast.SummarizeStage)
    assert stage.aggregates[0].name == "Count"
    assert stage.aggregates[0].func == "count"
    assert stage.aggregates[1].name == "Uniq"
    assert stage.aggregates[1].func == "dcount"
    assert [c.name for c in stage.group_by] == ["Device"]


def test_parse_summarize_without_by():
    query = parse("T | summarize sum(Amount)")
    stage = query.stages[0]
    assert stage.group_by == []
    assert stage.aggregates[0].name == "sum_Amount"


def test_parse_summarize_count_rejects_argument():
    with pytest.raises(KqlParseError):
        parse("T | summarize count(User)")


def test_parse_summarize_sum_requires_argument():
    with pytest.raises(KqlParseError):
        parse("T | summarize sum()")


def test_parse_summarize_unknown_function_raises():
    with pytest.raises(KqlParseError):
        parse("T | summarize median(X)")


def test_parse_join_shorthand_on():
    query = parse("Left | join kind=inner (Right) on Key")
    stage = query.stages[0]
    assert isinstance(stage, ast.JoinStage)
    assert stage.kind == "inner"
    assert stage.right.source_table == "Right"
    assert stage.on[0].left_expr.name == "Key"
    assert stage.on[0].right_expr.name == "Key"


def test_parse_join_dollar_left_right_form():
    query = parse("Left | join kind=leftouter (Right) on $left.A == $right.B")
    key = query.stages[0].on[0]
    assert key.left_expr.name == "A"
    assert key.right_expr.name == "B"


def test_parse_join_requires_explicit_kind():
    with pytest.raises(KqlParseError):
        parse("Left | join (Right) on Key")


def test_parse_join_rejects_unsupported_kind():
    with pytest.raises(KqlParseError):
        parse("Left | join kind=fullouter (Right) on Key")


def test_parse_join_right_side_can_have_stages():
    query = parse("Left | join kind=inner (Right | where X == 1) on Key")
    right = query.stages[0].right
    assert len(right.stages) == 1
