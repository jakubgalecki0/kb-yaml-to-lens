"""Tests for ES|QL source command extraction."""

import pytest

from kb_dashboard_core.queries.esql_source import extract_esql_index_pattern


def test_simple_from() -> None:
    """A bare FROM clause returns the index pattern verbatim."""
    assert extract_esql_index_pattern('FROM logs-*') == 'logs-*'


def test_simple_ts() -> None:
    """A bare TS (time series) clause returns the index pattern verbatim."""
    assert extract_esql_index_pattern('TS metrics-*') == 'metrics-*'


def test_from_with_pipe() -> None:
    """Trailing pipeline stages after the source clause are ignored."""
    assert extract_esql_index_pattern('FROM logs-* | LIMIT 10') == 'logs-*'


def test_from_multiple_sources() -> None:
    """Multiple comma-separated sources are joined with a comma in the title."""
    assert extract_esql_index_pattern('FROM logs-*, metrics-* | STATS count()') == 'logs-*,metrics-*'


def test_ts_multiple_sources() -> None:
    """TS supports multiple comma-separated sources just like FROM."""
    assert extract_esql_index_pattern('TS metrics-*, traces-*') == 'metrics-*,traces-*'


def test_quoted_source() -> None:
    """Surrounding double quotes around a source are stripped."""
    assert extract_esql_index_pattern('FROM "logs-*" | LIMIT 5') == 'logs-*'


def test_quoted_with_commas() -> None:
    """Each individually quoted source is unquoted and re-joined."""
    assert extract_esql_index_pattern('FROM "logs-*", "metrics-*"') == 'logs-*,metrics-*'


def test_metadata_suffix() -> None:
    """A trailing METADATA clause does not leak into the index pattern."""
    assert extract_esql_index_pattern('FROM logs-* METADATA _id, _index | LIMIT 1') == 'logs-*'


def test_lowercase_keyword() -> None:
    """Source keywords are matched case-insensitively."""
    assert extract_esql_index_pattern('from logs-* | limit 10') == 'logs-*'


def test_multiline_query() -> None:
    """Queries that span multiple lines parse the leading source command correctly."""
    query = 'FROM metrics-*\n| WHERE host.name IS NOT NULL\n| STATS avg = AVG(cpu.pct)'
    assert extract_esql_index_pattern(query) == 'metrics-*'


def test_leading_whitespace() -> None:
    """Leading whitespace and newlines are tolerated."""
    assert extract_esql_index_pattern('   \n  FROM logs-* | LIMIT 1') == 'logs-*'


def test_leading_pipe_stripped() -> None:
    """A stray leading pipe (e.g. from YAML anchor composition) is tolerated."""
    assert extract_esql_index_pattern('| FROM logs-*') == 'logs-*'


def test_block_comment_stripped() -> None:
    """Block comments before the source command are stripped before matching."""
    assert extract_esql_index_pattern('/* select source */ FROM logs-* | LIMIT 1') == 'logs-*'


def test_line_comment_stripped() -> None:
    """Line comments before the source command are stripped before matching."""
    query = '// pick our source\nFROM metrics-*\n| LIMIT 1'
    assert extract_esql_index_pattern(query) == 'metrics-*'


def test_quoted_source_with_comma_not_split() -> None:
    """A comma inside a quoted source is part of the name, not a source separator."""
    assert extract_esql_index_pattern('FROM "weird,index" | LIMIT 1') == 'weird,index'


def test_quoted_source_with_pipe_not_terminated() -> None:
    """A pipe inside a quoted source does not terminate the source clause."""
    assert extract_esql_index_pattern('FROM "logs|piped", metrics-*') == 'logs|piped,metrics-*'


def test_quoted_source_containing_metadata_keyword() -> None:
    """The METADATA keyword inside a quoted source is not treated as a clause boundary."""
    assert extract_esql_index_pattern('FROM "METADATA-like" METADATA _id') == 'METADATA-like'


