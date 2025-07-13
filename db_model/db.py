import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Config
from db_model.models import Base

DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI

async_engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, class_=AsyncSession
)

if __name__ == "__main__":
    async def main():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(main())


