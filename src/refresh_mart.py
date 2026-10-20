"""Run the project's existing Sales Data Mart SQL for the pipeline CLI."""
import re

from src.config import SETTINGS
from src.database import engine


def refresh_mart():
    """Refresh using the Buổi 4 script in one managed transaction.

    The repository contains sql/student/04_data_mart.sql, which creates and
    rebuilds the mart. Transaction boundaries in that standalone script are
    removed so a failed statement cannot commit a partial refresh.
    """
    sql_path = SETTINGS.root / "sql" / "student" / "04_data_mart.sql"
    sql = sql_path.read_text(encoding="utf-8")
    sql = re.sub(r"^\s*(?:BEGIN|COMMIT);\s*$", "", sql, flags=re.MULTILINE)
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
