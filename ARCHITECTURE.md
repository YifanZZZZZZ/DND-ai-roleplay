# AI TRPG MVP 技术架构

> 本文是开发入口版架构说明。完整的数据字段、事务步骤和测试清单见 [AI_TRPG_MVP_TECH_ARCHITECTURE.md](./AI_TRPG_MVP_TECH_ARCHITECTURE.md)。产品规则以 [AI_TRPG_Website_MVP_PRD_v0.3.md](./AI_TRPG_Website_MVP_PRD_v0.3.md) 为准。

## 1. 架构目标

架构需要在本地单用户条件下，以尽可能少的基础设施可靠实现：

- 1～6 个独立 Character Agent；
- 严格的角色级认知和私密隔离；
- 一次只发布一个完整消息气泡；
- DM 新消息抢占未发布 AI 输出；
- AI 需要裁决时全局等待 DM；
- OOC 修订和按角色计算的有效消息；
- 跨 Session、跨 Campaign 的角色记忆和成长；
- Campaign 重置、删除与来源记忆清理；
- 页面刷新、多标签页和后端重启后的可理解状态。

## 2. 技术栈选择及原因

### 2.1 技术栈

| 层级 | 技术 | 选择原因 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 适合交互密集的桌面单页应用，开发和构建简单 |
| 路由 | React Router | 页面数量有限，不需要全栈框架路由 |
| 服务端状态 | TanStack Query | 统一处理查询缓存、Mutation 和 SSE 后的数据失效 |
| 样式 | CSS Modules + CSS Variables | 依赖少，组件边界清晰，适合定制跑团界面 |
| API | FastAPI | Python Agent 生态兼容好，支持类型化 API、文件上传和 SSE |
| Agent 调用 | PydanticAI | 支持 Gemini/DeepSeek、Pydantic 结构化输出、校验、重试和 Token 统计 |
| Agent 编排 | LangGraph | 用低层状态图表达一次事件响应，不强迫使用共享群聊模式 |
| 数据库 | SQLite | 本地单用户、单 ACTIVE Campaign 场景足够，备份和迁移简单 |
| ORM | SQLAlchemy 2.x | 事务、约束和关系表达明确，便于后续迁移数据库 |
| 数据库迁移 | Alembic | Schema 变更可追踪，不依赖运行时自动建表 |
| SQLite Driver | aiosqlite | 与异步 LLM 调用和 FastAPI Runtime 配合 |
| Excel | openpyxl | 读取固定模板并生成版本化解析快照 |
| 服务端推送 | SSE | 页面只需要接收状态和消息通知，不需要双向 WebSocket |
| Python 工具 | uv、Ruff、Pyright、pytest | 锁定依赖、统一格式、类型检查和测试 |
| 前端工具 | npm、ESLint、Prettier、Vitest、Playwright | 保持常规前端开发流程和关键 E2E 覆盖 |

### 2.2 不采用的基础设施

MVP 不引入：

- PostgreSQL；
- Redis；
- Celery 或其他任务队列；
- Docker；
- 微服务；
- 多进程 Uvicorn Worker；
- 向量数据库；
- 托管式 Agent Memory；
- AutoGen GroupChat、CrewAI Crew 等共享上下文群聊；
- WebSocket。

原因是当前只有一个本地 DM、一个 ACTIVE Campaign 和最多 6 个角色。单进程 FastAPI、SQLite 和进程内 Task Supervisor 已足够，额外基础设施只会增加状态同步与删除一致性的复杂度。

## 3. 架构原则

1. **SQLite 是业务事实的唯一来源。**
2. **Character Agent 是无状态调用模板。** 角色历史不保存在 PydanticAI Agent 对象内部。
3. **Agent 没有数据库和文件工具。** Agent 不能直接读取或写入业务数据。
4. **所有 Agent 输入经过统一 Context Builder。**
5. **私密隔离在数据库查询阶段完成。** 不把秘密交给模型后再要求它忽略。
6. **未发布候选不是消息。** 不进入历史、摘要、记忆或导出。
7. **消息正文只追加。** OOC 通过 Correction 关系生成有效视图。
8. **发布是唯一不可逆边界。** 发布前必须在事务中再次确认 Run 仍有效。
9. **LangGraph 只处理一条触发消息。** 不持有 Campaign 长期状态。
10. **WAITING_FOR_DM 是业务状态。** DM 回复创建新 Run，不恢复旧 Graph。
11. **数据库事务中不等待 LLM。** 网络调用前读取快照，完成后重新验证发布权。
12. **删除优先于重建。** Campaign 来源记忆先移除，成长档案在安全状态下重新生成。

