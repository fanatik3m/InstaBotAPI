import uuid
from typing import Union

from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession


class BaseDAO:
    model = None

    @classmethod
    async def find_all(cls, session: AsyncSession, *filter, **filter_by):
        query = select(cls.model).filter(*filter).filter_by(**filter_by)
        result = await session.execute(query)
        return result.scalars().all()

    @classmethod
    async def find_one(cls, session: AsyncSession, *filter, **filter_by):
        query = select(cls.model).filter(*filter).filter_by(**filter_by)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def find_by_id(cls, session: AsyncSession, model_id: Union[int, uuid.UUID]):
        query = select(cls.model).filter_by(id=model_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def add(cls, session: AsyncSession, **data):
        stmt = insert(cls.model).values(**data).returning(cls.model)
        result = await session.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def update(cls, session: AsyncSession, *where, **data):
        stmt = update(cls.model).where(*where).values(**data).returning(cls.model)
        result = await session.execute(stmt)
        return result.scalars().one()

    @classmethod
    async def delete(cls, session: AsyncSession, *filter, **filter_by):
        stmt = delete(cls.model).filter(*filter).filter_by(**filter_by)
        await session.execute(stmt)
