from abc import ABC, abstractmethod


class BaseConnector(ABC):
    @abstractmethod
    def connect(self, url: str, user: str, password: str):
        pass

    @abstractmethod
    def execute(self, query: str, params: tuple = ()) -> list[dict]:
        pass

    @abstractmethod
    def get_indexes(self, table_name: str) -> list[dict]:
        pass

    @abstractmethod
    def get_cached_plan(self, sql: str) -> list[dict]:
        """Returns execution plan rows from the DB's plan cache for the given SQL fragment.
        Empty list if no cached plan exists."""
        pass

    @abstractmethod
    def get_sql_runtime_stats(self, sql: str) -> list[dict]:
        """Returns runtime execution statistics (executions, avg elapsed ms, avg buffer gets, avg disk reads)
        for the given SQL fragment. Empty list if not found in the query cache."""
        pass

    @abstractmethod
    def get_column_stats(self, table_name: str, columns: list[str]) -> list[dict]:
        """Returns optimizer statistics for the given columns on a table:
        num_distinct, num_nulls, density, histogram type, num_buckets."""
        pass

    @abstractmethod
    def get_sample(self, table_name: str, limit: int = 5) -> list[dict]:
        pass

    @abstractmethod
    def explain(self, query: str) -> list[dict]:
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def dialect(self) -> str:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
