from parser.hibernate_parser import HibernateParser
from agent_orchestrator import AgentOrchestrator
from db.oracle_connector import OracleConnector
import json
from fpdf import FPDF


def _parse_responses(raw_responses):
    parsed = []
    for raw in raw_responses:
        try:
            parsed.append(json.loads(raw.strip()))
        except Exception:
            pass
    return parsed


def _write_summary_page(pdf, items):
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "JPA Performance Optimization Report", ln=True, align="C")
    pdf.ln(4)

    total_methods = len(items)
    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    repo_issue_counts: dict[str, int] = {}
    all_indexes: list[str] = []
    seen_indexes: set[str] = set()

    for item in items:
        repo = item.get("repository", "Unknown")
        issues = item.get("query_issues", [])
        repo_issue_counts[repo] = repo_issue_counts.get(repo, 0) + len(issues)
        for issue in issues:
            sev = issue.get("severity", "")
            if sev in severity_counts:
                severity_counts[sev] += 1
        for idx in item.get("recommended_indexes", []):
            normalized = idx.strip().upper()
            if normalized not in seen_indexes:
                seen_indexes.add(normalized)
                all_indexes.append(idx.strip())

    pdf.set_font("Arial", "B", 12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, "Summary", ln=True, fill=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Methods analyzed: {total_methods}", ln=True)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(0, 6, f"HIGH severity issues: {severity_counts['HIGH']}", ln=True)
    pdf.set_text_color(200, 130, 0)
    pdf.cell(0, 6, f"MEDIUM severity issues: {severity_counts['MEDIUM']}", ln=True)
    pdf.set_text_color(0, 100, 180)
    pdf.cell(0, 6, f"LOW severity issues: {severity_counts['LOW']}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    if repo_issue_counts:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, "Issues by Repository", ln=True)
        pdf.set_font("Arial", "", 9)
        for repo, count in sorted(repo_issue_counts.items(), key=lambda x: -x[1]):
            if count > 0:
                pdf.cell(0, 5, f"  {repo}: {count} issue(s)", ln=True)
        pdf.ln(4)

    if all_indexes:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 7, "All Recommended Indexes (deduplicated)", ln=True)
        pdf.set_font("Courier", "", 8)
        for idx in all_indexes:
            pdf.multi_cell(0, 5, f"> {idx}")
        pdf.ln(4)

    pdf.line(10, pdf.get_y(), 200, pdf.get_y())


def generate_performance_report(raw_responses, filename="JPA_Optimization_Report.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    items = _parse_responses(raw_responses)
    _write_summary_page(pdf, items)
    pdf.add_page()

    for raw_item in raw_responses:
        try:
            item = json.loads(raw_item.strip())

            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, f"Repository: {item['repository']}", ln=True, fill=True)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, f"Method: {item['method']}", ln=True)

            issues = item.get("query_issues", [])
            if not issues:
                pdf.set_font("Arial", "", 10)
                pdf.set_text_color(0, 128, 0)
                pdf.multi_cell(0, 6, "Issues: None Identified")
                pdf.set_text_color(0, 0, 0)
            else:
                for issue in issues:
                    severity = issue.get("severity", "")
                    if severity == "HIGH":
                        color = (200, 0, 0)
                    elif severity == "MEDIUM":
                        color = (200, 130, 0)
                    else:
                        color = (0, 100, 180)
                    pdf.set_font("Arial", "B", 10)
                    pdf.set_text_color(*color)
                    pdf.multi_cell(0, 6, f"[{severity}] {issue.get('issue_type', '')}: {issue.get('description', '')}")
                    pdf.set_font("Arial", "I", 9)
                    pdf.set_text_color(60, 60, 60)
                    pdf.multi_cell(0, 5, f"  Suggestion: {issue.get('suggestion', '')}")
                pdf.set_text_color(0, 0, 0)

            if item.get("original"):
                pdf.ln(2)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(0, 5, "Offending Code:", ln=True)
                pdf.set_font("Courier", "", 9)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 5, item["original"])
                pdf.set_text_color(0, 0, 0)

            if item.get("optimized"):
                pdf.ln(2)
                pdf.set_font("Arial", "B", 9)
                pdf.cell(0, 5, "Optimized:", ln=True)
                pdf.set_font("Courier", "", 9)
                pdf.multi_cell(0, 5, item["optimized"], border=1)

            indexes = item.get("recommended_indexes", [])
            if indexes:
                pdf.ln(2)
                pdf.set_font("Arial", "B", 9)
                pdf.set_fill_color(255, 255, 200)
                pdf.cell(0, 5, "Recommended Indexes:", ln=True, fill=True)
                pdf.set_font("Courier", "B", 9)
                for idx in indexes:
                    pdf.multi_cell(0, 5, f"> {idx}")

            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)

        except Exception as e:
            print(f"Skipping malformed entry: {e}")

    pdf.output(filename)
    print(f"Report successfully saved to {filename}")


if __name__ == "__main__":
    parser = HibernateParser()
    result = parser.scan('')

    db = OracleConnector()
    db.connect("url", "user", "password")
    orchestrator = AgentOrchestrator(db, parser, result['entities'])

    all_methods = [
        (key, method, method_def, value.get('entity'))
        for key, value in result["repositories"].items()
        for method, method_def in value['methods'].items()
    ]
    total = len(all_methods)
    response = []

    for idx, (key, method, method_def, entity) in enumerate(all_methods, start=1):
        print(f"[{idx}/{total}] Analyzing {key}.{method}")
        payload = {"repository_name": key, "entity_name": entity, "method_name": method,
                   "native_query": method_def.get('sql'), "method_usages": method_def.get('usages')}
        try:
            result_item = orchestrator.analyze(json.dumps(payload, indent=2))
            if result_item is not None:
                response.append(result_item)
            else:
                print(f"[WARN] No output for {key}.{method} — skipping")
        except Exception as e:
            print(f"[ERROR] {key}.{method} failed: {e}")

    generate_performance_report(response)
