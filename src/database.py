import aioredis
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config import DB_NAME, DB_PORT, DB_HOST, DB_USER, DB_PASSWORD, DB_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    url=DB_URL
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_redis():
    redis = await aioredis.from_url('redis://localhost')
    try:
        yield redis
    finally:
        await redis.close()
    # await redis.connection_pool.disconnect()