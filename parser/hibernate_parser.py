import os
import re
from tree_sitter import Parser, Language, Query
import tree_sitter_java
from parser.base_parser import BaseParser

language = Language(tree_sitter_java.language())
parser = Parser(language)

REPO_QUERY = Query(language, """
    (interface_declaration
        (modifiers (marker_annotation
            name: (identifier) @annot (#eq? @annot "Repository")))
        name: (identifier) @repo_name
        (extends_interfaces
            (type_list
                (generic_type
                    (type_arguments
                        (type_identifier) @entity_type)))))
""")

ENTITY_QUERY = Query(language, """
    (class_declaration
        (modifiers (marker_annotation
            name: (identifier) @annot (#eq? @annot "Entity")))
        name: (identifier) @class_name)
""")

METHOD_QUERY_ANNOT = Query(language, """
    (method_declaration
        (modifiers (annotation
            name: (identifier) @annot (#eq? @annot "Query")
            arguments: (annotation_argument_list
                (element_value_pair
                    key:   (identifier) @key   (#eq? @key "value")
                    value: (string_literal)     @sql))))
        name: (identifier) @method_name)
""")

ALL_METHODS = Query(language, """
    (method_declaration
        name: (identifier) @method_name)
""")

FIELD_QUERY = Query(language, """
    (field_declaration
        type: (_) @field_type
        declarator: (variable_declarator
            name: (identifier) @field_name))
""")

CONTEXT_QUERY = Query(language, """
    (method_invocation
        name: (identifier) @call_name)
""")

CALL_SITE_RE = re.compile(r'\.(\w+)\s*\(')


