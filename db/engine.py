from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from core.config import DATABASE_URL
from db.models import Base

# Yangi kuchli PostgreSQL matori
engine = create_async_engine(DATABASE_URL, echo=False)

# Sessiya yaratuvchi
AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def init_db():
    # Jadvallarni bazada yaratish
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)