import oracledb
from db.base_connector import BaseConnector


class OracleConnector(BaseConnector):
    def __init__(self):
        self._conn = None
        self._cache: dict[str, list[dict]] = {}

    def connect(self, url: str, user: str, password: str):
        self._conn = oracledb.connect(dsn=url, user=user, password=password)
        self._cache.clear()

    def execute(self, query: str, params: tuple = ()) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description is None:
                return []
            columns = [col[0].lower() for col in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def _cached(self, key: str, fn) -> list[dict]:
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def explain(self, query: str) -> list[dict]:
        self.execute(f"EXPLAIN PLAN FOR {query}")
        return self.execute(
            "SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', null, 'ALL'))"
        )

    def get_indexes(self, table_name: str) -> list[dict]:
        name = table_name.upper()
        return self._cached(f"indexes:{name}", lambda: self.execute("""
            SELECT i.index_name, i.uniqueness, ic.column_name, ic.column_position
            FROM user_indexes i
            JOIN user_ind_columns ic ON i.index_name = ic.index_name
            WHERE i.table_name = :1
            ORDER BY i.index_name, ic.column_position
        """, (name,)))

    def get_sample(self, table_name: str, limit: int = 5) -> list[dict]:
        name = table_name.upper()
        return self._cached(f"sample:{name}:{limit}", lambda: self.execute(
            f"SELECT * FROM {name} FETCH FIRST {limit} ROWS ONLY"
        ))

    def dialect(self) -> str:
        return "Oracle"

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        self._cache.clear()