## 4. 总体结构

```text
┌───────────────────────────────────────────────────────┐
│ React Desktop Web                                     │
│ Character / Campaign / Play / Memory / Debug          │
│ REST Commands + SSE Notifications                     │
└──────────────────────────┬────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────┐
│ FastAPI                                                │
│                                                       │
│ API Routes                                             │
│   └─ Application Services                             │
│        ├─ Character & Sheet                           │
│        ├─ Campaign & Session                          │
│        ├─ Message & OOC                               │
│        ├─ Runtime Supervisor                          │
│        ├─ Context & Memory                            │
│        └─ Export                                      │
│                                                       │
│ Agent Runtime                                          │
│   ├─ PydanticAI Agents                                │
│   ├─ LangGraph Reaction Graph                         │
│   ├─ Speaker Coordinator                              │
│   └─ Candidate Validator                              │
│                                                       │
│ Infrastructure                                         │
│   ├─ SQLAlchemy + SQLite                              │
│   ├─ Local File Storage                               │
│   └─ In-process SSE Event Hub                         │
└───────────────────────────────────────────────────────┘
```

### 4.1 运行形态

- FastAPI 单进程、单 Uvicorn Worker；
- 前端开发期由 Vite 提供，构建后由 FastAPI 同源提供；
- 服务默认只绑定 `127.0.0.1`；
- SQLite 开启 WAL、Foreign Keys 和 Busy Timeout；
- 上传文件、数据库和导出文件放在仓库外；
- 页面刷新不会停止后端正在运行的 Agent Task；
- Python 进程重启后，未完成 Run 标记失败，不自动恢复或重新调用模型。

## 5. Agent Runtime

### 5.1 AgentRun 边界

一条已发布消息对应一次 `AgentRun`，一个 Run 最多发布一条新角色消息。

```text
已发布消息
→ 创建 AgentRun
→ 找出有权看到消息的角色
→ 分别构建角色 Context
→ 并行获得 SILENCE 或完整候选
→ Speaker Coordinator 选择一个候选
→ 发布前校验
→ 原子发布一个气泡，或全员沉默结束
```

发布的新角色消息会创建一个后继 AgentRun，因此可以形成自然连续对话，但每个 Run 都是有界、可取消、可审计的。

### 5.2 Reaction Graph

```text
START
  ↓
prepare_run
  ↓
evaluate_characters
  ├── all silent → finish_idle
  ↓
select_candidate
  ↓
validate_candidate
  ├── retry → regenerate_selected
  ├── failed → finish_failed
  ↓
commit_message
  ↓
finish_published
```

MVP 不使用 LangGraph Persistent Checkpointer。Graph State 只存在于当前进程内；业务状态由 SQLite 的 `agent_runs`、`session_runtimes` 和 `llm_invocations` 保存。

### 5.3 Character Agent 输出

```python
class AgentCandidate:
    decision: Literal["SILENCE", "RESPOND"]
    message: str | None
    response_type: Literal[
        "SPEECH",
        "ACTION",
        "SPEECH_AND_ACTION",
    ] | None
    visibility: Literal["PUBLIC", "DM_ONLY"] | None
    urgency: Literal["NORMAL", "HIGH", "IMMEDIATE"] | None
    addressed_character_ids: list[str]
    requires_dm_resolution: bool
    resolution_request: str | None
```

一次调用只返回一个完整候选。未选择候选只在当前 Run 内存中短暂存在，默认不持久化正文。

### 5.4 Speaker Coordinator

Speaker Coordinator 使用纯 Python 规则：

1. 被最新消息直接点名或提问；
2. `IMMEDIATE`；
3. 更高 urgency；
4. 更久没有实际发言；
5. 完全相同时使用记录了 Seed 的随机选择。

Coordinator 不使用 LLM，不改写候选，也不替角色决定行动。

