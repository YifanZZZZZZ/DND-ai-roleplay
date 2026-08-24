from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.agents.character_agent import CharacterAgentResult, CharacterDecision
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.db.engine import create_engine
from backend.app.db.models import (
    AgentRun,
    Campaign,
    CampaignMembership,
    Character,
    CharacterAcquaintance,
    CharacterProfile,
    GameSession,
    LlmInvocation,
    Message,
    MessageRecipient,
    SessionCharacterState,
    SessionRuntime,
    SessionSummary,
)
from backend.app.domain.enums import (
    AgentRunStatus,
    CampaignLifecycleStatus,
    LlmInvocationStatus,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    RuntimeStatus,
    SessionStatus,
    SummaryAudience,
)
from backend.app.runtime.supervisor import RuntimeSupervisor


class FakeCharacterAgent:
    def __init__(self, result: CharacterAgentResult) -> None:
        self.result = result
        self.contexts: list[str] = []
        self.system_prompts: list[str] = []

    async def respond(self, system_prompt: str, context: str) -> CharacterAgentResult:
        self.system_prompts.append(system_prompt)
        self.contexts.append(context)
        return self.result


class ScriptedCharacterAgent:
    def __init__(self) -> None:
        self.contexts: list[str] = []
        self.system_prompts: list[str] = []

    async def respond(self, system_prompt: str, context: str) -> CharacterAgentResult:
        self.system_prompts.append(system_prompt)
        self.contexts.append(context)
        if "布兰" in system_prompt:
            return CharacterAgentResult(
                decision=CharacterDecision(
                    decision="RESPOND",
                    content="布兰举起手示意赛蕾妮先停下。",
                    urgency="HIGH",
                    requires_dm_resolution=True,
                    resolution_request="布兰能否从脚步声中判断对方距离？",
                ),
                input_tokens=9,
                output_tokens=7,
            )
        return CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="赛蕾妮安静地观察走廊。"),
            input_tokens=8,
            output_tokens=6,
        )


class FailingCharacterAgent:
    async def respond(self, system_prompt: str, context: str) -> CharacterAgentResult:
        del system_prompt, context
        raise RuntimeError("模拟供应商超时")


@pytest.fixture
async def runtime_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    settings = Settings(data_dir=tmp_path / "data")
    engine = create_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


async def _seed_run(factory: async_sessionmaker[AsyncSession]) -> tuple[str, str, str]:
    async with factory() as session:
        character = Character(name="赛蕾妮", roleplay_prompt="谨慎而友善。", max_hp=30)
        character.profile = CharacterProfile(content="信任自己的小队伙伴。")
        campaign = Campaign(name="测试战役", lifecycle_status=CampaignLifecycleStatus.ACTIVE)
        campaign.memberships = [CampaignMembership(character=character)]
        game_session = GameSession(title="第一节", campaign=campaign, next_sequence_no=2)
        game_session.runtime = SessionRuntime(
            status=RuntimeStatus.AGENTS_EVALUATING,
            generation=1,
        )
        game_session.character_states = [
            SessionCharacterState(character=character, current_hp=15, max_hp_snapshot=30)
        ]
        message = Message(
            session=game_session,
            sequence_no=1,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PUBLIC,
            content="昏暗的走廊尽头传来脚步声。",
            client_request_id="6b1a16ee-9c0f-4b42-b91a-0bd419eeedaa",
        )
        message.recipients = [MessageRecipient(character=character)]
        session.add_all([campaign, game_session, message])
        await session.flush()
        run = AgentRun(
            campaign_id=campaign.id,
            session_id=game_session.id,
            trigger_message_id=message.id,
            generation=1,
            status=AgentRunStatus.PENDING,
            eligible_count=1,
        )
        session.add(run)
        await session.flush()
        game_session.runtime.active_agent_run_id = run.id
        await session.commit()
        return run.id, game_session.id, character.id


