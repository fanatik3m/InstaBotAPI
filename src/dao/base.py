import uuid
from typing import Union, TypeVar

from pydantic import BaseModel

from sqlalchemy import select, insert, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

Schema = TypeVar('Schema', bound=BaseModel)


class BaseDAO:
    model = None

    @classmethod
    async def find_all(cls, session: AsyncSession, *filter, **filter_by):
        query = select(cls.model).filter(*filter).filter_by(**filter_by)
        result = await session.execute(query)
        return result.scalars().all()

    @classmethod
    async def find_last(cls, session: AsyncSession, limit: int, order_by, **filter_by):
        query = select(cls.model).filter_by(**filter_by).order_by(desc(order_by)).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

    @classmethod
    async def find_pagination(cls, session: AsyncSession, offset: int, limit: int, *filter, **filter_by):
        query = select(cls.model).filter(*filter).filter_by(**filter_by).offset(offset).limit(limit)
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
    async def add(cls, session: AsyncSession, obj: Union[dict, Schema]):
        if isinstance(obj, dict):
            data = obj
        else:
            data = obj.model_dump(exclude_unset=True)

        stmt = insert(cls.model).values(**data).returning(cls.model)
        result = await session.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def update(cls, session: AsyncSession, *where, obj: Union[dict, Schema]):
        if isinstance(obj, dict):
            data = obj
        else:
            data = obj.model_dump(exclude_unset=True)

        stmt = update(cls.model).where(*where).values(**data).returning(cls.model)
        result = await session.execute(stmt)
        return result.scalars().one()

    @classmethod
    async def delete(cls, session: AsyncSession, *filter, **filter_by):
        stmt = delete(cls.model).filter(*filter).filter_by(**filter_by)
        await session.execute(stmt)
