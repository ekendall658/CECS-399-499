from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from chatbot_implementation.orchestrator.graph import agent_graph

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    intent: str | None = None
    query_plan: dict | None = None
    sql_result: list | None = None
    validation_flags: dict | None = None
    chart_data: dict | None = None

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = agent_graph.invoke({
            "user_question": request.question,
            "intent": None,
            "query_plan": None,
            "sql_result": None,
            "validation_flags": None,
            "final_answer": None,
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