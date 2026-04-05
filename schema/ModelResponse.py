from pydantic import BaseModel


class QueryAnalysis(BaseModel):
    repository: str
    method: str
    original_query: str | None
    query_issues: list[str]
    optimized_query: str | None
    recommended_indexes: list[str]


class ModelResponse(BaseModel):
    response: list[QueryAnalysis]
