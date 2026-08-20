from pathlib import Path
from zipfile import BadZipFile, ZipFile

from backend.app.core.errors import AppError

MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 120 * 1024 * 1024
XLSX_MAGIC = b"PK\x03\x04"


def validate_xlsx_archive(path: Path) -> None:
    if path.suffix.lower() != ".xlsx":
        raise AppError("SHEET_FILE_TYPE_INVALID", "角色卡必须是 .xlsx 文件。")
    size = path.stat().st_size
    if size == 0 or size > MAX_XLSX_BYTES:
        raise AppError("SHEET_FILE_SIZE_INVALID", "角色卡文件必须小于 10 MB。")
    with path.open("rb") as source:
        if source.read(4) != XLSX_MAGIC:
            raise AppError("SHEET_SIGNATURE_INVALID", "文件不是有效的 Excel 工作簿。")

    try:
        with ZipFile(path) as archive:
            total_size = 0
            for member in archive.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise AppError("SHEET_ARCHIVE_PATH_INVALID", "角色卡压缩结构不安全。")
                total_size += member.file_size
                if total_size > MAX_UNCOMPRESSED_BYTES:
                    raise AppError("SHEET_ARCHIVE_TOO_LARGE", "角色卡解压后的体积过大。")
                if member.filename.lower().endswith("vbaproject.bin"):
                    raise AppError("SHEET_MACRO_NOT_ALLOWED", "角色卡不能包含宏。")
    except BadZipFile as error:
        raise AppError("SHEET_ARCHIVE_INVALID", "文件不是有效的 Excel 工作簿。") from error