### 5.5 发布前校验

第一层为确定性规则：

- 结构化输出合法；
- SILENCE 与正文一致；
- visibility 合法；
- 没有机械数值或明显检定申请；
- DM_ONLY、待裁决和单气泡字段一致；
- 正文长度在限制内。

第二层为语义 Validator Agent：

- 是否替 DM 决定 NPC、环境或规则结果；
- 是否把未知内容写成事实；
- 是否泄露不可见信息；
- 是否漏标 DM 裁决；
- 是否违反可观察内容原则。

Validator 只读取被选角色自己的过滤后 Context。它只能通过、要求等待或退回重试，不能替角色重写正文。

### 5.6 WAITING_FOR_DM

若发布消息需要 DM 裁决：

- 消息正常提交；
- Session Runtime 进入 `WAITING_FOR_DM`；
- 保存待裁决消息和请求；
- 当前 AgentRun 正常结束；
- 不创建后继 AgentRun。

DM 发送新 IN_GAME 消息后清除等待状态，并以该消息创建全新的 AgentRun。

### 5.7 DM 抢占

`session_runtimes.generation` 和 `active_agent_run_id` 共同决定发布权。

以下操作使 Generation 加一：

- DM 发送新消息；
- DM Stop；
- OOC 修订；
- Session 结束；
- Campaign 完成、重置或删除。

提交 AI 消息前必须在事务中验证：

```text
run.generation == runtime.generation
AND run.id == runtime.active_agent_run_id
AND session.status == ACTIVE
```

即使供应商请求不能及时取消，迟到结果也无法发布。

## 6. 项目目录结构

```text
DND跑团/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── AI_TRPG_Website_MVP_PRD_v0.3.md
├── AI_TRPG_MVP_TECH_ARCHITECTURE.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
├── alembic.ini
│
├── backend/
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   ├── errors.py
│   │   │   └── ids.py
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   ├── dependencies.py
│   │   │   ├── schemas/
│   │   │   └── routes/
│   │   ├── domain/
│   │   │   ├── enums.py
│   │   │   ├── errors.py
│   │   │   ├── value_objects.py
│   │   │   └── policies/
│   │   ├── services/
│   │   │   ├── character_service.py
│   │   │   ├── campaign_service.py
│   │   │   ├── session_service.py
│   │   │   ├── message_service.py
│   │   │   ├── ooc_service.py
│   │   │   ├── memory_service.py
│   │   │   └── export_service.py
│   │   ├── runtime/
│   │   │   ├── supervisor.py
│   │   │   ├── graph.py
│   │   │   ├── graph_state.py
│   │   │   ├── coordinator.py
│   │   │   ├── publisher.py
│   │   │   └── nodes/
│   │   ├── agents/
│   │   │   ├── schemas.py
│   │   │   ├── model_factory.py
│   │   │   ├── character_agent.py
│   │   │   ├── validator_agent.py
│   │   │   ├── summary_agent.py
│   │   │   ├── memory_agent.py
│   │   │   ├── profile_agent.py
│   │   │   └── prompts/
│   │   ├── context/
│   │   │   ├── builder.py
│   │   │   ├── message_projection.py
│   │   │   ├── memory_selector.py
│   │   │   ├── token_budget.py
│   │   │   └── ability_view.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── engine.py
│   │   │   ├── unit_of_work.py
│   │   │   ├── models/
│   │   │   └── repositories/
│   │   ├── files/
│   │   │   ├── storage.py
│   │   │   ├── sheet_parser.py
│   │   │   ├── archive_builder.py
│   │   │   └── safety.py
│   │   └── events/
│   │       ├── hub.py
│   │       └── schemas.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── privacy/
│       ├── concurrency/
│       └── fixtures/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── app/
│       ├── api/
│       ├── pages/
│       ├── features/
│       │   ├── characters/
│       │   ├── characterSheets/
│       │   ├── campaigns/
│       │   ├── sessions/
│       │   ├── chat/
│       │   ├── hp/
│       │   ├── ooc/
│       │   ├── memories/
│       │   └── runtime/
│       ├── components/
│       ├── hooks/
│       └── styles/
│
├── scripts/
└── docs/
    └── adr/
```

