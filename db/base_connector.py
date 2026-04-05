from abc import ABC, abstractmethod


class BaseConnector(ABC):
    @abstractmethod
    def connect(self, url: str, user: str, password: str):
        pass

    @abstractmethod
    def execute(self, query: str, params: tuple = ()) -> list[dict]:
        pass

    @abstractmethod
    def explain(self, query: str) -> list[dict]:
        pass

    @abstractmethod
    def get_indexes(self, table_name: str) -> list[dict]:
        pass

    @abstractmethod
    def get_sample(self, table_name: str, limit: int = 5) -> list[dict]:
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