async def _seed_two_character_run(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[str, str, str]:
    async with factory() as session:
        selene = Character(name="赛蕾妮", roleplay_prompt="赛蕾妮", max_hp=30)
        selene.profile = CharacterProfile(content="")
        bran = Character(name="布兰", roleplay_prompt="布兰", max_hp=20)
        bran.profile = CharacterProfile(content="")
        campaign = Campaign(name="双角色测试", lifecycle_status=CampaignLifecycleStatus.ACTIVE)
        campaign.memberships = [
            CampaignMembership(character=selene),
            CampaignMembership(character=bran),
        ]
        game_session = GameSession(title="第一节", campaign=campaign, next_sequence_no=2)
        game_session.runtime = SessionRuntime(status=RuntimeStatus.AGENTS_EVALUATING, generation=1)
        game_session.character_states = [
            SessionCharacterState(character=selene, current_hp=30, max_hp_snapshot=30),
            SessionCharacterState(character=bran, current_hp=20, max_hp_snapshot=20),
        ]
        message = Message(
            session=game_session,
            sequence_no=1,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=MessageAudience.PUBLIC,
            content="远处传来脚步声。",
            client_request_id="6b1a16ee-9c0f-4b42-b91a-0bd419eeedabc",
        )
        message.recipients = [MessageRecipient(character=selene), MessageRecipient(character=bran)]
        session.add_all([campaign, game_session, message])
        await session.flush()
        run = AgentRun(
            campaign_id=campaign.id,
            session_id=game_session.id,
            trigger_message_id=message.id,
            generation=1,
            status=AgentRunStatus.PENDING,
            eligible_count=2,
            random_seed=1,
        )
        session.add(run)
        await session.flush()
        game_session.runtime.active_agent_run_id = run.id
        await session.commit()
        return run.id, game_session.id, bran.id


async def test_supervisor_publishes_one_message_and_waits_for_dm(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, character_id = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(
                decision="RESPOND",
                content="赛蕾妮贴近墙边，试着辨认脚步声来自何处。",
                requires_dm_resolution=True,
                resolution_request="赛蕾妮是否能辨认脚步声的来源？",
            ),
            input_tokens=12,
            output_tokens=8,
        )
    )
    settings = Settings(
        data_dir=tmp_path / "runtime-data",
        deepseek_api_key="unused-for-fake-agent",
    )
    supervisor = RuntimeSupervisor(runtime_factory, lambda _: agent, settings)

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.WAITING_FOR_DM
        assert game_session.runtime.waiting_request == "赛蕾妮是否能辨认脚步声的来源？"
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert len(messages) == 2
        assert messages[-1].sender_character_id == character_id
        invocation = await session.scalar(
            select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id)
        )
        assert invocation is not None
        assert invocation.status == LlmInvocationStatus.COMPLETED
        assert invocation.input_tokens == 12
    assert len(agent.contexts) == 1
    assert "重伤" in agent.contexts[0]
    assert "15" not in agent.contexts[0]


async def test_narrative_character_message_continues_without_dm_resolution(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(
                decision="RESPOND",
                content="赛蕾妮转向布兰，问道：‘你怎么看？’",
                requires_dm_resolution=False,
            ),
            input_tokens=6,
            output_tokens=5,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )

    claimed = await supervisor._claim(run_id)
    assert claimed is not None
    selection, rejections = await supervisor._select_publishable(agent, claimed, [agent.result])
    next_run_id = await supervisor._commit_results(
        claimed, [agent.result], selection, rejections, 0.0
    )

    assert next_run_id is not None
    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.AGENTS_EVALUATING
        assert game_session.runtime.active_agent_run_id == next_run_id
        assert game_session.runtime.waiting_request is None
        followup = await session.get(AgentRun, next_run_id)
        assert followup is not None
        assert followup.status == AgentRunStatus.PENDING


async def test_stale_generation_cannot_publish_old_agent_result(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="赛蕾妮准备前进。"),
            input_tokens=None,
            output_tokens=None,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )
    claimed = await supervisor._claim(run_id)
    assert claimed is not None
    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        game_session.runtime.generation += 1
        game_session.runtime.active_agent_run_id = None
        await session.commit()

    selection, rejections = await supervisor._select_publishable(agent, claimed, [agent.result])
    await supervisor._commit_results(claimed, [agent.result], selection, rejections, 0.0)

    async with runtime_factory() as session:
        messages = list(
            await session.scalars(select(Message).where(Message.session_id == session_id))
        )
        assert len(messages) == 1
        invocation = await session.scalar(
            select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id)
        )
        assert invocation is not None
        assert invocation.status == LlmInvocationStatus.CANCELLED


