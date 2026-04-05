from abc import ABC, abstractmethod
from tree_sitter import Query, QueryCursor


class BaseParser(ABC):
    
    @abstractmethod
    def scan(self, file_path: str) -> dict:
        pass

    @abstractmethod
    def get_entity_columns(self, entity_path: str) -> list[dict] | None:
        pass

    @staticmethod
    def text(node, src: bytes) -> str:
        return src[node.start_byte:node.end_byte].decode("utf-8")

    @staticmethod
    def iter_matches(query: Query, node):
        cursor = QueryCursor(query)
        for match in cursor.matches(node):
            _pattern_idx, capture_dict = match
            yield capture_dict
