"""Analyst tools — SQL querying and trend analysis over the revenue SQLite DB."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
from langchain.tools import tool
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from backend.config import get_settings
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


def _get_db() -> SQLDatabase:
    cfg = get_settings()
    return SQLDatabase.from_uri(f"sqlite:///{cfg.sqlite_db_path}")


@weave_op()
def _run_sql(query: str) -> str:
    """Execute a raw SQL query against the revenue DB and return results as text."""
    cfg = get_settings()
    try:
        conn = sqlite3.connect(str(cfg.sqlite_db_path))
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df.to_string(index=False)
    except Exception as exc:
        return f"SQL error: {exc}"


@weave_op()
def _generate_sql(natural_language_query: str) -> str:
    """Ask the LLM to translate a natural-language question into SQL."""
    cfg = get_settings()
    db = _get_db()
    schema = db.get_table_info()

    llm = ChatOpenAI(
        model=cfg.planner_model,
        temperature=0,
        openai_api_key=cfg.openai_api_key,
    )

    prompt = (
        "You are a SQL expert. Given the schema below, write a valid SQLite query "
        "that answers the user's question. Return ONLY the SQL statement, no explanation.\n\n"
        f"Schema:\n{schema}\n\n"
        f"Question: {natural_language_query}"
    )
    response = llm.invoke(prompt)
    sql = response.content.strip().strip("```sql").strip("```").strip()
    return sql


@tool
def analyst_sql_tool(question: str) -> str:
    """Query the structured revenue database using SQL to answer quantitative questions.

    Use this for specific numerical questions about Microsoft's revenue, net income,
    quarterly performance, or year-over-year comparisons.
    """
    sql = _generate_sql(question)
    logger.debug("Generated SQL: %s", sql)
    result = _run_sql(sql)
    return f"SQL Query: {sql}\n\nResult:\n{result}"


@weave_op()
def _compute_trends(df: pd.DataFrame) -> dict[str, Any]:
    """Compute basic trend statistics from the revenue DataFrame."""
    trends: dict[str, Any] = {}

    for col in ["revenue_usd_billions", "net_income_usd_billions"]:
        if col not in df.columns:
            continue
        values = df[col].tolist()
        if len(values) >= 2:
            pct_change = ((values[0] - values[-1]) / values[-1]) * 100
            trends[col] = {
                "latest": values[0],
                "earliest": values[-1],
                "pct_change": round(pct_change, 2),
                "trend": "upward" if pct_change > 0 else "downward",
            }

    return trends


@tool
def analyst_trend_tool(metric: str) -> str:
    """Analyse financial trends for a given metric over time.

    Suitable for: revenue growth rates, net income trends, YoY and QoQ comparisons.
    Pass the metric name (e.g. 'revenue', 'net income').
    """
    cfg = get_settings()
    try:
        conn = sqlite3.connect(str(cfg.sqlite_db_path))
        df = pd.read_sql_query(
            "SELECT * FROM revenue_summary ORDER BY year DESC, quarter DESC", conn
        )
        conn.close()
    except Exception as exc:
        return f"Database error: {exc}"

    trends = _compute_trends(df)
    if not trends:
        return "No trend data available."

    lines = [f"Trend analysis for '{metric}':"]
    for key, data in trends.items():
        lines.append(
            f"  {key}: {data['earliest']}B → {data['latest']}B "
            f"({data['pct_change']:+.1f}% change, {data['trend']} trend)"
        )
    return "\n".join(lines)