目录依赖规则：

- `domain/` 不导入 FastAPI、SQLAlchemy、PydanticAI 或 LangGraph；
- `api/` 不直接写 SQLAlchemy Query；
- `agents/` 不直接访问 Repository；
- `runtime/` 通过 Service 或 Repository 接口读写；
- ORM Model、API Schema 和 Agent Schema 是不同类型；
- 前端业务代码按 `features/` 组织。

## 7. 核心模块说明

### 7.1 Character

负责全局角色、Roleplay Prompt、头像、Max HP、当前角色卡版本、长期记忆、成长档案和角色导出。

不负责当前 Campaign HP、Session 消息或 Agent 调度。

### 7.2 Character Sheet

负责固定 Excel 模板校验、解析预览和版本激活。解析结果保存为整体 JSON Snapshot；解析失败的新版本不能替换旧有效版本。

### 7.3 Campaign

负责生命周期、归档、Membership、唯一 ACTIVE Campaign、中途加入、完成、重新开启、重置和永久删除。

Campaign 状态变化通过显式 Command Service 完成，不允许通用 PATCH 任意写状态。

### 7.4 Session

负责 Session 生命周期、HP Snapshot、Runtime、连续 AI 消息数以及结束后的 Summary/Memory 任务状态。

### 7.5 Message 与 OOC

负责消息、可见范围、Recipient Snapshot、不可修改正文、Correction 关系以及 UI、Agent、Summary 和 Export 使用的统一有效消息规则。

### 7.6 Runtime

负责 AgentRun、进程内 Task Supervisor、LangGraph、并行角色判断、发言排序、校验、有限重试、原子发布、WAITING_FOR_DM、Stop 和错误恢复。

### 7.7 Context 与 Memory

负责角色级可见消息查询、OOC 修订投影、Rolling Summary、旧 Campaign Summary、长期记忆选择、Token Budget、定性健康状态和成长档案重建。

### 7.8 Export

负责 Campaign ZIP 和 Character Export。导出必须使用同一个 Effective Message Projection，不得单独实现 OOC 规则。

### 7.9 Debug

负责显示 Run ID、触发事件、调用角色、SILENCE/RESPOND、排序、模型、Token、耗时、重试和错误码。

默认不保存完整 Prompt、私密 Context、Chain of Thought 或未发布候选正文。

## 8. 数据模型设计

### 8.1 实体关系

```text
characters
  ├── character_sheet_versions
  ├── character_profiles
  ├── character_memories
  └── campaign_memberships ── campaigns
                                └── sessions
                                     ├── session_character_states
                                     ├── session_runtimes
                                     ├── messages
                                     │    ├── message_recipients
                                     │    └── message_corrections
                                     ├── character_session_summaries
                                     ├── dm_session_summaries
                                     └── agent_runs
                                          └── llm_invocations
```

主键统一使用 UUID，内部时间统一保存 UTC。

### 8.2 核心表

#### `characters`

主要字段：

- `id`；
- `name`；
- `roleplay_prompt`；
- `avatar_path`；
- `max_hp`；
- `active_sheet_version_id`；
- `revision`；
- `created_at`、`updated_at`。

`revision` 用于多标签页编辑时的乐观并发检查。

#### `character_sheet_versions`

保存：

- 原文件展示名和安全存储路径；
- SHA-256；
- `PENDING/VALID/FAILED`；
- Parser Version；
- Parsed JSON Snapshot；
- 脱敏错误码。

只有 VALID Version 可以成为角色当前 Sheet。

#### `character_profiles`

保存成长档案和状态：

```text
READY / NEEDS_REBUILD / GENERATING / FAILED
```

Campaign 重置或删除时先清空受影响 Profile 并设为 NEEDS_REBUILD。Profile 不是 READY 时不得进入 Agent Context。

#### `campaigns`

主要字段：

- 名称与描述；
- `PREPARATION/ACTIVE/COMPLETED`；
- `archived_at`；
- Revision 和内部时间。

SQLite Partial Unique Index 保证全站只有一个 ACTIVE Campaign：

```sql
CREATE UNIQUE INDEX ux_campaign_single_active
ON campaigns(lifecycle_status)
WHERE lifecycle_status = 'ACTIVE';
```

