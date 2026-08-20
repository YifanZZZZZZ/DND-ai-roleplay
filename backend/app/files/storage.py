import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.core.ids import new_id
from backend.app.files.safety import MAX_XLSX_BYTES, validate_xlsx_archive

MAX_AVATAR_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@dataclass(frozen=True, slots=True)
class StoredUpload:
    path: Path
    relative_path: str
    original_filename: str
    sha256: str


class FileStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_data_directories()

    async def save_character_sheet(self, upload: UploadFile) -> StoredUpload:
        original_filename = Path(upload.filename or "character-sheet.xlsx").name
        if Path(original_filename).suffix.lower() != ".xlsx":
            raise AppError("SHEET_FILE_TYPE_INVALID", "角色卡必须是 .xlsx 文件。")

        file_id = new_id()
        temp_path = self.settings.data_dir / "temp" / f"{file_id}.xlsx"
        destination = self.settings.data_dir / "uploads" / "character-sheets" / f"{file_id}.xlsx"
        digest = hashlib.sha256()
        total_size = 0

        try:
            with temp_path.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > MAX_XLSX_BYTES:
                        raise AppError("SHEET_FILE_SIZE_INVALID", "角色卡文件必须小于 10 MB。")
                    digest.update(chunk)
                    target.write(chunk)
            validate_xlsx_archive(temp_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        temp_path.replace(destination)
        relative_path = destination.relative_to(self.settings.data_dir).as_posix()
        return StoredUpload(
            path=destination,
            relative_path=relative_path,
            original_filename=original_filename,
            sha256=digest.hexdigest(),
        )

    async def save_avatar(self, upload: UploadFile) -> StoredUpload:
        extension = IMAGE_TYPES.get(upload.content_type or "")
        if extension is None:
            raise AppError("AVATAR_FILE_TYPE_INVALID", "头像仅支持 PNG、JPEG 或 WebP 图片。")
        file_id = new_id()
        destination = self.settings.data_dir / "uploads" / "avatars" / f"{file_id}{extension}"
        digest = hashlib.sha256()
        total_size = 0
        try:
            with destination.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > MAX_AVATAR_BYTES:
                        raise AppError("AVATAR_FILE_SIZE_INVALID", "头像图片必须小于 5 MB。")
                    digest.update(chunk)
                    target.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
        return StoredUpload(
            path=destination,
            relative_path=destination.relative_to(self.settings.data_dir).as_posix(),
            original_filename=Path(upload.filename or "avatar").name,
            sha256=digest.hexdigest(),
        )

    def resolve(self, relative_path: str) -> Path:
        candidate = (self.settings.data_dir / relative_path).resolve()
        data_root = self.settings.data_dir.resolve()
        if candidate != data_root and data_root not in candidate.parents:
            raise AppError("STORAGE_PATH_INVALID", "存储路径无效。")
        return candidate
