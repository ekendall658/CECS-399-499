from langgraph.graph import StateGraph, END
from chatbot_implementation.orchestrator.state import AgentState
from chatbot_implementation.orchestrator.nodes import (
    classify_intent,
    plan_query,
    execute_sql,
    validate_result,
    synthesize_answer,
)

def should_continue(state: AgentState) -> str:
    if state.get("final_answer") or state.get("error"):
        return "synthesize_answer"
    return "execute_sql"

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("plan_query", plan_query)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("validate_result", validate_result)
    graph.add_node("synthesize_answer", synthesize_answer)

    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "plan_query")

    graph.add_conditional_edges("plan_query", should_continue, {
        "execute_sql": "execute_sql",
        "synthesize_answer": "synthesize_answer"
    })

    graph.add_edge("execute_sql", "validate_result")
    graph.add_edge("validate_result", "synthesize_answer")
    graph.add_edge("synthesize_answer", END)

    return graph.compile()

agent_graph = build_graph()