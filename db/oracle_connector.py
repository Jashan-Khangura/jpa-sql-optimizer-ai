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

    def _sql_fragment(self, sql: str) -> str:
        return sql.strip()[:60]

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

    def get_cached_plan(self, sql: str) -> list[dict]:
        fragment = self._sql_fragment(sql)
        return self._cached(f"cached_plan:{fragment}", lambda: self.execute("""
            SELECT p.operation, p.options, p.object_name, p.cost, p.cardinality,
                   p.bytes, s.sql_text
            FROM v$sql s
            JOIN v$sql_plan p
              ON s.sql_id = p.sql_id AND s.child_number = p.child_number
            WHERE UPPER(s.sql_text) LIKE UPPER(:1)
            ORDER BY s.last_active_time DESC, p.id ASC FETCH FIRST 30 ROWS ONLY
        """, (f"%{fragment}%",)))

    def get_sql_runtime_stats(self, sql: str) -> list[dict]:
        fragment = self._sql_fragment(sql)
        return self._cached(f"runtime_stats:{fragment}", lambda: self.execute("""
            SELECT sql_text, executions,
                   ROUND(elapsed_time / NULLIF(executions, 0) / 1000) AS avg_elapsed_ms,
                   ROUND(buffer_gets  / NULLIF(executions, 0))        AS avg_buffer_gets,
                   ROUND(disk_reads   / NULLIF(executions, 0))        AS avg_disk_reads,
                   rows_processed,
                   last_active_time
            FROM v$sql
            WHERE UPPER(sql_text) LIKE UPPER(:1)
            ORDER BY last_active_time DESC FETCH FIRST 5 ROWS ONLY
        """, (f"%{fragment}%",)))

    def get_column_stats(self, table_name: str, columns: list[str]) -> list[dict]:
        if not columns:
            return []
        name = table_name.upper()
        upper_cols = [c.upper() for c in columns]
        cache_key = f"col_stats:{name}:{','.join(sorted(upper_cols))}"
        placeholders = ",".join(f":{i + 2}" for i in range(len(upper_cols)))
        return self._cached(cache_key, lambda: self.execute(f"""
            SELECT column_name, num_distinct, num_nulls, density,
                   histogram, num_buckets
            FROM all_col_statistics
            WHERE owner = USER
              AND table_name = :1
              AND column_name IN ({placeholders})
        """, (name, *upper_cols)))

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
