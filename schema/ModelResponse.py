from pydantic import BaseModel
from typing import Optional


class QueryIssue(BaseModel):
    issue_type: str
    severity: str
    description: str
    suggestion: str


class QueryAnalysis(BaseModel):
    repository: str
    method: str
    original: Optional[str]
    query_issues: list[QueryIssue]
    optimized: Optional[str]
    recommended_indexes: list[str]
