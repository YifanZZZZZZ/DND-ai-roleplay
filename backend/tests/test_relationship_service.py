from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.relationship_agent import (
    RelationshipAgentResult,
    RelationshipDecision,
    RelationshipUpdate,
)
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.engine import create_engine
from backend.app.db.models import (
    Campaign,
    CampaignMembership,
    Character,
    CharacterAcquaintance,
    GameSession,
    Message,
    MessageRecipient,
    SessionRuntime,
)
from backend.app.domain.enums import (
    CampaignLifecycleStatus,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    RuntimeStatus,
)
from backend.app.services.relationship_service import RelationshipService


class FakeRelationshipAgent:
    def __init__(self, character_a_id: str, character_b_id: str) -> None:
        self.character_a_id = character_a_id
        self.character_b_id = character_b_id
        self.contexts: list[str] = []

    async def refresh(self, context: str) -> RelationshipAgentResult:
        self.contexts.append(context)
        return RelationshipAgentResult(
            output=RelationshipDecision(
                updates=[
                    RelationshipUpdate(
                        character_a_id=self.character_a_id,
                        character_b_id=self.character_b_id,
                        acquainted=True,
                        relationship_history="在断桥前互相救援，因此开始信任彼此。",
                    )
                ]
            ),
            input_tokens=10,
            output_tokens=8,
        )


@pytest.fixture
async def relationship_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = Settings(data_dir=tmp_path / "data")
    engine = create_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


async def test_relationship_is_generated_from_only_the_shared_story(
    relationship_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    async with relationship_factory() as session:
        aria = Character(name="艾莉娅", roleplay_prompt="冷静", max_hp=20)
        bran = Character(name="布兰", roleplay_prompt="勇敢", max_hp=20)
        campaign = Campaign(name="自动关系测试", lifecycle_status=CampaignLifecycleStatus.ACTIVE)
        campaign.memberships = [
            CampaignMembership(character=aria),
            CampaignMembership(character=bran),
        ]
        game_session = GameSession(title="当前故事", campaign=campaign, next_sequence_no=3)
        game_session.runtime = SessionRuntime(status=RuntimeStatus.IDLE)
        shared = Message(
            session=game_session,
            sequence_no=1,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PUBLIC,
            content="断桥坍塌时，两人互相抓住了对方。",
        )
        shared.recipients = [
            MessageRecipient(character=aria),
            MessageRecipient(character=bran),
        ]
        private = Message(
            session=game_session,
            sequence_no=2,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PRIVATE,
            content="只有艾莉娅知道的秘密。",
        )
        private.recipients = [MessageRecipient(character=aria)]
        session.add_all([campaign, game_session, shared, private])
        await session.commit()
        pair = sorted((aria.id, bran.id))
        agent = FakeRelationshipAgent(pair[0], pair[1])

        await RelationshipService(
            session,
            Settings(data_dir=tmp_path / "settings"),
            agent,
        ).refresh_for_campaign(campaign.id)

        relationship = await session.get(CharacterAcquaintance, (pair[0], pair[1]))
        assert relationship is not None
        assert relationship.relationship_history == "在断桥前互相救援，因此开始信任彼此。"
        assert "断桥坍塌" in agent.contexts[0]
        assert "只有艾莉娅知道的秘密" not in agent.contexts[0]
