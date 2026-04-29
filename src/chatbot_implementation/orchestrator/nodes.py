import json

from langchain_groq import ChatGroq
from chatbot_implementation.orchestrator.state import AgentState
from chatbot_implementation.orchestrator.prompts import INTENT_PROMPT, QUERY_PLAN_PROMPT, SYNTHESIS_PROMPT
from chatbot_implementation.database import get_engine
from sqlalchemy import cast, Date, desc, func, or_, select, String, text
from sqlalchemy.sql import column, table
from datetime import datetime

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(model="llama-3.3-70b-versatile")
    return _llm


def classify_intent(state: AgentState) -> AgentState:
    chain = INTENT_PROMPT | get_llm()
    result = chain.invoke({"question": state["user_question"]})
    return {**state, "intent": result.content.strip()}


def plan_query(state: AgentState) -> AgentState:
    if state.get("intent") == "out_of_scope":
        return {**state, "final_answer": "That question is outside the scope of this tool."}

    chain = QUERY_PLAN_PROMPT | get_llm()
    result = chain.invoke({
        "question": state["user_question"],
        "intent": state["intent"]
    })

    raw = result.content.strip()
    print("=== RAW LLM OUTPUT ===")
    print(repr(raw))
    print("======================")

    # Strip markdown code blocks if LLM wraps response in them
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        # LLM returned a plain-text explanation instead of JSON — show it cleanly
        return {**state, "final_answer": raw}

    return {**state, "query_plan": plan}


