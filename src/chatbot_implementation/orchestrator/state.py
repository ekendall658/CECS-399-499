from typing import TypedDict, Optional, Any

class AgentState(TypedDict):
    # input
    user_question: str

    # pipeline stages
    intent: Optional[str]  
    #JSON plan for which tools to call         
    query_plan: Optional[dict]  
    # generated SQL str   
    sql_query: Optional[str]
    #raw db rows        
    sql_result: Optional[list]     
    validation_flags: Optional[dict]
    final_answer: Optional[str]
    chart_data: Optional[Any]

    #controls flow
    error: Optional[str]