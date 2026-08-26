from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.dm_agent import DmAgentResult, DmDecision
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.engine import create_engine
from backend.app.db.models import (
    Campaign,
    CampaignDmDraft,
    CampaignMembership,
    Character,
    GameSession,
    Message,
    MessageRecipient,
    SessionRuntime,
)
from backend.app.domain.enums import (
    CampaignLifecycleStatus,
    CampaignPlayMode,
    DmDraftStatus,
    DmDraftTriggerType,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    RuntimeStatus,
)
from backend.app.services.dm_draft_service import DmDraftService


class FakeDmAgent:
    def __init__(self, recipient_id: str) -> None:
        self.recipient_id = recipient_id
        self.system_prompts: list[str] = []
        self.contexts: list[str] = []

    async def draft(self, system_prompt: str, context: str) -> DmAgentResult:
        self.system_prompts.append(system_prompt)
        self.contexts.append(context)
        assert "最新角色回复" in context
        return DmAgentResult(
            output=DmDecision(
                content="只有布兰听见门后传来一声低语。",
                audience="PRIVATE",
                recipient_character_ids=[self.recipient_id],
            )
        )


@pytest.fixture
async def dm_draft_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = Settings(data_dir=tmp_path / "data")
    engine = create_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


async def test_new_character_reply_stales_old_draft_and_generates_private_replacement(
    dm_draft_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    async with dm_draft_factory() as session:
        aria = Character(name="艾莉娅", roleplay_prompt="冷静", max_hp=20)
        bran = Character(name="布兰", roleplay_prompt="谨慎", max_hp=20)
        campaign = Campaign(
            name="草稿替换测试",
            module_content="一座会低语的古堡。",
            lifecycle_status=CampaignLifecycleStatus.ACTIVE,
            play_mode=CampaignPlayMode.NARRATIVE,
        )
        campaign.memberships = [
            CampaignMembership(character=aria),
            CampaignMembership(character=bran),
        ]
        game_session = GameSession(title="当前故事", campaign=campaign, next_sequence_no=2)
        game_session.runtime = SessionRuntime(
            status=RuntimeStatus.WAITING_FOR_DM,
            waiting_request="正在生成旧草稿",
        )
        reply = Message(
            session=game_session,
            sequence_no=1,
            sender_type=MessageSenderType.CHARACTER,
            sender_character=aria,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PUBLIC,
            content="我推开门。",
        )
        reply.recipients = [
            MessageRecipient(character=aria),
            MessageRecipient(character=bran),
        ]
        session.add_all([campaign, game_session, reply])
        await session.flush()
        game_session.runtime.waiting_message_id = reply.id
        old_draft = CampaignDmDraft(
            campaign_id=campaign.id,
            session_id=game_session.id,
            source_message_id="older-message",
            trigger_type=DmDraftTriggerType.CHARACTER_REPLY,
            content="这是一份没有发送的旧草稿。",
            status=DmDraftStatus.READY,
        )
        session.add(old_draft)
        await session.commit()

        generated = await DmDraftService(
            session,
            Settings(data_dir=tmp_path / "settings"),
            FakeDmAgent(bran.id),
        ).generate_for_character_reply(reply.id)

        assert generated is not None
        assert generated.id != old_draft.id
        assert generated.status == DmDraftStatus.READY
        assert generated.audience == MessageAudience.PRIVATE
        assert generated.recipient_character_ids == [bran.id]
        await session.refresh(old_draft)
        await session.refresh(game_session, ["runtime"])
        assert old_draft.status == DmDraftStatus.STALE
        assert game_session.runtime.status == RuntimeStatus.WAITING_FOR_DM
        assert game_session.runtime.waiting_message_id == reply.id
        assert game_session.runtime.waiting_request == "正在生成旧草稿"


def test_ai_dm_output_has_a_short_hard_limit() -> None:
    with pytest.raises(ValueError):
        DmDecision(content="长" * 801)


def test_ai_dm_output_allows_natural_personal_pronouns() -> None:
    decision = DmDecision(content="我看见门开了，你们跟上。")
    assert decision.content == "我看见门开了，你们跟上。"
