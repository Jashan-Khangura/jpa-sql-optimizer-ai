import json
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_ollama import ChatOllama
from db.base_connector import BaseConnector
from parser.base_parser import BaseParser
from schema.ModelResponse import QueryAnalysis
from PromptLoader import prompt_store


def _build_tools(connector: BaseConnector, parser: BaseParser, entities: dict):
    @tool
    def retrieve_table_indexes(table_name: str) -> str:
        """Returns all existing indexes on a table (index_name, uniqueness, column_name, column_position).
        Must be called before recommending any index. Use the real DB table name in uppercase, not the Java entity name."""
        return json.dumps(connector.get_indexes(table_name), default=str)

    @tool
    def get_entity_columns(entity_name: str) -> str:
        """Returns the real DB table name and persistable columns for a JPA entity.
        Response: {table_name, table_name_inferred (true if no @Table annotation — uppercase for Oracle),
        columns: [{field_name, column_name (actual DB column from @Column or same as field_name), type}]}.
        Always use column_name (not field_name) when calling get_column_stats or retrieve_table_indexes."""
        result = parser.get_entity_columns(entities.get(entity_name))
        if result is None:
            return f"Entity '{entity_name}' not found"
        return json.dumps(result, default=str)

    @tool
    def explain_query(sql: str) -> str:
        """Returns the cached execution plan from V$SQL/V$SQL_PLAN for a native SQL query.
        Response: {source: 'v$sql_cache', plan: [...]} or {source: 'none'} if not cached.
        If source is 'none', use static analysis only — do not assign HIGH severity without plan evidence."""
        plan = connector.get_cached_plan(sql)
        if plan:
            return json.dumps({"source": "v$sql_cache", "plan": plan}, default=str)
        return json.dumps({"source": "none", "plan": []}, default=str)

    @tool
    def get_sql_runtime_stats(sql: str) -> str:
        """Returns real execution statistics from V$SQL for a native SQL query:
        executions, avg_elapsed_ms, avg_buffer_gets, avg_disk_reads, rows_processed, last_active_time.
        Use this to determine actual production impact and calibrate issue severity.
        Empty list means the query has not been captured in the plan cache."""
        stats = connector.get_sql_runtime_stats(sql)
        return json.dumps(stats, default=str)

    @tool
    def get_column_stats(table_name: str, columns: str) -> str:
        """Returns Oracle optimizer statistics for specific columns: num_distinct, num_nulls, density, histogram, num_buckets.
        Pass columns as a comma-separated string (e.g. 'STATUS,CREATED_AT').
        Use this before recommending an index — low num_distinct means the index will not help."""
        col_list = [c.strip() for c in columns.split(",") if c.strip()]
        stats = connector.get_column_stats(table_name, col_list)
        return json.dumps(stats, default=str)

    return [retrieve_table_indexes, get_entity_columns, explain_query, get_sql_runtime_stats, get_column_stats]


class AgentOrchestrator:
    def __init__(self, connector: BaseConnector, parser: BaseParser, entities: dict,
                 model: str = "hf.co/bartowski/Qwen2.5-Coder-14B-GGUF:Q4_K_M"):
        self._db = connector
        self._parser = parser
        self._entities = entities
        self._tools = _build_tools(connector, parser, entities)
        self._tools_dict = {t.name: t for t in self._tools}
        self._llm = ChatOllama(model=model,
                               temperature=0.1,
                               format=QueryAnalysis.model_json_schema()).bind_tools(self._tools)
        self._system_prompt = prompt_store.get_prompt('sql-analysis', dialect=connector.dialect())

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
                if not result.content or not result.content.strip():
                    return None
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

        print(f"[WARN] Reached max turns limit for input: {user_input[:120]}")
        return None