#### `campaign_memberships`

联合主键为 `campaign_id + character_id`，并保存加入时间、加入 Session 和加入消息边界。

实际认知边界不依赖时间推导，而依赖每条消息的 Recipient Snapshot。

#### `sessions`

保存 Campaign、标题、`ACTIVE/ENDED`、下一个 Message Sequence 和内部时间。Partial Unique Index 保证一个 Campaign 最多一个 ACTIVE Session。

#### `session_character_states`

联合主键为 `session_id + character_id`，保存：

- `current_hp`；
- `max_hp_snapshot`；
- `updated_at`。

Agent 不读取这些整数，只读取 Health Status Policy 输出的定性状态。

#### `session_runtimes`

每个 Session 一行：

- Runtime Status；
- Generation；
- Active AgentRun；
- Last Trigger Message；
- Waiting Message 和 Resolution Request；
- Consecutive AI Messages；
- Updated At。

Runtime Status：

```text
IDLE
AGENTS_EVALUATING
VALIDATING_MESSAGE
WAITING_FOR_DM
ERROR
ENDED
```

#### `messages`

主要字段：

- Session；
- Sequence Number；
- Sender Type 和 Character Sender；
- `IN_GAME/OOC/SYSTEM`；
- `PUBLIC/PRIVATE/DM_ONLY`；
- 不可原地修改的 Content；
- Client Request ID；
- Origin AgentRun；
- Created At。

约束：

- `UNIQUE(session_id, sequence_no)`；
- `client_request_id` 防止标签页或网络重复提交；
- AI 候选只有成功发布后才创建 Message。

#### `message_recipients`

联合主键为 `message_id + character_id`。角色能感知该消息时才存在一行。

- PUBLIC 写入发送时全部成员；
- PRIVATE 只写入 DM 选择的角色；
- DM_ONLY 至少写入发送角色自己；
- 后加入角色不会被补进旧 Recipient。

Character Context 和 Summary 必须通过 Recipient Join 查询，不能先加载全部消息再过滤。

#### `message_corrections`

保存：

- Target Message；
- OOC Message；
- `LATEST_REPLACE/FACTUAL_CORRECTION/INVALIDATE`；
- Replacement Message；
- `OMIT/REPLACE` Export Policy；
- `PENDING/APPLIED/FAILED`。

OOC 可以私密，因此 Correction 必须按角色计算：只有位于 OOC Recipient Snapshot 中的角色应用该纠正。

统一投影接口：

```python
EffectiveMessageProjection.for_dm(session_id)
EffectiveMessageProjection.for_character(session_id, character_id)
EffectiveMessageProjection.for_export(campaign_id)
```

#### `character_session_summaries`

按 Session、Character 和 `ROLLING/FINAL` 唯一，保存内容、状态、Revision 和 `DM/SYSTEM` 更新来源。

#### `dm_session_summaries`

每个 Session 一行，只供 DM 和 Export 使用。任何 Character Context Repository 都不得引用该表。

#### `character_memories`

保存 Character、Content、`CAMPAIGN/DM_MANUAL` 来源、Campaign/Session 来源和 Pinned。

不保存数值重要度、好感度、情绪或关系值。

#### `agent_runs`

保存：

- Campaign、Session 和 Trigger Message；
- Generation；
- `PENDING/RUNNING/COMPLETED/CANCELLED/FAILED`；
- Stop Reason；
- Selected Character；
- Published Message；
- Eligible/Response Count；
- Random Seed；
- Started/Finished At。

#### `llm_invocations`

统一记录 Character、Validator、Summary、Memory 和 Profile 调用的：

- Provider 和 Model；
- Prompt Version；
- Status；
- Decision；
- Input/Output Token；
- Duration；
- Retry Count；
- Error Code。

默认不保存完整 Prompt、Context 或未发布 Candidate 正文。

## 9. 关键事务

### 9.1 DM 发送消息

一个事务内：

1. 校验 Session 可写；
2. 使用 Client Request ID 去重；
3. Generation 加一；
4. 旧 Active Run 标记取消；
5. 写入 Message 和 Recipient Snapshot；
6. 清除 WAITING_FOR_DM；
7. IN_GAME 时连续 AI 计数归零；
8. 创建新 AgentRun；
9. 提交后启动 Runtime Task 并发送 SSE 通知。

