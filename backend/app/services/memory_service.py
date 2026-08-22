from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas.characters import MemoryCreate, MemoryUpdate
from backend.app.core.errors import NotFoundError
from backend.app.db.models import Character, CharacterMemory
from backend.app.domain.enums import MemoryOrigin
from backend.app.services.edit_lock import ensure_character_editable


class MemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, character_id: str) -> list[CharacterMemory]:
        await self._character(character_id)
        return list(
            await self.session.scalars(
                select(CharacterMemory)
                .where(CharacterMemory.character_id == character_id)
                .order_by(CharacterMemory.pinned.desc(), CharacterMemory.updated_at.desc())
            )
        )

    async def create(self, character_id: str, payload: MemoryCreate) -> CharacterMemory:
        await self._character(character_id)
        await ensure_character_editable(self.session, character_id)
        memory = CharacterMemory(
            character_id=character_id,
            origin=MemoryOrigin.DM,
            content=payload.content.strip(),
            pinned=payload.pinned,
        )
        self.session.add(memory)
        await self.session.commit()
        return memory

    async def update(
        self, character_id: str, memory_id: str, payload: MemoryUpdate
    ) -> CharacterMemory:
        memory = await self._memory(character_id, memory_id)
        await ensure_character_editable(self.session, character_id)
        if payload.content is not None:
            memory.content = payload.content.strip()
        if payload.pinned is not None:
            memory.pinned = payload.pinned
        await self.session.commit()
        return memory

    async def delete(self, character_id: str, memory_id: str) -> None:
        memory = await self._memory(character_id, memory_id)
        await ensure_character_editable(self.session, character_id)
        await self.session.delete(memory)
        await self.session.commit()

    async def _character(self, character_id: str) -> Character:
        character = await self.session.get(Character, character_id)
        if character is None:
            raise NotFoundError("Character", character_id)
        return character

    async def _memory(self, character_id: str, memory_id: str) -> CharacterMemory:
        memory = await self.session.scalar(
            select(CharacterMemory).where(
                CharacterMemory.id == memory_id,
                CharacterMemory.character_id == character_id,
            )
        )
        if memory is None:
            raise NotFoundError("CharacterMemory", memory_id)
        return memory
