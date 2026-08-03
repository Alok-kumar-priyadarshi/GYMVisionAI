# file_name: user_repository.py

"""SQLAlchemy implementations of the user repositories."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import BodyProfile, User
from app.domain.repositories.user_repository import (
    BodyProfileRepository,
    UserRepository,
)
from app.infrastructure.database import mappers
from app.infrastructure.database.models import BodyProfileModel, UserModel


class SqlUserRepository(UserRepository):
    """Stores users in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return mappers.to_user(model) if model else None

    async def get_by_google_id(self, google_id: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.google_id == google_id)
        )
        model = result.scalar_one_or_none()
        return mappers.to_user(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return mappers.to_user(model) if model else None

    async def add(self, user: User) -> User:
        model = mappers.to_user_model(user)
        self._session.add(model)
        await self._session.flush()
        return mappers.to_user(model)

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise ValueError(f"user {user.id} does not exist")

        mappers.apply_user(model, user)
        await self._session.flush()
        return mappers.to_user(model)

    async def exists(self, user_id: UUID) -> bool:
        result = await self._session.execute(
            select(UserModel.id).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none() is not None


class SqlBodyProfileRepository(BodyProfileRepository):
    """Stores body profiles in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: UUID) -> BodyProfile | None:
        result = await self._session.execute(
            select(BodyProfileModel).where(BodyProfileModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return mappers.to_body_profile(model) if model else None

    async def add(self, profile: BodyProfile) -> BodyProfile:
        model = mappers.to_body_profile_model(profile)
        self._session.add(model)
        await self._session.flush()
        return mappers.to_body_profile(model)

    async def update(self, profile: BodyProfile) -> BodyProfile:
        result = await self._session.execute(
            select(BodyProfileModel).where(BodyProfileModel.user_id == profile.user_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"body profile for user {profile.user_id} does not exist")

        mappers.apply_body_profile(model, profile)
        await self._session.flush()
        return mappers.to_body_profile(model)
