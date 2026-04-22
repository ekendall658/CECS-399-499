
from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env") 
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from chatbot_implementation.database import AsyncSessionLocal
from chatbot_implementation.routers.chat import router as chat_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/test")
async def test_connection(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"status": "connected", "result": result.scalar()}