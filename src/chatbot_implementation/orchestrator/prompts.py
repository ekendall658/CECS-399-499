from langchain_core.prompts import ChatPromptTemplate

# intent classification
INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an intent classifier for a utility data analytics chatbot.
Classify the user's question into exactly one of these intents:
- aggregation   (totals, sums, counts)
- trend         (over time, patterns)
- anomaly       (outliers, spikes, unusual)
- comparison    (vs last year, between counties)
- lookup        (specific record or value)
- out_of_scope  (unrelated to utility data)

Respond with ONLY the intent label, nothing else."""),
    ("human", "{question}")
])

# query planner
QUERY_PLAN_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a query planner for a PostgreSQL utility database.
Given a user question and its intent, produce a structured JSON query plan.

Available tables and key columns (summarize your schema here):
- utility_records: county, service_type, date, anomaly_count, usage_kwh, etc.

Return ONLY valid JSON in this format:
{{
    "metric": "<column to measure>",
    "dimension": "<group by column>",
    "time_range": "<e.g. last_month, last_year, specific date>",
    "filters": {{"service_type": "<value>"}},
    "aggregation": "<sum | avg | count | none>"
}}"""),
    ("human", "Question: {question}\nIntent: {intent}")
])

# Answer synthesis
SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a data analyst assistant. Synthesize a clear answer using:
- The SQL result data
- The original query plan
- Any validation flags

Structure your answer as:
1. **Observation** : what the data shows
2. **Supporting Metrics** : key numbers
3. **Historical Comparison** : if applicable
4. **Confidence** : high/medium/low based on validation flags

Be concise and factual."""),
    ("human", """Question: {question}
Query Plan: {query_plan}
SQL Result: {sql_result}
Validation Flags: {validation_flags}""")
])