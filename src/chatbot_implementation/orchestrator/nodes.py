import json
from langchain_anthropic import ChatAnthropic
from.state import AgentState
from.prompts import INTENT_PROMPT, QUERY_PLAN_PROMPT, SYNTHESIS_PROMPT
from sqlalchemy import text
from db.database import get_engine   # update for get_engine at 

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")  # using claude, subject ot change


# node 1 intent classificaiton
def classify_intent(state: AgentState) -> AgentState:
    chain = INTENT_PROMPT | llm
    result = chain.invoke({"question": state["user_question"]})
    return {**state, "intent": result.content.strip()}


# query planning
def plan_query(state: AgentState) -> AgentState:
    if state.get("intent") == "out_of_scope":
        return {**state, "final_answer": "That question is outside the scope of this tool."}

    chain = QUERY_PLAN_PROMPT | llm
    result = chain.invoke({
        "question": state["user_question"],
        "intent": state["intent"]
    })
    try:
        plan = json.loads(result.content)
    except json.JSONDecodeError:
        return {**state, "error": "Failed to parse query plan."}

    return {**state, "query_plan": plan}


# node 3, sql tool 
def execute_sql(state: AgentState) -> AgentState:
    plan = state.get("query_plan")
    if not plan:
        return {**state, "error": "No query plan available."}

    # build sql from sqlalchemy
    # will need to refine for schema we have
    from sqlalchemy import select, func, column, table

    tbl = table("utility_records",
                column("county"), column("service_type"),
                column("anomaly_count"), column("date"))

    agg_map = {
        "sum": func.sum, "avg": func.avg,
        "count": func.count, "none": lambda c: c
    }
    agg_fn = agg_map.get(plan.get("aggregation", "none"), lambda c: c)
    metric_col = column(plan["metric"])

    stmt = select(
        column(plan["dimension"]),
        agg_fn(metric_col).label("value")
    ).select_from(tbl)

    #filter
    for col, val in (plan.get("filters") or {}).items():
        stmt = stmt.where(column(col) == val)

    stmt = stmt.group_by(column(plan["dimension"])).limit(500)

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
        result = [dict(row) for row in rows]

    return {**state, "sql_result": result}


# node 4 validation - NO LLM
def validate_result(state: AgentState) -> AgentState:
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
    if values:
        avg = sum(values) / len(values)
        outliers = [v for v in values if abs(v - avg) > 3 * (avg or 1)]
        if outliers:
            flags["extreme_outliers"] = True

    return {**state, "validation_flags": flags}


# node answer synthesis
def synthesize_answer(state: AgentState) -> AgentState:
    if state.get("final_answer"):  # pre set
        return state

    chain = SYNTHESIS_PROMPT | llm
    result = chain.invoke({
        "question": state["user_question"],
        "query_plan": json.dumps(state.get("query_plan")),
        "sql_result": json.dumps(state.get("sql_result", [])[:50]), 
        "validation_flags": json.dumps(state.get("validation_flags", {}))
    })
    return {**state, "final_answer": result.content}