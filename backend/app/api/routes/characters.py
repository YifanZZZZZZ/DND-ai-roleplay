from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import JSONResponse

from backend.app.api.dependencies import DatabaseSession, FileStorageDependency
from backend.app.api.schemas.characters import (
    CharacterCreate,
    CharacterDetail,
    CharacterSummary,
    CharacterUpdate,
    MemoryCreate,
    MemoryUpdate,
    MemoryView,
    SkillSetUpdate,
    SkillSetView,
)
from backend.app.api.schemas.sheets import SheetActivation, SheetPreview
from backend.app.db.models import Character, CharacterMemory
from backend.app.services.character_service import CharacterService
from backend.app.services.export_service import ExportService
from backend.app.services.memory_service import MemoryService
from backend.app.services.sheet_service import SheetService
from backend.app.services.skill_service import SkillService

router = APIRouter(prefix="/characters", tags=["characters"])


def to_summary(character: Character) -> CharacterSummary:
    return CharacterSummary(
        id=character.id,
        name=character.name,
        max_hp=character.max_hp,
        avatar_path=character.avatar_path,
        has_roleplay_prompt=bool(character.roleplay_prompt.strip()),
        has_active_sheet=character.active_sheet_version_id is not None,
        revision=character.revision,
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


def to_detail(character: Character) -> CharacterDetail:
    summary = to_summary(character)
    return CharacterDetail(
        **summary.model_dump(),
        roleplay_prompt=character.roleplay_prompt,
        voice_samples=character.voice_samples,
        narration_notes=character.narration_notes,
        profile_content=character.profile.content,
        profile_status=character.profile.status,
    )


def to_memory_view(memory: CharacterMemory) -> MemoryView:
    return MemoryView.model_validate(memory)


@router.get("", response_model=list[CharacterSummary])
async def list_characters(session: DatabaseSession) -> list[CharacterSummary]:
    characters = await CharacterService(session).list()
    return [to_summary(character) for character in characters]


@router.post("", response_model=CharacterDetail, status_code=status.HTTP_201_CREATED)
async def create_character(payload: CharacterCreate, session: DatabaseSession) -> CharacterDetail:
    character = await CharacterService(session).create(payload)
    return to_detail(character)


@router.get("/{character_id}", response_model=CharacterDetail)
async def get_character(character_id: str, session: DatabaseSession) -> CharacterDetail:
    character = await CharacterService(session).get(character_id)
    return to_detail(character)


@router.patch("/{character_id}", response_model=CharacterDetail)
async def update_character(
    character_id: str, payload: CharacterUpdate, session: DatabaseSession
) -> CharacterDetail:
    character = await CharacterService(session).update(character_id, payload)
    return to_detail(character)


@router.post("/{character_id}/avatar", response_model=CharacterDetail)
async def upload_avatar(
    character_id: str,
    session: DatabaseSession,
    storage: FileStorageDependency,
    file: Annotated[UploadFile, File()],
) -> CharacterDetail:
    return to_detail(await CharacterService(session).set_avatar(character_id, storage, file))


@router.get("/{character_id}/skills", response_model=SkillSetView)
async def get_skills(character_id: str, session: DatabaseSession) -> SkillSetView:
    skill_set = await SkillService(session).get(character_id)
    return SkillSetView.model_validate(skill_set)


@router.put("/{character_id}/skills", response_model=SkillSetView)
async def update_skills(
    character_id: str, payload: SkillSetUpdate, session: DatabaseSession
) -> SkillSetView:
    skill_set = await SkillService(session).update(character_id, payload)
    return SkillSetView.model_validate(skill_set)


@router.get("/{character_id}/memories", response_model=list[MemoryView])
async def list_memories(character_id: str, session: DatabaseSession) -> list[MemoryView]:
    return [to_memory_view(item) for item in await MemoryService(session).list(character_id)]


@router.post(
    "/{character_id}/memories", response_model=MemoryView, status_code=status.HTTP_201_CREATED
)
async def create_memory(
    character_id: str, payload: MemoryCreate, session: DatabaseSession
) -> MemoryView:
    return to_memory_view(await MemoryService(session).create(character_id, payload))


@router.patch("/{character_id}/memories/{memory_id}", response_model=MemoryView)
async def update_memory(
    character_id: str, memory_id: str, payload: MemoryUpdate, session: DatabaseSession
) -> MemoryView:
    return to_memory_view(await MemoryService(session).update(character_id, memory_id, payload))


@router.delete("/{character_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(character_id: str, memory_id: str, session: DatabaseSession) -> None:
    await MemoryService(session).delete(character_id, memory_id)


@router.get("/{character_id}:export")
async def export_character(character_id: str, session: DatabaseSession) -> JSONResponse:
    return JSONResponse(await ExportService(session).character(character_id))


@router.post(
    "/{character_id}/sheet-versions:preview",
    response_model=SheetPreview,
    status_code=status.HTTP_201_CREATED,
)
async def preview_character_sheet(
    character_id: str,
    session: DatabaseSession,
    storage: FileStorageDependency,
    file: Annotated[UploadFile, File()],
) -> SheetPreview:
    return await SheetService(session, storage).preview(character_id, file)


@router.post(
    "/{character_id}/sheet-versions/{version_id}:activate",
    response_model=SheetActivation,
)
async def activate_character_sheet(
    character_id: str,
    version_id: str,
    session: DatabaseSession,
    storage: FileStorageDependency,
) -> SheetActivation:
    return await SheetService(session, storage).activate(character_id, version_id)
