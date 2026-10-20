from unittest.mock import MagicMock
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src import refresh_mart


@pytest.mark.parametrize("fails", [False, True])
def test_refresh_commits_on_success_rolls_back_on_error_and_always_closes(monkeypatch, tmp_path, fails):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        ("mart.fact_sales",), (False,), (Decimal("10.10"), 1, 1, 2),
        ("mart.fact_sales",), (True,), (Decimal("30.30"), 2, 1, 4),
    ]
    original_root = refresh_mart.SETTINGS.root
    sql_dir = tmp_path / "sql" / "solutions"
    sql_dir.mkdir(parents=True)
    (sql_dir / "12_load_data_mart.sql").write_text(
        (original_root / "sql/solutions/12_load_data_mart.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(refresh_mart, "SETTINGS", SimpleNamespace(root=tmp_path))
    if fails:
        def fail_during_load(statement):
            if "CREATE SCHEMA" in statement:
                raise RuntimeError("SQL failed")
        cursor.execute.side_effect = fail_during_load
        previous = tmp_path / "docs/kpi_comparison.csv"
        previous.parent.mkdir()
        previous.write_text("previous successful comparison")
    monkeypatch.setattr(refresh_mart.engine, "raw_connection", lambda: connection)

    if fails:
        with pytest.raises(RuntimeError, match="SQL failed"):
            refresh_mart.refresh_mart()
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        assert previous.read_text() == "previous successful comparison"
    else:
        rows = refresh_mart.refresh_mart()
        assert rows[0]["diff"] == Decimal("20.20")
        assert "total_revenue,10.10,30.30,20.20" in (
            tmp_path / "docs/kpi_comparison.csv").read_text()
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_empty_mart_has_zero_kpis():
    cursor = MagicMock()
    cursor.fetchone.return_value = (None,)
    assert refresh_mart._read_kpis(cursor) == dict.fromkeys(refresh_mart.KPI_NAMES, 0)


def test_commit_failure_rolls_back_closes_and_keeps_previous_csv(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.commit.side_effect = RuntimeError("commit failed")
    monkeypatch.setattr(refresh_mart.engine, "raw_connection", lambda: connection)
    monkeypatch.setattr(refresh_mart, "_read_kpis", lambda cursor: dict.fromkeys(refresh_mart.KPI_NAMES, 0))
    monkeypatch.setattr(refresh_mart, "write_comparison", MagicMock())
    with pytest.raises(RuntimeError, match="commit failed"):
        refresh_mart.refresh_mart()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    refresh_mart.write_comparison.assert_not_called()
