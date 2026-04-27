import json
from langchain_groq import ChatGroq
from chatbot_implementation.orchestrator.state import AgentState
from chatbot_implementation.orchestrator.prompts import INTENT_PROMPT, QUERY_PLAN_PROMPT, SYNTHESIS_PROMPT
from chatbot_implementation.database import get_engine
from sqlalchemy import select, func, column, table

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
    #print statement to see what its runnign
    print("=== RAW LLM OUTPUT ===")
    print(repr(raw))
    print("======================")

    # Strip markdown code blocks if LLM wraps response in them
    if "```" in raw:
        # Extract content between the first ``` and last ```
        raw = raw.split("```")[1]
        # Remove language identifier like "json" at the start
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        return {**state, "error": f"Failed to parse query plan. Error: {str(e)}. Raw: {raw}"}

    return {**state, "query_plan": plan}

def execute_sql(state: AgentState) -> AgentState:
    if state.get("final_answer") or state.get("error"):
        return state

    plan = state.get("query_plan")
    if not plan:
        return {**state, "error": "No query plan available."}

    try:
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

        for col, val in (plan.get("filters") or {}).items():
            stmt = stmt.where(column(col) == val)

        stmt = stmt.group_by(column(plan["dimension"])).limit(500)

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

    chain = SYNTHESIS_PROMPT | get_llm()
    result = chain.invoke({
        "question": state["user_question"],
        "query_plan": json.dumps(state.get("query_plan")),
        "sql_result": json.dumps(state.get("sql_result", [])[:50]),
        "validation_flags": json.dumps(state.get("validation_flags", {}))
    })
    return {**state, "final_answer": result.content}