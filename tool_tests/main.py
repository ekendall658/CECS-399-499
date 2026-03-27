from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlalchemy.engine.url import URL

DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username="cecs_energy_lake",
    password="94_8y-g2408!gsdf?",
    host="postgres-1.cju08ags2kn7.us-east-2.rds.amazonaws.com",
    port=5432,
    database="postgres-1"
)

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": "require"},
    echo=True
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

app = FastAPI()

@app.get("/test")
async def test_connection():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        return {"status": "connected", "result": result.scalar()}