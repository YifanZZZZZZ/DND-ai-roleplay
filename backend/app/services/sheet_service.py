from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas.sheets import (
    SheetActivation,
    SheetActivationRequest,
    SheetPreview,
)
from backend.app.core.errors import AppError, NotFoundError
from backend.app.db.models import Character, CharacterSheetVersion, CharacterSkillSet
from backend.app.domain.enums import SheetParseStatus, SkillName
from backend.app.files.sheet_parser import (
    PARSER_VERSION,
    CharacterSheetParser,
    CharacterSheetSnapshot,
)
from backend.app.files.storage import FileStorage
from backend.app.services.edit_lock import ensure_character_editable
from backend.app.services.skill_service import DEFAULT_SKILL_MODIFIERS
from backend.app.services.spellbook_service import normalized_spellbook, spellbook_from_snapshot


class SheetService:
    def __init__(self, session: AsyncSession, storage: FileStorage | None = None) -> None:
        self.session = session
        self.storage = storage or FileStorage()
        self.parser = CharacterSheetParser()

    async def preview(self, character_id: str, upload: UploadFile) -> SheetPreview:
        character = await self.session.get(Character, character_id)
        if character is None:
            raise NotFoundError("Character", character_id)
        await ensure_character_editable(self.session, character_id)

        stored = await self.storage.save_character_sheet(upload)
        try:
            snapshot = self.parser.parse(stored.path)
        except AppError as error:
            failed_version = CharacterSheetVersion(
                character_id=character.id,
                stored_path=stored.relative_path,
                original_filename=stored.original_filename,
                sha256=stored.sha256,
                parse_status=SheetParseStatus.FAILED,
                parser_version=self.parser_version,
                parse_error_code=error.error_code,
            )
            self.session.add(failed_version)
            await self.session.commit()
            raise

        version = CharacterSheetVersion(
            character_id=character.id,
            stored_path=stored.relative_path,
            original_filename=stored.original_filename,
            sha256=stored.sha256,
            parse_status=SheetParseStatus.VALID,
            parser_version=snapshot.parser_version,
            parsed_snapshot=snapshot.model_dump(mode="json"),
        )
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)
        return SheetPreview(
            version_id=version.id,
            parse_status=version.parse_status,
            original_filename=version.original_filename,
            snapshot=snapshot,
            spellbook=spellbook_from_snapshot(snapshot),
            created_at=version.created_at,
        )

    async def activate(
        self,
        character_id: str,
        version_id: str,
        payload: SheetActivationRequest | None = None,
    ) -> SheetActivation:
        character = await self.session.get(Character, character_id)
        if character is None:
            raise NotFoundError("Character", character_id)
        await ensure_character_editable(self.session, character_id)
        version = await self.session.scalar(
            select(CharacterSheetVersion).where(
                CharacterSheetVersion.id == version_id,
                CharacterSheetVersion.character_id == character_id,
            )
        )
        if version is None:
            raise NotFoundError("CharacterSheetVersion", version_id)
        if version.parse_status != SheetParseStatus.VALID or version.parsed_snapshot is None:
            raise AppError("SHEET_VERSION_NOT_VALID", "只有解析成功的角色卡可以激活。")

        snapshot = CharacterSheetSnapshot.model_validate(version.parsed_snapshot)
        spellbook = payload.spellbook if payload is not None else spellbook_from_snapshot(snapshot)

        old_versions = list(
            await self.session.scalars(
                select(CharacterSheetVersion).where(
                    CharacterSheetVersion.character_id == character_id,
                    CharacterSheetVersion.id != version_id,
                )
            )
        )
        character.active_sheet_version_id = version.id
        character.spellbook = normalized_spellbook(spellbook)
        character.revision += 1

        if len(snapshot.skills) == len(SkillName):
            skill_set = await self.session.get(CharacterSkillSet, character_id)
            if skill_set is None:
                skill_set = CharacterSkillSet(
                    character_id=character_id, modifiers=dict(DEFAULT_SKILL_MODIFIERS)
                )
                self.session.add(skill_set)
            skill_set.modifiers = {
                skill.value: modifier for skill, modifier in snapshot.skills.items()
            }
            skill_set.revision += 1

        if old_versions:
            await self.session.execute(
                delete(CharacterSheetVersion).where(
                    CharacterSheetVersion.character_id == character_id,
                    CharacterSheetVersion.id != version_id,
                )
            )
        await self.session.commit()

        for old_version in old_versions:
            self._delete_stored_file(old_version.stored_path)

        return SheetActivation(
            character_id=character.id,
            active_version_id=version.id,
            snapshot=snapshot,
            spellbook=spellbook,
        )

    @property
    def parser_version(self) -> str:
        return PARSER_VERSION

    def _delete_stored_file(self, stored_path: str) -> None:
        path: Path = self.storage.resolve(stored_path)
        path.unlink(missing_ok=True)