def execute_sql(state: AgentState) -> AgentState:
    """Executes SQL for fact_outage_daily with county-name joins and time filters."""
    if state.get("final_answer") or state.get("error"):
        return state

    plan = state.get("query_plan")

    if not plan:
        return {**state, "error": "No query plan available."}

    try:
        fact = table(
            "fact_outage_daily",
            column("county_id"),
            column("time_key"),
            column("customers_wo_power"),
        )
        county = table(
            "dim_county",
            column("county_id"),
            column("county_name"),
        )

        agg_map = {
            "sum": func.sum,
            "avg": func.avg,
            "count": func.count,
            "none": lambda c: c,
        }

        aggregation = plan.get("aggregation", "sum")
        agg_fn = agg_map.get(aggregation, func.sum)

        metric = plan.get("metric", "customers_wo_power")
        dimension = plan.get("dimension", "time_key")
        filters = plan.get("filters") or {}

        allowed_metrics = {"customers_wo_power"}
        allowed_dimensions = {"time_key", "county_id", "county_name"}
        allowed_filters = {"county_id", "county_name"}

        if metric not in allowed_metrics:
            return {**state, "error": f"Unsupported metric: {metric}"}
        if dimension not in allowed_dimensions:
            return {**state, "error": f"Unsupported dimension: {dimension}"}

        invalid_filters = sorted(set(filters) - allowed_filters)
        if invalid_filters:
            return {**state, "error": f"Unsupported filter(s): {', '.join(invalid_filters)}"}

        metric_col = fact.c.customers_wo_power
        from_clause = fact

        needs_county_join = (
            dimension == "county_name"
            or "county_name" in filters
            or (
                "county_id" in filters
                and isinstance(filters["county_id"], (str, list))
                and not str(filters["county_id"]).isdigit()
            )
        )
        if needs_county_join:
            from_clause = fact.join(county, fact.c.county_id == county.c.county_id)

        dimension_col = county.c.county_name if dimension == "county_name" else fact.c[dimension]
        value_col = agg_fn(metric_col).label("value")

        stmt = select(
            dimension_col.label("name"),
            value_col
        ).select_from(from_clause)

        time_key_date = cast(cast(fact.c.time_key, String), Date)
        time_range = str(plan.get("time_range") or "").strip().lower()

        if time_range:
            if time_range.isdigit() and len(time_range) == 4:
                stmt = stmt.where(func.extract("year", time_key_date) == int(time_range))
            elif time_range == "last_6_months":
                max_date = select(func.max(time_key_date)).select_from(fact).scalar_subquery()
                stmt = stmt.where(time_key_date >= max_date - text("interval '6 months'"))
            elif time_range == "last_month":
                max_date = select(func.max(time_key_date)).select_from(fact).scalar_subquery()
                stmt = stmt.where(time_key_date >= max_date - text("interval '1 month'"))
            elif time_range == "last_year":
                max_date = select(func.max(time_key_date)).select_from(fact).scalar_subquery()
                stmt = stmt.where(time_key_date >= max_date - text("interval '1 year'"))

        if "county_id" in filters and filters["county_id"] not in (None, ""):
            county_id_val = filters["county_id"]
            if isinstance(county_id_val, list):
                # Check if LLM put county names in county_id by mistake
                if any(isinstance(x, str) and not str(x).isdigit() for x in county_id_val):
                    names = [n.strip().lower() for n in county_id_val]
                    stmt = stmt.where(or_(*[
                        or_(
                            func.lower(county.c.county_name) == n,
                            func.lower(county.c.county_name) == n.removesuffix(" county").strip()
                        )
                        for n in names
                    ]))
                else:
                    stmt = stmt.where(fact.c.county_id.in_([int(x) for x in county_id_val]))
            elif isinstance(county_id_val, str) and not county_id_val.isdigit():
                county_filter = county_id_val.strip().lower()
                stmt = stmt.where(or_(
                    func.lower(county.c.county_name) == county_filter,
                    func.lower(county.c.county_name) == county_filter.removesuffix(" county").strip()
                ))
            else:
                stmt = stmt.where(fact.c.county_id == int(county_id_val))

        if "county_name" in filters and filters["county_name"]:
            county_name_val = filters["county_name"]
            if isinstance(county_name_val, list):
                names = [n.strip().lower() for n in county_name_val]
                stmt = stmt.where(or_(*[
                    or_(
                        func.lower(county.c.county_name) == n,
                        func.lower(county.c.county_name) == n.removesuffix(" county").strip()
                    )
                    for n in names
                ]))
            else:
                county_filter = str(county_name_val).strip().lower()
                county_filter_without_suffix = county_filter.removesuffix(" county").strip()
                stmt = stmt.where(or_(
                    func.lower(county.c.county_name) == county_filter,
                    func.lower(county.c.county_name) == county_filter_without_suffix,
                ))

        stmt = stmt.group_by(dimension_col)

        if dimension == "time_key":
            stmt = stmt.order_by(fact.c.time_key.asc())
        else:
            stmt = stmt.order_by(desc(value_col))

        stmt = stmt.limit(500)

        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
            sql_result = [dict(row) for row in rows]

        return {**state, "sql_result": sql_result}

    except Exception as e:
        return {**state, "error": f"SQL execution failed: {str(e)}"}


def validate_result(state: AgentState) -> AgentState:
    if state.get("final_answer") or state.get("error"):
        return state

    result = state.get("sql_result", [])
    flags = {}

    if not result:
        flags["empty_result"] = True

    if len(result) >= 500:
        flags["row_limit_exceeded"] = True

    null_count = sum(1 for row in result if row.get("value") is None)
    if result and null_count / len(result) > 0.5:
        flags["null_heavy"] = True

    values = [row["value"] for row in result if row.get("value") is not None]
    if len(values) > 1:
        avg = sum(values) / len(values)
        if avg != 0:
            outliers = [v for v in values if abs(v - avg) > 3 * abs(avg)]
            if outliers:
                flags["extreme_outliers"] = True

    return {**state, "validation_flags": flags}


def synthesize_answer(state: AgentState) -> AgentState:
    if state.get("final_answer"):
        return state
    if state.get("error"):
        return {**state, "final_answer": f"An error occurred: {state['error']}"}

    def datetime_handler(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return str(obj)

    chain = SYNTHESIS_PROMPT | get_llm()

    result = chain.invoke({
        "question": state["user_question"],
        "query_plan": json.dumps(state.get("query_plan"), default=datetime_handler),
        "sql_result": json.dumps(state.get("sql_result", [])[:50], default=datetime_handler),
        "validation_flags": json.dumps(state.get("validation_flags", {}), default=datetime_handler)
    })

    return {**state, "final_answer": result.content}