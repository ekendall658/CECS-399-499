from dotenv import load_dotenv
load_dotenv()
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import URL
from sqlalchemy import create_engine

# Async engine (for FastAPI routes)
DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 5432)),
    database=os.getenv("DB_NAME")
)

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": "require"},
    echo=True
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Sync engine (for orchestrator SQL tool calls)
SYNC_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USERNAME"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 5432)),
    database=os.getenv("DB_NAME")
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    connect_args={"sslmode": "require"},
    echo=True
)

def get_engine():
    return sync_engine