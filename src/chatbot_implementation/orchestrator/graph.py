from langgraph.graph import StateGraph, END
from.state import AgentState
from.nodes import (
    classify_intent,
    plan_query,
    execute_sql,
    validate_result,
    synthesize_answer,
)

def build_graph():
    graph = StateGraph(AgentState)

    # register nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("plan_query", plan_query)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("validate_result", validate_result)
    graph.add_node("synthesize_answer", synthesize_answer)

    # linear edges
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "plan_query")
    graph.add_edge("plan_query", "execute_sql")
    graph.add_edge("execute_sql", "validate_result")
    graph.add_edge("validate_result", "synthesize_answer")
    graph.add_edge("synthesize_answer", END)

    # if out of scope, skips SQL stuff
    graph.add_conditional_edges(
        "plan_query",
        lambda state: END if state.get("final_answer") else "execute_sql"
    )

    return graph.compile()

#build single graph instance
agent_graph = build_graph()