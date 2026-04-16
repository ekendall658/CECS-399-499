from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.orchestrator.graph import agent_graph

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    intent: str | None
    query_plan: dict | None
    sql_result: list | None
    validation_flags: dict | None
    chart_data: dict | None

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = agent_graph.invoke({
            "user_question": request.question,
            "intent": None,
            "query_plan": None,
            "sql_query": None,
            "sql_result": None,
            "validation_flags": None,
            "final_answer": None,
            "chart_data": None,
            "error": None,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        answer=result.get("final_answer", "No answer generated."),
        intent=result.get("intent"),
        query_plan=result.get("query_plan"),
        sql_result=result.get("sql_result"),
        validation_flags=result.get("validation_flags"),
        chart_data=result.get("chart_data"),
    )