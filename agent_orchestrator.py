import json
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_ollama import ChatOllama
from db.base_connector import BaseConnector
from parser.base_parser import BaseParser
from schema.ModelResponse import ModelResponse

SYSTEM_PROMPT = """You are a SQL index and query optimization analyst. You will receive a JSON containing repository 
methods extracted from a Java Hibernate project. Each entry includes the repository name, entity name, method name, 
and the native SQL query if present. The target database is {dialect}. All SQL statements you generate must use 
{dialect} syntax.

Important: The "entity" field in the input refers to a Java/JPA entity class name, NOT the actual database table name. 
These are different. If the SQL query is present, extract the table name directly from it. If the SQL query is null 
and you need to know the table name or columns, use the get_entity_columns tool with the entity name — it will return 
the actual database table name and column details.

Your job:
1. Analyze each method. There are two cases:
   a. If the SQL query is present: analyze it for performance issues such as missing WHERE clause indexes, unindexed 
      JOIN columns, inefficient patterns like SELECT *, unnecessary subqueries, or implicit type conversions.
   b. If the SQL query is null: it is a standard JPA/Spring Data repository method. The method name follows JPA naming 
      conventions (e.g. findByName, findByStatusAndType). Parse the method name to determine which columns are being 
      queried, filtered, or sorted on. Use the get_entity_columns tool to resolve the actual table name and column 
      details, then check if appropriate indexes exist for those columns.
2. Use the retrieve_table_indexes tool to check what indexes already exist on the relevant tables before making 
   recommendations. You must use the actual database table name, not the Java entity name.
3. Use the get_method_usage tool to retrieve code snippets showing how each method is called. Look for:
   - N+1 problems: the method is called inside a loop (for/while/stream.forEach) that iterates over a collection. 
     This means one query per iteration instead of a single batch query.
   - Overfetching: the query returns all columns (SELECT * or full entity fetch) but the calling code only uses 
     a few fields from the result.

Rules:
- Only recommend indexes that do not already exist. Always check existing indexes first using the tool.
- Do not recommend indexes on primary key columns as they are already indexed.
- For JPA derived methods, recommend composite indexes when multiple columns are used in the method name.
- All CREATE INDEX statements must be valid {dialect} SQL.
- Do not include any explanation outside the JSON. Return only the JSON object."""


def _build_tools(connector: BaseConnector, parser: BaseParser, entities: dict):
    @tool
    def retrieve_table_indexes(table_name: str) -> str:
        """Retrieves all indexes defined on a given table.
        Use this to check existing indexes before recommending new ones."""
        return json.dumps(connector.get_indexes(table_name), default=str)

    @tool
    def get_entity_columns(entity_name: str) -> str:
        """Retrieves the column names and types of an entity class. Use this to check what columns a JPA entity has."""
        columns = parser.get_entity_columns(entities.get(entity_name))
        if columns is None:
            return f"Entity '{entity_name}' not found"
        return json.dumps(columns, default=str)

    @tool
    def get_method_usage(repo_name: str, method_name: str) -> str:
        """Retrieves at most 2 code snippets showing how a repository method is called.
        Use this to detect N+1 query problems and overfetching."""
        pass

    return [retrieve_table_indexes, get_entity_columns]


class AgentOrchestrator:
    def __init__(self, connector: BaseConnector, parser: BaseParser, entities: dict,
                 model: str = "hf.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF:Q4_K_M"):
        self._db = connector
        self._parser = parser
        self._entities = entities
        self._tools = _build_tools(connector, parser, entities)
        self._tools_dict = {t.name: t for t in self._tools}
        self._llm = ChatOllama(model=model,
                               temperature=0,
                               format=ModelResponse.model_json_schema()).bind_tools(self._tools)
        self._system_prompt = SYSTEM_PROMPT.format(dialect=connector.dialect())

    def analyze(self, user_input: str, max_turns: int = 15) -> str:

        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=user_input),
        ]

        for turn in range(max_turns):

            result = self._llm.invoke(messages)
            messages.append(result)

            print(f"Model Response {messages}")

            if not isinstance(result, AIMessage) or not result.tool_calls:
                return result.content

            for tool_call in result.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call.get("id", f"call_{turn}")

                print(f"Calling Tool {tool_name}")
                print(f"With Args {tool_args}")

                if tool_name in self._tools_dict:
                    try:
                        tool_result = self._tools_dict[tool_name].invoke(tool_args)
                    except Exception as e:
                        tool_result = f"Error: {e}"
                else:
                    tool_result = f"Unknown tool: {tool_name}"

                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id,
                ))

        return "Reached max tool calls limit"