def test_remote_cluster_sources() -> None:
    """Cluster-qualified sources (``cluster:index``) are preserved verbatim."""
    query = 'TS cluster_one:metrics-*, cluster_two:metrics-*'
    assert extract_esql_index_pattern(query) == 'cluster_one:metrics-*,cluster_two:metrics-*'


def test_selector_source() -> None:
    """Index selectors (``index::failures``) are preserved verbatim."""
    assert extract_esql_index_pattern('FROM logs-*::failures') == 'logs-*::failures'


def test_triple_quoted_source() -> None:
    """Triple-quoted sources are unquoted and may contain delimiter characters."""
    assert extract_esql_index_pattern('FROM """triple,quoted|src"""') == 'triple,quoted|src'


# The following cases are taken from real ES|QL dashboards in the
# elastic/integrations repository (packages/*/kibana and _dev/shared/kibana),
# to keep the parser honest against the source shapes that actually ship.


@pytest.mark.parametrize(
    ('query', 'expected'),
    [
        # Single dotted OTel data streams (the overwhelmingly common case).
        ('FROM metrics-postgresqlreceiver.otel-*\n| STATS c = COUNT(*)', 'metrics-postgresqlreceiver.otel-*'),
        ('TS metrics-hostmetricsreceiver.otel-*\n| STATS `CPU usage` = AVG(container.cpu.usage)', 'metrics-hostmetricsreceiver.otel-*'),
        ('FROM logs-generic.otel*\n| LIMIT 10', 'logs-generic.otel*'),
        # Lowercase source keyword as seen in the wild.
        ('from logs-*\n| STATS total = COUNT(*)', 'logs-*'),
        # Concrete (non-glob) indices, including underscores, dots and version suffixes.
        ('FROM aws_billing.cur_latest', 'aws_billing.cur_latest'),
        ('FROM logs-keeper.audit-1.0.0', 'logs-keeper.audit-1.0.0'),
        ('FROM metrics-statsdreceiver-default', 'metrics-statsdreceiver-default'),
        ('FROM metrics-nvidia_gpu.otel-default', 'metrics-nvidia_gpu.otel-default'),
        # Multiple sources, comma with and without surrounding whitespace.
        ('FROM logs-generic.otel*,traces-generic.otel*', 'logs-generic.otel*,traces-generic.otel*'),
        (
            'FROM metrics-kubeletstatsreceiver.otel-*, metrics-k8sclusterreceiver.otel-*\n| STATS x = MAX(v)',
            'metrics-kubeletstatsreceiver.otel-*,metrics-k8sclusterreceiver.otel-*',
        ),
        # METADATA clause directly following the source glob.
        ('FROM logs-*.otel-* METADATA _index\n| WHERE host.name IS NOT NULL', 'logs-*.otel-*'),
    ],
)
def test_real_integrations_sources(query: str, expected: str) -> None:
    """Source shapes drawn from ES|QL dashboards in elastic/integrations parse correctly."""
    assert extract_esql_index_pattern(query) == expected


@pytest.mark.parametrize('query', ['', '   ', '\n\t  \n'])
def test_empty_query_raises(query: str) -> None:
    """An empty or whitespace-only query raises a distinct 'query is empty' error."""
    with pytest.raises(ValueError, match='ES\\|QL query is empty'):
        extract_esql_index_pattern(query)


def test_missing_source_raises() -> None:
    """Queries without a leading FROM/TS clause raise a ValueError."""
    with pytest.raises(ValueError, match='missing a FROM/TS source command'):
        extract_esql_index_pattern('WHERE foo == 1 | LIMIT 1')


def test_empty_sources_raises() -> None:
    """A FROM clause with no sources after stripping raises a ValueError."""
    with pytest.raises(ValueError, match='no sources'):
        extract_esql_index_pattern('FROM   | LIMIT 1')
