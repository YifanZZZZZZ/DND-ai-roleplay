from pathlib import Path

from pydantic import SecretStr

from backend.app.core.config import Settings
from backend.app.services.summary_service import SummaryService


def test_summary_model_falls_back_to_memory_then_character_model(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        character_model="character-model",
        memory_model="memory-model",
        summary_model="",
        deepseek_api_key=SecretStr("test-key"),
    )

    assert settings.summary_model_name == "memory-model"
    assert settings.summary_agent_is_configured

    character_fallback = settings.model_copy(update={"memory_model": ""})
    assert character_fallback.summary_model_name == "character-model"
    assert character_fallback.summary_agent_is_configured


def test_fallback_summary_is_bounded_and_marks_the_missing_middle() -> None:
    record = "A" * 4000 + "B" * 4000

    summary = SummaryService._fallback_summary(record)

    assert len(summary) <= 5000
    assert summary.startswith("A" * 100)
    assert summary.endswith("B" * 100)
    assert "【中间记录暂未完成智能摘要】" in summary


def test_fallback_summary_preserves_short_records() -> None:
    record = "本节可见事实记录：\n卡斯珀走进村庄。"

    assert SummaryService._fallback_summary(record) == record