async def test_parallel_candidates_publish_only_the_coordinator_choice(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, bran_id = await _seed_two_character_run(runtime_factory)
    agent = ScriptedCharacterAgent()
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert len(messages) == 2
        assert messages[-1].sender_character_id == bran_id
        invocations = list(
            await session.scalars(select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id))
        )
        assert len(invocations) == 2
        assert {item.status for item in invocations} == {LlmInvocationStatus.COMPLETED}
    assert len(agent.contexts) == 2
    selene_context = next(
        context
        for system_prompt, context in zip(agent.system_prompts, agent.contexts, strict=True)
        if "你就是赛蕾妮" in system_prompt
    )
    bran_context = next(
        context
        for system_prompt, context in zip(agent.system_prompts, agent.contexts, strict=True)
        if "你就是布兰" in system_prompt
    )
    assert "布兰" not in selene_context
    assert "赛蕾妮" not in bran_context
    assert "陌生人#1" in selene_context
    assert "陌生人#1" in bran_context


async def test_context_contains_relationship_history_and_every_prior_story(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, _, bran_id = await _seed_two_character_run(runtime_factory)
    async with runtime_factory() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        characters = list(
            await session.scalars(
                select(Character)
                .join(CampaignMembership)
                .where(CampaignMembership.campaign_id == run.campaign_id)
            )
        )
        selene = next(item for item in characters if item.id != bran_id)
        pair = sorted((selene.id, bran_id))
        session.add(
            CharacterAcquaintance(
                character_a_id=pair[0],
                character_b_id=pair[1],
                relationship_history="曾在黑石矿坑并肩逃生，彼此信任。",
            )
        )
        for index in range(1, 7):
            old_campaign = Campaign(
                name=f"旧战役{index}",
                lifecycle_status=CampaignLifecycleStatus.COMPLETED,
            )
            old_session = GameSession(
                title=f"旧故事{index}",
                campaign=old_campaign,
                status=SessionStatus.ENDED,
            )
            old_session.runtime = SessionRuntime(status=RuntimeStatus.ENDED)
            session.add(old_session)
            await session.flush()
            session.add(
                SessionSummary(
                    session_id=old_session.id,
                    character_id=selene.id,
                    audience=SummaryAudience.CHARACTER,
                    content=f"第{index}段完整经历。",
                )
            )
        await session.commit()

    agent = ScriptedCharacterAgent()
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused"),
    )
    await supervisor._execute(run_id)

    selene_context = next(
        context
        for system_prompt, context in zip(agent.system_prompts, agent.contexts, strict=True)
        if "你就是赛蕾妮" in system_prompt
    )
    assert "曾在黑石矿坑并肩逃生，彼此信任。" in selene_context
    assert "布兰" in selene_context
    assert "第1段完整经历。" in selene_context
    assert "第6段完整经历。" in selene_context


def test_character_response_has_a_hard_short_length_limit() -> None:
    with pytest.raises(ValueError):
        CharacterDecision(decision="RESPOND", content="长" * 241)


def test_character_response_allows_natural_personal_pronouns() -> None:
    decision = CharacterDecision(decision="RESPOND", content="我推开门，你们继续前进。")
    assert decision.content == "我推开门，你们继续前进。"


async def test_twelfth_published_ai_message_returns_runtime_to_idle(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        game_session.runtime.consecutive_ai_messages = 11
        await session.commit()
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="赛蕾妮暂且停在这里。"),
            input_tokens=4,
            output_tokens=4,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused-for-fake-agent"),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.IDLE
        assert game_session.runtime.consecutive_ai_messages == 12
        runs = list(
            await session.scalars(select(AgentRun).where(AgentRun.session_id == session_id))
        )
        assert len(runs) == 1


