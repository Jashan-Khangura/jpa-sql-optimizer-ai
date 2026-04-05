from parser.hibernate_parser import HibernateParser
from agent_orchestrator import AgentOrchestrator
from db.oracle_connector import OracleConnector
import json
from fpdf import FPDF


def generate_performance_report(raw_responses, filename="JPA_Optimization_Report.pdf"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "JPA Performance Optimization Report", ln=True, align="C")
    pdf.ln(10)

    for raw_item in raw_responses:
        try:
            clean_json = raw_item.strip()
            data = json.loads(clean_json)

            for item in data.get("response", []):
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, f"Repository: {item['repository']}", ln=True, fill=True)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 8, f"Method: {item['method']}", ln=True)

                issues = item.get("query_issues", [])
                pdf.set_font("Arial", "B", 10)
                pdf.set_text_color(200, 0, 0) if issues else pdf.set_text_color(0, 128, 0)
                issue_text = f"Issues: {', '.join(issues)}" if issues else "Issues: None Identified"
                pdf.multi_cell(0, 6, issue_text)
                pdf.set_text_color(0, 0, 0)  # Reset color

                if item.get("original_query"):
                    pdf.set_font("Arial", "I", 9)
                    pdf.set_text_color(100, 100, 100)
                    pdf.multi_cell(0, 5, f"SQL: {item['original_query']}")
                    pdf.set_text_color(0, 0, 0)

                if item.get("optimized_query"):
                    pdf.ln(2)
                    pdf.set_font("Arial", "B", 9)
                    pdf.cell(0, 5, "Optimized SQL Suggestion:", ln=True)
                    pdf.set_font("Courier", "", 9)
                    pdf.multi_cell(0, 5, item["optimized_query"], border=1)

                indexes = item.get("recommended_indexes", [])
                if indexes:
                    pdf.ln(2)
                    pdf.set_font("Arial", "B", 9)
                    pdf.set_fill_color(255, 255, 200)
                    pdf.cell(0, 5, "Required Indexes:", ln=True, fill=True)
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
    result = parser.scan('/path/to/folder')

    db = OracleConnector()
    orchestrator = AgentOrchestrator(db, parser, result['entities'])

    response = []

    count = 0

    for key, value in result["repositories"].items():
        for method, method_def in value['methods'].items():
            payload = {"entity_name": value.get('entity'), "method_name": method, "native_query": method_def.get('sql'),
                       "method_usages": method_def.get('usages')}
            user_input = json.dumps(payload, indent=2)
            response.append(orchestrator.analyze(user_input))
    generate_performance_report(response)
