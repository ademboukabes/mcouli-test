from alembic import op
import os

SQL_DIR = os.path.join(os.path.dirname(__file__), "sql")

def run_sql_up(message: str) -> None:
    """
        message: Migration message exactly as typed (matches filename).
    """
    path = os.path.join(SQL_DIR, "up", message + ".sql")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Up SQL file not found: {path}")

    with open(path, "r") as f:
        sql = f.read()

    op.execute(sql)


def run_sql_down(message: str) -> None:
   # write the message here u create it  in th emigration
    path = os.path.join(SQL_DIR, "down", message + ".sql")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Down SQL file not found: {path}")

    with open(path, "r") as f:
        sql = f.read()

    op.execute(sql)
