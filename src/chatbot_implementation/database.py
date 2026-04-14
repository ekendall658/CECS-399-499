from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import URL

DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username="cecs_energy_lake",
    password="94_8y-g2408!gsdf?",
    host="postgres-1.cju08ags2kn7.us-east-2.rds.amazonaws.com",
    port=5432,
    database="postgres"
)

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": "require"},
    echo=True
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)