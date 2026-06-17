import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from server.database.models import Base

logger = logging.getLogger(__name__)

# In production, use PostgreSQL: "postgresql+asyncpg://user:pass@host/dbname"
DATABASE_URL = "sqlite+aiosqlite:///server/database/monitoring.db"

class DatabaseManager:
    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session_maker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        logger.info("Initializing Database schema...")
        async with self.engine.begin() as conn:
            # Create tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized.")

    async def get_session(self) -> AsyncSession:
        async with self.async_session_maker() as session:
            yield session

# Global DB instance
db_manager = DatabaseManager()
