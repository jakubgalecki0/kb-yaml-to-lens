"""Tests for the main() console-script entry point."""

import sys

import pytest

from dashboard_compiler.cli import main


class TestMain:
    """Tests for main(), which runs the CLI on a larger-stack worker thread."""

    def test_main_exits_zero_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() runs the CLI to completion and exits 0 on success."""
        monkeypatch.setattr(sys, 'argv', ['kb-dashboard', '--version'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    def test_main_propagates_nonzero_exit_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() propagates a non-zero exit code from a failing invocation."""
        monkeypatch.setattr(sys, 'argv', ['kb-dashboard', 'nonexistent-command'])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code != 0
