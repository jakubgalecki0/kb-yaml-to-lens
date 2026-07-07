# pyright: reportUnknownMemberType=false
# pyright: reportAny=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportMissingTypeStubs=false
"""Utilities for extracting the source index pattern from an ES|QL query string.

The ES|QL grammar requires every top-level query to start with a source command
(`FROM` or `TS`) followed by one or more comma-separated index patterns. The
adHocDataView emitted for ES|QL panels uses this comma-joined source list as its
`title`, matching Kibana's own behavior.

Rather than pattern-matching the leading clause with regexes, the source list is
parsed with a small TatSu (PEG) grammar. This mirrors the approach used for Lens
formulas (see ``panels/charts/lens/metrics/formula_parser.py``) and lets quoting
be a first-class concern: quoted sources may legally contain the characters that
otherwise delimit the clause (``,``, ``|``) or the ``METADATA`` keyword.
"""

import tatsu
from tatsu.exceptions import FailedParse

# TatSu grammar for the leading source command of an ES|QL query.
# It intentionally matches only the `FROM`/`TS` clause and its source list; the
# remainder of the pipeline (everything from the first `|`, or a trailing
# `METADATA` clause) is left unconsumed. ES|QL line (`//`) and block (`/* */`)
# comments are stripped natively via the comment directives.
_ESQL_SOURCE_GRAMMAR = r'''
@@grammar::EsqlSource
@@whitespace :: /\s+/
@@nameguard :: False
@@eol_comments :: /\/\/[^\n]*/
@@comments :: /\/\*[\s\S]*?\*\//

start = ['|'] command_keyword [sources:source_list] ;

command_keyword = /(?i)(?:FROM|TS)\b/ ;

source_list = ','.{ source }+ ;

source = triple_quoted | double_quoted | unquoted ;

triple_quoted = /"""(?:[^"]|"(?!""))*"""/ ;

double_quoted = /"(?:\\.|[^"\\])*"/ ;

unquoted = /[^,|"\s]+/ ;
'''

# Compiled parser (module-level singleton for performance): compiling the
# grammar once at import time avoids re-parsing it on every call.
_PARSER = tatsu.compile(_ESQL_SOURCE_GRAMMAR)

_MIN_DOUBLE_QUOTED_LEN = 2
_MIN_TRIPLE_QUOTED_LEN = 6


def _strip_source_quotes(source: str) -> str:
    """Strip surrounding double or triple quotes from a single index source."""
    stripped = source.strip()
    if len(stripped) >= _MIN_TRIPLE_QUOTED_LEN and stripped.startswith('"""') and stripped.endswith('"""'):
        return stripped[3:-3]
    if len(stripped) >= _MIN_DOUBLE_QUOTED_LEN and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def extract_esql_index_pattern(query: str) -> str:
    """Extract the comma-joined source list from the leading `FROM`/`TS` clause of an ES|QL query.

    Examples:
        >>> extract_esql_index_pattern('FROM logs-* | LIMIT 10')
        'logs-*'
        >>> extract_esql_index_pattern('TS metrics-*, traces-* | STATS avg = AVG(value)')
        'metrics-*,traces-*'
        >>> extract_esql_index_pattern('FROM "logs-*" METADATA _id')
        'logs-*'

    Args:
        query: A complete ES|QL query string.

    Returns:
        The comma-joined index pattern (e.g. ``'metrics-*'`` or ``'logs-*,metrics-*'``)
        suitable for use as an adHocDataView ``title``.

    Raises:
        ValueError: If the query is empty, has no ``FROM``/``TS`` source command,
            or the source command has no sources.

    """
    if not query.strip():
        msg = 'ES|QL query is empty'
        raise ValueError(msg)

    try:
        ast = _PARSER.parse(query)
    except FailedParse as exc:
        msg = f'ES|QL query is missing a FROM/TS source command: {query!r}'
        raise ValueError(msg) from exc

    raw_sources = ast['sources'] or []
    sources = [_strip_source_quotes(source) for source in raw_sources]
    sources = [source for source in sources if len(source) > 0]
    if len(sources) == 0:
        msg = f'ES|QL query FROM/TS clause has no sources: {query!r}'
        raise ValueError(msg)

    return ','.join(sources)
