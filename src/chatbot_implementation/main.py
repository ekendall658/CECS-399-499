from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import AsyncSessionLocal

app = FastAPI()

#FastAPI will handle opening/closing the session per request
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/test")
async def test_connection(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"status": "connected", "result": result.scalar()}

@app.get("/query")
async def run_query(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM your_table WHERE county = :county"),
        {"county": "Knox"}
    )
    rows = result.fetchall()
    return {"rows": [dict(r._mapping) for r in rows]}