async def test_validator_is_disabled_by_default(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(
                decision="RESPOND",
                content="赛蕾妮进行调查检定。\n\n结果是 18。",
                requires_dm_resolution=True,
                resolution_request="请 DM 裁定调查结果。",
            ),
            input_tokens=5,
            output_tokens=5,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused"),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.WAITING_FOR_DM
        assert game_session.runtime.last_error_code is None
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert messages[-1].content == "赛蕾妮进行调查检定。\n\n结果是 18。"


async def test_rejected_candidate_degrades_to_silence_without_halting(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """A blocked line must not park the campaign in ERROR."""
    run_id, session_id, _ = await _seed_run(runtime_factory)
    agent = FakeCharacterAgent(
        CharacterAgentResult(
            decision=CharacterDecision(decision="RESPOND", content="赛蕾妮的调查检定结果很好。"),
            input_tokens=5,
            output_tokens=5,
        )
    )
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: agent,
        Settings(
            data_dir=tmp_path / "runtime-data",
            deepseek_api_key="unused",
            enable_message_validator=True,
        ),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.IDLE
        assert game_session.runtime.last_error_code == "CHARACTER_MESSAGE_REJECTED"
        assert "规则术语" in (game_session.runtime.last_error_message or "")
        messages = list(
            await session.scalars(select(Message).where(Message.session_id == session_id))
        )
        assert len(messages) == 1
    # The author gets exactly one corrective retry before the run gives up.
    assert len(agent.contexts) == 2
    assert "刚才那句被退回了" in agent.contexts[1]


async def test_rejected_candidate_falls_through_to_the_next_speaker(
    runtime_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    run_id, session_id, bran_id = await _seed_two_character_run(runtime_factory)

    class OneBadOneGoodAgent:
        def __init__(self) -> None:
            self.system_prompts: list[str] = []

        async def respond(self, system_prompt: str, context: str) -> CharacterAgentResult:
            del context
            self.system_prompts.append(system_prompt)
            # Bran wins the priority tier but keeps leaking rules terms.
            content = (
                "布兰报出自己的察觉检定。"
                if "布兰" in system_prompt
                else "赛蕾妮把手按在门框上。"
            )
            return CharacterAgentResult(
                decision=CharacterDecision(decision="RESPOND", content=content, urgency="HIGH"),
                input_tokens=3,
                output_tokens=3,
            )

    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: OneBadOneGoodAgent(),
        Settings(
            data_dir=tmp_path / "runtime-data",
            deepseek_api_key="unused",
            enable_message_validator=True,
        ),
    )

    await supervisor._execute(run_id)

    async with runtime_factory() as session:
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence_no)
            )
        )
        assert len(messages) == 2
        assert messages[-1].sender_character_id != bran_id
        assert messages[-1].content == "赛蕾妮把手按在门框上。"


async def test_agent_failure_persists_invocation_and_runtime_details(
    runtime_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_id, session_id, _ = await _seed_run(runtime_factory)
    supervisor = RuntimeSupervisor(
        runtime_factory,
        lambda _: FailingCharacterAgent(),
        Settings(data_dir=tmp_path / "runtime-data", deepseek_api_key="unused"),
    )

    with caplog.at_level("ERROR"):
        await supervisor._execute(run_id)

    async with runtime_factory() as session:
        game_session = await session.get(GameSession, session_id)
        assert game_session is not None
        await session.refresh(game_session, ["runtime"])
        assert game_session.runtime.status == RuntimeStatus.ERROR
        assert game_session.runtime.last_error_code == "ALL_CHARACTER_AGENTS_FAILED"
        assert "模拟供应商超时" in (game_session.runtime.last_error_message or "")
        invocation = await session.scalar(
            select(LlmInvocation).where(LlmInvocation.agent_run_id == run_id)
        )
        assert invocation is not None
        assert invocation.status == LlmInvocationStatus.FAILED
        assert invocation.error_code == "CHARACTER_AGENT_FAILED"
        assert invocation.error_message == "RuntimeError: 模拟供应商超时"
    assert "Character Agent call failed" in caplog.text


def test_question_to_the_world_forces_dm_resolution() -> None:
    """A question raised at the DM's scene, aimed at nobody in the party."""
    trigger = Message(sender_type=MessageSenderType.DM, kind=MessageKind.IN_GAME)
    assert (
        RuntimeSupervisor._question_needs_the_world(
            "你是用硫磺粉混了什么，还是纯粹靠手势引导？", trigger, ["赛蕾妮"], []
        )
        is True
    )


def test_party_talk_does_not_force_dm_resolution() -> None:
    dm_trigger = Message(sender_type=MessageSenderType.DM, kind=MessageKind.IN_GAME)
    peer_trigger = Message(sender_type=MessageSenderType.CHARACTER, kind=MessageKind.IN_GAME)
    # Names a party member.
    assert (
        RuntimeSupervisor._question_needs_the_world(
            "赛蕾妮，你觉得这条路能走吗？", dm_trigger, ["赛蕾妮"], []
        )
        is False
    )
    # Explicitly addressed to a party member.
    assert (
        RuntimeSupervisor._question_needs_the_world(
            "我们走哪条？", dm_trigger, ["赛蕾妮"], ["c-selene"]
        )
        is False
    )
    # Replying to another character rather than to the DM's scene.
    assert (
        RuntimeSupervisor._question_needs_the_world(
            "那你打算怎么办？", peer_trigger, ["赛蕾妮"], []
        )
        is False
    )
    # Not a question at all.
    assert (
        RuntimeSupervisor._question_needs_the_world(
            "我把火把举高了一些。", dm_trigger, ["赛蕾妮"], []
        )
        is False
    )
