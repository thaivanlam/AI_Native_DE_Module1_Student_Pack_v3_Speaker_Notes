from unittest.mock import MagicMock

import pytest

from src import refresh_mart


@pytest.mark.parametrize("fails", [False, True])
def test_refresh_commits_on_success_rolls_back_on_error_and_always_closes(monkeypatch, fails):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    if fails:
        cursor.execute.side_effect = RuntimeError("SQL failed")
    monkeypatch.setattr(refresh_mart.engine, "raw_connection", lambda: connection)

    if fails:
        with pytest.raises(RuntimeError, match="SQL failed"):
            refresh_mart.refresh_mart()
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
    else:
        refresh_mart.refresh_mart()
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