### 9.2 AI 原子发布

一个事务内：

1. 比较 Generation、Active Run 和 Session Status；
2. 检查 12 条上限；
3. 写入最终 Message 和 Recipients；
4. 完成当前 Run；
5. 更新连续 AI 数；
6. 需要裁决则进入 WAITING_FOR_DM；
7. 达到上限则进入 IDLE；
8. 否则创建后继 AgentRun。

### 9.3 Stop

- Generation 加一；
- Active Run 标记 `CANCELLED/DM_STOP`；
- Runtime 回到 IDLE；
- 已发布消息保留；
- 提交后尽力取消 asyncio Task。

### 9.4 OOC

- OOC 和 Correction 先以 PENDING 提交；
- 最新 AI 消息只调用原角色重新处理；
- 最新 DM 消息使用 DM 填写的正确版本；
- Replacement 通过正常校验后提交；
- 原角色选择 SILENCE 时使用 INVALIDATE；
- 较早事实 Correction 从当前时点向后生效；
- Correction 失败后错误原文不能重新进入已收到 OOC 角色的 Context。

### 9.5 Session 结束

先在事务内结束 Session、取消 Run、保存 HP 并创建 PENDING Summary/Memory 状态；事务外再调用 LLM。单项失败不回滚 Session 结束。

### 9.6 Campaign 重置或删除

事务内先删除 Campaign 来源 Memory、清空并禁用受影响 Profile，再删除 Session/Campaign 数据；事务提交后根据剩余 Memory 重建 Profile。

## 10. Context 与 Memory

### 10.1 唯一入口

```python
ContextBuilder.build_for_character(
    character_id=...,
    session_id=...,
    trigger_message_id=...,
    purpose=...,
)
```

Character、Summary 和 Memory Agent 都必须通过该入口获取角色数据。

### 10.2 构建顺序

```text
Roleplay Prompt
→ 当前有效 Sheet Snapshot
→ READY Development Profile
→ 角色自己的旧 Campaign Summary
→ 角色自己的 Long-Term Memory
→ 当前 Rolling Summary
→ 角色 Recipient 可见的 Effective Messages
→ 定性 Health View
→ Trigger Message
→ Token Budget 裁剪
```

### 10.3 Memory Selector

MVP 不使用向量数据库。定义可替换接口，初版按以下顺序选择：

1. Pinned Memory；
2. 当前 Campaign Memory；
3. 最近未固定 Memory；
4. 在 Token Budget 内截断。

未来可以替换为 Embedding 或混合检索，而不改变 Character Agent 接口。

### 10.4 Health View

准确 HP 只存在于数据库和 DM UI。Agent 只读取：

```text
HEALTHY
LIGHTLY_HURT
HEAVILY_HURT
CRITICAL
UNCONSCIOUS
```

## 11. API 与事件

### 11.1 API 风格

- `/api/v1` 前缀；
- 查询使用 GET；
- 普通编辑使用 PATCH；
- 生命周期和破坏性操作使用显式 Command Endpoint；
- 消息请求带 Client Request ID；
- 错误返回稳定 Error Code；
- 不返回供应商原始错误或密钥。

示例：

```text
POST   /api/v1/characters
PATCH  /api/v1/characters/{id}
POST   /api/v1/campaigns/{id}:activate
POST   /api/v1/campaigns/{id}:complete
POST   /api/v1/campaigns/{id}:reset
DELETE /api/v1/campaigns/{id}
POST   /api/v1/campaigns/{id}/sessions
POST   /api/v1/sessions/{id}/messages
POST   /api/v1/messages/{id}/corrections
POST   /api/v1/sessions/{id}/runtime:stop
POST   /api/v1/sessions/{id}/runtime:retry-latest
GET    /api/v1/sessions/{id}/events
```

### 11.2 SSE

SSE 只推送数据变化通知：

```text
message.created
message.effective_view.changed
runtime.changed
hp.changed
summary.changed
memory.changed
campaign.changed
```

Payload 只带必要 ID 和 Revision，不广播私密正文。前端收到事件后让 TanStack Query 失效并重新读取服务器状态。