class HibernateParser(BaseParser):

    @staticmethod
    def extract_sql(raw: str) -> str:
        if raw.startswith('"""') and raw.endswith('"""'):
            return raw[3:-3]
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        return raw.replace('\\"', '"').replace('\\n', '\n')

    @staticmethod
    def find_injected_repos(content: str, known_repos: set[str]) -> set[str]:
        return {repo for repo in known_repos if repo in content}

    @staticmethod
    def find_all_java_file(root_dir) -> list:
        java_files = []
        for dirpath, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(dirpath, file))
        return java_files

    def _extract_entities(self, root, src: bytes, path: str) -> dict:
        entities = {}
        for match in self.iter_matches(ENTITY_QUERY, root):
            for node in match.get("class_name", []):
                entities[self.text(node, src)] = path
        return entities

    def _extract_repository(self, root, src: bytes) -> tuple[str | None, str | None, dict]:
        repo_matches = list(self.iter_matches(REPO_QUERY, root))
        if not repo_matches:
            return None, None, {}

        repo_name = None
        entity_type = None
        for match in repo_matches:
            for node in match.get("repo_name", []):
                repo_name = self.text(node, src)
                break
            for node in match.get("entity_type", []):
                entity_type = self.text(node, src)
                break
            if repo_name:
                break
        if not repo_name:
            return None, None, {}

        all_methods: dict[str, dict] = {}
        for match in self.iter_matches(ALL_METHODS, root):
            for node in match.get("method_name", []):
                all_methods[self.text(node, src)] = {"sql": None}

        for match in self.iter_matches(METHOD_QUERY_ANNOT, root):
            method_nodes = match.get("method_name", [])
            sql_nodes = match.get("sql", [])
            if method_nodes and sql_nodes:
                method_name = self.text(method_nodes[0], src)
                raw_sql = self.extract_sql(self.text(sql_nodes[0], src))
                if method_name in all_methods:
                    all_methods[method_name]["sql"] = raw_sql

        return repo_name, entity_type, all_methods

    @staticmethod
    def _filter_unused(repositories: dict) -> dict:
        filtered = {}
        for repo, data in repositories.items():
            used_methods = {
                name: {
                    "sql": info["sql"],
                    "usages": info.get("usages", []),
                }
                for name, info in data["methods"].items()
                if info.get("used")
            }
            if used_methods:
                filtered[repo] = {
                    "entity": data.get("entity"),
                    "methods": used_methods,
                }
        return filtered

    def get_entity_columns(self, entity_path: str) -> list[dict] | None:
        if not entity_path:
            return None
        try:
            with open(entity_path, "rb") as f:
                src = f.read()
        except (OSError, IOError):
            return None

        tree = parser.parse(src)
        root = tree.root_node

        columns = []
        for match in self.iter_matches(FIELD_QUERY, root):
            type_nodes = match.get("field_type", [])
            name_nodes = match.get("field_name", [])
            if type_nodes and name_nodes:
                columns.append({
                    "name": self.text(name_nodes[0], src),
                    "type": self.text(type_nodes[0], src),
                })
        return columns

    def _build_index(self, java_files: list[str]) -> dict:
        result = {"entities": {}, "repositories": {}}
        for path in java_files:
            try:
                with open(path, "rb") as f:
                    src = f.read()
            except (OSError, IOError) as exc:
                print(f"[WARN] Skipping unreadable file {path}: {exc}")
                continue

            tree = parser.parse(src)
            root = tree.root_node

            result["entities"] |= self._extract_entities(root, src, path)

            repo_name, entity_type, methods = self._extract_repository(root, src)
            if repo_name:
                result["repositories"][repo_name] = {
                    "entity": entity_type,
                    "methods": methods,
                }

        return result

    @staticmethod
    def _find_enclosing_scope(node):
        scope_types = {
            "method_declaration",
            "for_statement",
            "enhanced_for_statement",
            "while_statement",
            "do_statement",
            "if_statement",
            "lambda_expression",
            "try_statement",
        }
        current = node.parent
        while current:
            if current.type in scope_types:
                if current.type != "method_declaration":
                    return current
                break
            current = current.parent

        current = node.parent
        while current:
            if current.type == "method_declaration":
                return current
            current = current.parent
        return node

    def scan(self, root_dir: str) -> dict:
        result = {"entities": {}, "repositories": {}}
        java_files = self.find_all_java_file(root_dir)

        for path in java_files:
            try:
                with open(path, "rb") as f:
                    src = f.read()
            except (OSError, IOError) as exc:
                print(f"[WARN] Skipping unreadable file {path}: {exc}")
                continue

            tree = parser.parse(src)
            root = tree.root_node

            result["entities"] |= self._extract_entities(root, src, path)

            repo_name, entity_type, methods = self._extract_repository(root, src)
            if repo_name:
                result["repositories"][repo_name] = {
                    "entity": entity_type,
                    "methods": methods,
                }

        known_repos = set(result["repositories"].keys())
        if not known_repos:
            return result

        method_to_repos: dict[str, set[str]] = {}
        for repo, data in result["repositories"].items():
            for method in data["methods"]:
                method_to_repos.setdefault(method, set()).add(repo)

        repo_pattern = re.compile(r'\b(' + '|'.join(re.escape(r) for r in known_repos) + r')\b')

        for path in java_files:
            try:
                with open(path, "rb") as f:
                    src = f.read()
            except (OSError, IOError):
                continue

            content = src.decode("utf-8", errors="replace")
            called_methods = set(CALL_SITE_RE.findall(content))
            relevant_methods = called_methods & method_to_repos.keys()
            if not relevant_methods:
                continue

            injected = set(repo_pattern.findall(content))
            if not injected:
                continue

            tree = parser.parse(src)
            root = tree.root_node

            call_nodes: dict[str, list] = {}
            for match in self.iter_matches(CONTEXT_QUERY, root):
                for node in match.get("call_name", []):
                    name = self.text(node, src)
                    if name in relevant_methods:
                        call_nodes.setdefault(name, []).append(node)

            for method_name, nodes in call_nodes.items():
                for repo in method_to_repos.get(method_name, set()) & injected:
                    info = result["repositories"][repo]["methods"][method_name]
                    info["used"] = True

                    usages = info.setdefault("usages", [])
                    if len(usages) >= 2:
                        continue

                    for node in nodes:
                        if len(usages) >= 2:
                            break
                        scope = self._find_enclosing_scope(node)
                        usages.append(self.text(scope, src))

        result["repositories"] = self._filter_unused(result["repositories"])
        return result
