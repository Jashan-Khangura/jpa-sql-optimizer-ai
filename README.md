# jpa-sql-optimizer-ai
JPA SQL Optimizer is an AI Agent to find database bottlenecks directly from your source code. It scans your application’s queries, compares them to your live schema, and identifies missing indexes or inefficient logic. By generating production-ready audit report and DDL scripts, it ensures high performance and scalability with zero manual effort.
The JPA SQL Optimizer Agent is an AI Agent that automates database performance tuning by analyzing application source code. It bridges the gap between Java/JPA development and database efficiency, ensuring your data layer scales seamlessly with your logic.

How it Works
1. Code Scouting: Uses Tree-sitter static analysis to extract @Entity mappings and @Query definitions directly from your repositories.
2. Usage Filtering: Scans service layers to identify "live" methods, ensuring optimization efforts are prioritized for active code.
3. Agentic Audit: An AI Agent compares extracted queries against live database metadata to perform a "Gap Analysis."
4. Reporting: Generates a professional PDF Performance Audit with optimized SQL rewrites and ready-to-run DDL scripts (e.g., CREATE INDEX).
Key Benefits
1. Proactive Tuning: Identifies missing indexes and "N+1" problems before they hit production.
2. Zero Overhead: Operates via static analysis without requiring application runtime or manual EXPLAIN PLAN sessions.
3. DBA-Level Insights: Delivers high-fidelity indexing strategies tailored to your specific query patterns.
4. Runs in local machine.