## 12. 本地文件和配置

```text
AI_TRPG_DATA/
├── app-data.sqlite3
├── uploads/
│   ├── avatars/
│   └── character-sheets/
├── temp/
└── exports/
```

规则：

- 运行数据目录由 `AI_TRPG_DATA_DIR` 配置；
- 文件使用 UUID 名称；
- 原文件名只用于展示；
- 上传先进入 Temp，验证后原子移动；
- 校验扩展名、MIME、文件签名、大小和 SHA-256；
- API Key 只通过环境变量读取；
- 数据库、上传文件、Export 和 `.env` 不提交 Git。

## 13. 代码规范

### 13.1 Python

- 公共函数必须有参数和返回类型；
- 使用 Ruff 格式化与 Lint；
- 使用 Pyright Strict 或逐模块收紧；
- 核心业务数据使用 dataclass、TypedDict 或 Pydantic Model，不传裸 Dict；
- Route 不写业务判断或 SQL；
- ORM Model 不调用 LLM；
- 生命周期使用 Enum，不使用多个 Boolean；
- 所有写入通过 Unit of Work；
- 数据库事务中不等待网络；
- 时间统一使用带时区 UTC；
- Prompt 使用独立版本文件；
- 外部异常转换为稳定应用错误；
- 不静默吞掉顶层异常。

### 13.2 TypeScript / React

- 启用 `strict: true`；
- 禁止无理由使用 `any`；
- API DTO 从 FastAPI OpenAPI 生成；
- 页面负责组合，业务组件归属具体 Feature；
- API URL 和 Query Key 集中管理；
- Mutation 统一处理 Error Code；
- 不在前端重复实现 Campaign、OOC 和权限规则；
- Runtime 和 Message 以服务器状态为准；
- 消息、HP 和生命周期命令不做可能误导的乐观提交。

### 13.3 数据库

- 表和字段使用 `snake_case`；
- 每个 Schema 变更必须有 Alembic Migration；
- 正式启动不调用 `create_all()`；
- 开启 SQLite Foreign Keys；
- 明确 Cascade 或 Restrict；
- Message Recipient 使用关系表，不存 JSON 数组；
- JSON 只保存 Character Sheet Snapshot 等整体读取结构；
- 永久删除通过 Service 显式执行。

### 13.4 日志与隐私

可以记录：

- ID、状态、Provider、Model；
- Token、耗时、重试；
- 脱敏 Error Code。

默认禁止记录：

- API Key；
- 完整 Prompt 和 Context；
- 私密消息正文；
- 完整角色记忆；
- 未发布候选正文；
- Chain of Thought；
- Excel 原始内容。

### 13.5 Prompt

- 文件名包含版本；
- 变更记录 Prompt Version；
- 明确区分系统规则、角色资料、可见事实和 Trigger；
- 角色资料不能覆盖系统规则；
- 不要求模型输出隐藏推理；
- 测试结构化决定和最终正文规则，不测试思维过程。

## 14. 测试要求

最高优先级是隐私和并发测试：

- 新角色看不到加入前消息；
- PRIVATE 和 DM_ONLY 不泄露；
- DM Summary 不进入 Character Context；
- OOC 无效版本不再进入对应角色 Context；
- Campaign 删除后 Memory/Profile 不残留；
- DM 新消息后旧 Run 不能发布；
- Stop 后迟到响应不能发布；
- 多标签页重复请求只创建一条消息；
- 两个候选同时完成只发布一个；
- 不发布第 13 条连续 AI 消息；
- Session 结束与 AI 提交竞争时，AI 提交失败。

Agent Contract 测试使用假的 Model Adapter 或 PydanticAI TestModel，CI 不调用真实供应商。

## 15. MVP 演进边界

以下能力可以以后替换而不改变 Domain 规则：

- SQLite → PostgreSQL；
- 进程内 Runtime Supervisor → 持久化任务队列；
- Pinned/Recent Memory Selector → Embedding/Hybrid Search；
- 单一模型 → 按 Character/Validator/Summary 分配不同模型；
- 单进程 SSE Hub → Redis Pub/Sub；
- 固定 6 人产品限制 → 更高可配置上限。

在 MVP 阶段不为这些未来能力提前引入基础设施。

