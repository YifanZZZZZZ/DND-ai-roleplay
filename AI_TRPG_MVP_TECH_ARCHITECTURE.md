# AI TRPG 网站 MVP 轻量级技术架构

> 版本：v0.1  
> 日期：2026-08-18  
> 对应产品文档：`AI_TRPG_Website_MVP_PRD_v0.3.md`

---

## 0. 文档目的

本文把已经确认的产品需求落实为一套可以直接开始开发的轻量级技术架构，重点解决：

- 1～6 个长期存在的 Character Agent 如何保持认知独立；
- DM 消息如何抢占未发布 AI 输出；
- 如何一次只发布一个完整消息气泡；
- 如何在需要裁决时停止所有 AI；
- 如何可靠处理 OOC 修订和有效消息视图；
- 角色如何跨 Session、跨 Campaign 保留自己的记忆和成长；
- Campaign 重置或永久删除后，如何保证相关 AI 记忆真正消失；
- 如何在本地单用户场景下保持实现简单、可测试、可演进。

本文不改变 PRD。若本文与 PRD 发生冲突，以 PRD 为准。

---

# 1. 架构结论

## 1.1 推荐技术栈

| 层级 | 推荐技术 | 用途 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 桌面网页界面 |
| 前端路由 | React Router | 页面路由 |
| 服务端状态 | TanStack Query | API 缓存、刷新和失效 |
| 样式 | CSS Modules + CSS Variables | 保持依赖少、样式边界清晰 |
| 后端 API | FastAPI | REST API、文件上传和 SSE |
| Agent 调用 | PydanticAI | 模型适配、结构化输出、校验和调用统计 |
| Agent 编排 | LangGraph | 单个事件的有界响应状态图 |
| 数据库 | SQLite | 本地单用户业务数据 |
| ORM | SQLAlchemy 2.x | 显式数据模型与事务 |
| 数据库迁移 | Alembic | 版本化 Schema 迁移 |
| SQLite 异步驱动 | aiosqlite | 配合异步 Agent Runtime |
| Excel 解析 | openpyxl | 固定角色卡模板解析 |
| Python 管理 | pyproject.toml + uv.lock | 依赖和环境锁定 |
| 前端依赖管理 | npm + package-lock.json | 降低额外工具要求 |
| 后端测试 | pytest + pytest-asyncio + httpx | 单元与 API 集成测试 |
| 前端/E2E 测试 | Vitest + Playwright | 组件与关键流程测试 |
| Python 规范 | Ruff + Pyright | 格式、静态检查和类型检查 |
| TypeScript 规范 | ESLint + Prettier + strict mode | 前端一致性与类型安全 |

## 1.2 MVP 不引入的基础设施

MVP 不需要：

- PostgreSQL；
- Redis；
- Celery、RQ 或其他分布式任务队列；
- Docker；
- Kubernetes；
- 向量数据库；
- 登录与权限系统；
- WebSocket；
- 微服务；
- 多进程 Uvicorn Worker；
- 托管式 Agent Memory；
- CrewAI、AutoGen GroupChat 或其他共享上下文群聊运行时。

采用单个 Python 后端进程即可支持一个 DM、一个 ACTIVE Campaign 和最多 6 个角色。

## 1.3 最高级架构原则

1. **SQLite 是业务事实的唯一来源。**
2. **Character Agent 是无状态调用模板，不在框架对象内部保存长期历史。**
3. **Agent 永远不能直接查询数据库，也没有任何数据写入工具。**
4. **所有 Agent 输入必须先经过角色级 Context Builder。**
5. **私密过滤必须发生在查询与摘要生成阶段，而不是依靠 Prompt 提醒。**
6. **未发布候选不是消息，不进入历史、摘要、记忆或导出。**
7. **Message 正文只追加，不原地编辑；OOC 使用关系表生成有效视图。**
8. **发布消息是唯一不可逆边界，发布前必须再次检查 Run 是否仍有效。**
9. **LangGraph 只执行有界响应流程，不持有整个 Campaign 或长期角色记忆。**
10. **WAITING_FOR_DM 是数据库中的 Session Runtime 状态，不恢复旧 Agent Run。**

---

# 2. 系统总体结构

```text
┌─────────────────────────────────────────────────────────────┐
│ React Desktop Web                                           │
│                                                             │
│ Character / Campaign / Play / Memory / Debug                │
│ REST commands + SSE state notifications                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│ FastAPI Application                                         │
│                                                             │
│ API Routes                                                   │
│   └─ Application Services / Command Handlers                │
│        ├─ Character & Sheet Service                         │
│        ├─ Campaign & Session Service                        │
│        ├─ Message & OOC Service                             │
│        ├─ Runtime Supervisor                                │
│        ├─ Memory & Profile Service                          │
│        └─ Export Service                                    │
│                                                             │
│ Agent Runtime                                                │
│   ├─ Context Builder                                         │
│   ├─ PydanticAI Character / Validator / Summary Agents      │
│   └─ LangGraph Reaction Graph                               │
│                                                             │
│ Infrastructure                                               │
│   ├─ SQLAlchemy Repositories                                │
│   ├─ SQLite                                                  │
│   ├─ Local File Storage                                     │
│   └─ In-process SSE Event Hub                               │
└─────────────────────────────────────────────────────────────┘
```

## 2.1 运行与部署形态

- 前端编译为静态文件，由 FastAPI 同源提供；开发期由 Vite Dev Server 提供。
- 后端只绑定 `127.0.0.1`，不默认暴露到局域网或公网。
- Uvicorn 只运行一个 Worker。
- SQLite 开启 WAL、Foreign Keys 和 Busy Timeout。
- 上传文件和数据库放在项目目录之外的可配置数据目录。
- 浏览器刷新、关闭或多标签页不会终止后端正在执行的 Task。
- 整个 Python 进程关闭后，未完成 Run 不恢复现场，启动时统一标记为失败。

---

# 3. Agent Runtime 设计

## 3.1 一次 Agent Run 的边界

一个 `AgentRun` 只处理一条已经发布的触发消息，并且最多发布一条新的角色消息。

```text
一条已发布消息
→ 创建 AgentRun
→ 找出有权看到该消息的角色
→ 为每个角色独立构建上下文
→ 并行获得 SILENCE 或候选消息
→ 选择一个候选
→ 校验
→ 原子发布一个气泡，或全员沉默结束
```

若发布了角色消息，该消息会成为一个新的事件，再创建一个新的 AgentRun。这样自然形成连续对话，但每个 Run 都短小、可取消、可审计。

## 3.2 为什么不让一个 Graph 运行整个对话

不使用长期运行的 Campaign Graph，原因是：

- PRD 明确不恢复旧 Run；
- DM 的任意新消息都应让旧候选立即失效；
- WAITING_FOR_DM 后应由新 DM 消息启动新的判断；
- Campaign 和角色记忆必须能够独立导出、重置和删除；
- 长期 Graph Checkpoint 会形成第二套状态与记忆来源；
- 发生错误时，重试最新事件比恢复到某个内部 Node 更容易理解。

MVP 中 LangGraph 不使用持久化 Checkpointer。业务运行状态和调试数据由 SQLite 中的 `agent_runs`、`session_runtimes` 和 `llm_invocations` 保存。

## 3.3 Reaction Graph

```text
START
  │
  ▼
prepare_run
  │  加载 Trigger、Run Generation、Eligible Character IDs
  ▼
evaluate_characters
  │  独立构建 Context，并行调用 Character Agents
  ├────────────── all silent ──────────────► finish_idle
  ▼
select_candidate
  │  规则排序，不使用 LLM 决定角色意志
  ▼
validate_candidate
  ├──────── reject, retry available ───────► regenerate_selected
  ├──────── reject, no retry ──────────────► finish_failed
  ▼
commit_message
  │  比较 Generation，事务内发布
  ▼
finish_published
```

Graph State 只在内存中存在，包含：

- `agent_run_id`；
- `session_id`；
- `trigger_message_id`；
- `generation`；
- eligible Character IDs；
- 本次候选；
- 最终选择和校验结果。

Graph State 不包含：

- 其他角色的长期记忆集合；
- DM 总览摘要；
- 全 Campaign 原始数据库快照；
- 模型隐藏推理；
- 可跨 Run 复用的内部思维状态。

## 3.4 Character Agent

PydanticAI `CharacterAgent` 使用统一的调用模板，每次传入不同角色依赖：

```python
class CharacterAgentDeps:
    character_id: str
    roleplay_prompt: str
    development_profile: str | None
    ability_view: str
    health_view: str
    memory_view: str
    campaign_context: str
    trigger_message: str
```

结构化输出：

```python
class AgentCandidate:
    decision: Literal["SILENCE", "RESPOND"]
    message: str | None
    response_type: Literal["SPEECH", "ACTION", "SPEECH_AND_ACTION"] | None
    visibility: Literal["PUBLIC", "DM_ONLY"] | None
    urgency: Literal["NORMAL", "HIGH", "IMMEDIATE"] | None
    addressed_character_ids: list[str]
    requires_dm_resolution: bool
    resolution_request: str | None
```

规则：

- 一次调用只返回一个完整候选气泡；
- `SILENCE` 时正文必须为空；
- `appraisal` 在生成正文前检查角色自己最近 3～5 次回复的动作结构、收尾方式、已提问题及已有答案；
- `intent` 允许行动、提问、关系回应和纯情绪表达，不要求每次回复都推动剧情或带有实际诉求；
- 动作与神态是可选表达层素材；一句台词已经成立时不强制附加动作，近期使用过的同构动作不得换词复刻；
- 向同一对象提问前检查相同信息目标；对方已回答不知道、不记得、没见过、无法确认或拒绝时，不再换词追问，除非出现新证据或情况实质变化；
- Agent 没有数据库、HP、文件或资源状态写入工具；
- Agent 不调用其他 Character Agent；
- Agent 不决定下一位发言者；
- 未选择候选只保留运行元数据，不持久化正文。

## 3.5 Speaker Coordinator

Speaker Coordinator 是纯 Python 策略，不使用额外 LLM：

1. 被最新消息直接点名或提问；
2. `IMMEDIATE`；
3. 更高 urgency；
4. 距离上次实际发言更久；
5. 完全相同时使用有记录种子的随机选择。

Coordinator 只选择候选，不重写候选内容。

每发布一个候选，其他旧候选立即失效；所有角色基于新消息重新判断，因此不会同时发布互相矛盾的行动。

## 3.6 发布前校验

采用两层校验：

### 第一层：确定性规则

- Pydantic Schema 完整性；
- `SILENCE` 与正文一致性；
- visibility 与接收者合法性；
- 禁止机械数值和明显检定申请表达；
- `DM_ONLY` 只能由角色发给 DM；
- `requires_dm_resolution` 与 `resolution_request` 一致；
- 消息长度上限；
- 单气泡约束。

### 第二层：语义 Validator Agent

只在候选通过第一层后调用，用于判断：

- 是否替 DM 决定了 NPC、环境或行动结果；
- 是否把未知内容写成确定事实；
- 是否泄露角色无权知道的信息；
- 是否漏标 DM 裁决；
- 是否违反可观察内容原则。

Validator 只获得：

- 被选角色自己的过滤后 Context；
- 被选候选；
- 校验规则。

Validator 不读取其他角色秘密。它只能返回 `PASS`、`REQUIRE_DM` 或 `RETRY`，不能代替角色改写正文。

## 3.7 WAITING_FOR_DM

若最终发布消息需要 DM 裁决：

1. 消息正常提交；
2. `session_runtimes.status` 设为 `WAITING_FOR_DM`；
3. 保存 `waiting_message_id` 和 `waiting_request`；
4. 当前 AgentRun 以 `WAITING_FOR_DM` 原因正常结束；
5. 不创建下一次自动 AgentRun。

DM 随后发送任意 IN_GAME 消息时：

- 清除等待信息；
- DM 消息成为新 Trigger；
- 创建全新的 AgentRun；
- 不恢复旧 Graph Node 或旧候选。

## 3.8 DM 抢占和停止

`session_runtimes.generation` 是正确性保护的核心。

每当发生以下事件时，Generation 加一：

- DM 发送新消息；
- DM 点击停止 AI；
- OOC 修订开始；
- Session 结束；
- Campaign 完成、重置或删除。

AgentRun 创建时保存当时的 Generation。提交消息前必须在事务中验证：

```text
run.generation == session_runtime.generation
AND run.id == session_runtime.active_agent_run_id
AND session.status == ACTIVE
```

任何一项不成立，候选直接丢弃。即使供应商 API 无法及时取消请求，也不会发生旧候选发布。

---

# 4. 核心板块划分

## 4.1 Character 模块

负责：

- 全局角色 CRUD；
- Roleplay Prompt；
- 头像；
- 最大 HP；
- 当前 Character Sheet Version；
- Character Development Profile；
- 长期记忆查看、编辑、删除和固定；
- 角色导出。

不负责：

- 当前 Campaign HP；
- Session 消息；
- Agent 调度。

## 4.2 Character Sheet 模块

负责：

- 固定 Excel 模板校验；
- 上传临时文件；
- 解析选中能力、法术、种族、职业、背景、装备与说明；
- 解析预览；
- 成功确认后激活新 Version；
- 解析失败时保留旧 Version。

解析结果保存为版本化 JSON 快照，不将大量能力字段拆成关系表。

## 4.3 Campaign 模块

负责：

- PREPARATION、ACTIVE、COMPLETED 状态；
- 归档状态；
- 1～6 名 Membership；
- 唯一 ACTIVE Campaign；
- 中途加入；
- 完成、重新开启、重置和永久删除；
- Campaign 导出。

Campaign 生命周期变化必须通过明确 Command，不允许使用通用 PATCH 任意写状态。

## 4.4 Session 模块

负责：

- 创建和结束 Session；
- 每个 Campaign 唯一 ACTIVE Session；
- Session Character HP 快照；
- Runtime Status；
- 连续 AI 消息计数；
- Session 结束后的摘要与记忆生成状态。

## 4.5 Message 模块

负责：

- DM IN_GAME、DM OOC 和角色消息；
- PUBLIC、PRIVATE、DM_ONLY；
- 发送时的角色可见快照；
- 追加式消息序列；
- OOC Correction 关系；
- Agent Context、UI 和导出使用的有效消息视图。

## 4.6 Runtime 模块

负责：

- Runtime Supervisor；
- AgentRun 创建和取消；
- LangGraph 执行；
- 并行角色调用；
- Speaker Coordinator；
- 校验和有限重试；
- 原子发布；
- WAITING_FOR_DM、IDLE、ERROR；
- 12 条自动消息上限；
- Token、耗时和错误元数据。

## 4.7 Context 与 Memory 模块

负责：

- 角色级可见消息查询；
- OOC 有效事实处理；
- 最近消息与 Rolling Summary 组合；
- 旧 Campaign 角色独立摘要；
- 长期记忆选择；
- 定性健康状态；
- Token Budget；
- Session 结束摘要；
- 长期记忆提取；
- Character Development Profile 更新与重建。

## 4.8 Export 模块

负责：

- 生成 Campaign ZIP；
- 生成 Character 导出；
- 使用与 UI 相同的 Effective Message Projection；
- 排除无效消息、OOC 指令、头像和原始 Excel；
- 严格限制跨 Campaign 和记忆泄露。

## 4.9 Debug 模块

负责：

- AgentRun 列表和状态；
- 每个角色 SILENCE/RESPOND 元数据；
- 排序结果；
- 模型、Token、耗时和重试；
- 校验结果；
- 错误代码。

默认不保存：

- Prompt 完整正文；
- 私密上下文快照；
- 模型 Chain of Thought；
- 未选候选正文。

---

# 5. 项目目录结构

```text
ai-trpg/
├── README.md
├── AI_TRPG_Website_MVP_PRD_v0.3.md
├── AI_TRPG_MVP_TECH_ARCHITECTURE.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── package.json                    # 根级便捷脚本，可选
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
│   │   │
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   ├── dependencies.py
│   │   │   ├── schemas/
│   │   │   │   ├── characters.py
│   │   │   │   ├── campaigns.py
│   │   │   │   ├── sessions.py
│   │   │   │   ├── messages.py
│   │   │   │   └── runtime.py
│   │   │   └── routes/
│   │   │       ├── characters.py
│   │   │       ├── character_sheets.py
│   │   │       ├── campaigns.py
│   │   │       ├── sessions.py
│   │   │       ├── messages.py
│   │   │       ├── runtime.py
│   │   │       ├── memories.py
│   │   │       ├── exports.py
│   │   │       └── debug.py
│   │   │
│   │   ├── domain/
│   │   │   ├── enums.py
│   │   │   ├── errors.py
│   │   │   ├── value_objects.py
│   │   │   └── policies/
│   │   │       ├── campaign_policy.py
│   │   │       ├── message_visibility.py
│   │   │       ├── health_status.py
│   │   │       ├── speaker_priority.py
│   │   │       └── candidate_validation.py
│   │   │
│   │   ├── services/
│   │   │   ├── character_service.py
│   │   │   ├── sheet_service.py
│   │   │   ├── campaign_service.py
│   │   │   ├── session_service.py
│   │   │   ├── message_service.py
│   │   │   ├── ooc_service.py
│   │   │   ├── memory_service.py
│   │   │   ├── profile_service.py
│   │   │   └── export_service.py
│   │   │
│   │   ├── runtime/
│   │   │   ├── supervisor.py
│   │   │   ├── graph.py
│   │   │   ├── graph_state.py
│   │   │   ├── coordinator.py
│   │   │   ├── publisher.py
│   │   │   └── nodes/
│   │   │       ├── prepare.py
│   │   │       ├── evaluate.py
│   │   │       ├── select.py
│   │   │       ├── validate.py
│   │   │       └── commit.py
│   │   │
│   │   ├── agents/
│   │   │   ├── schemas.py
│   │   │   ├── model_factory.py
│   │   │   ├── character_agent.py
│   │   │   ├── validator_agent.py
│   │   │   ├── summary_agent.py
│   │   │   ├── memory_agent.py
│   │   │   ├── profile_agent.py
│   │   │   └── prompts/
│   │   │       ├── character_system_v1.md
│   │   │       ├── validator_system_v1.md
│   │   │       ├── summary_system_v1.md
│   │   │       ├── memory_system_v1.md
│   │   │       └── profile_system_v1.md
│   │   │
│   │   ├── context/
│   │   │   ├── builder.py
│   │   │   ├── message_projection.py
│   │   │   ├── memory_selector.py
│   │   │   ├── token_budget.py
│   │   │   └── ability_view.py
│   │   │
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── engine.py
│   │   │   ├── unit_of_work.py
│   │   │   ├── models/
│   │   │   │   ├── character.py
│   │   │   │   ├── campaign.py
│   │   │   │   ├── session.py
│   │   │   │   ├── message.py
│   │   │   │   ├── memory.py
│   │   │   │   └── runtime.py
│   │   │   └── repositories/
│   │   │       ├── characters.py
│   │   │       ├── campaigns.py
│   │   │       ├── sessions.py
│   │   │       ├── messages.py
│   │   │       ├── memories.py
│   │   │       └── agent_runs.py
│   │   │
│   │   ├── files/
│   │   │   ├── storage.py
│   │   │   ├── sheet_parser.py
│   │   │   ├── archive_builder.py
│   │   │   └── safety.py
│   │   │
│   │   └── events/
│   │       ├── hub.py
│   │       └── schemas.py
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── privacy/
│       ├── concurrency/
│       └── fixtures/
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── app/
│       │   ├── router.tsx
│       │   ├── queryClient.ts
│       │   └── AppShell.tsx
│       ├── api/
│       │   ├── client.ts
│       │   ├── generated.ts
│       │   └── events.ts
│       ├── pages/
│       │   ├── CampaignListPage.tsx
│       │   ├── CampaignDetailPage.tsx
│       │   ├── PlayPage.tsx
│       │   ├── CharacterListPage.tsx
│       │   ├── CharacterDetailPage.tsx
│       │   └── DebugPage.tsx
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
│       ├── styles/
│       └── types/
│
├── scripts/
│   ├── dev.py
│   ├── export_openapi.py
│   └── check.py
│
└── docs/
    └── adr/
        ├── 0001-single-process-local-app.md
        ├── 0002-sqlite-as-source-of-truth.md
        ├── 0003-bounded-langgraph-runs.md
        ├── 0004-query-level-cognitive-isolation.md
        └── 0005-append-only-message-revisions.md
```

目录原则：

- `domain/` 不导入 FastAPI、SQLAlchemy、PydanticAI 或 LangGraph；
- `api/` 不直接写 SQLAlchemy Query；
- `agents/` 不直接访问 Repository；
- `runtime/` 只通过 Service、Repository 接口读取或提交；
- ORM Model、API Schema 和 Agent Schema 必须是三组不同的类型；
- 前端 `features/` 按产品能力组织，避免把所有组件堆进通用目录。

---

# 6. 数据模型设计

## 6.1 关系概览

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

所有主键使用 UUID 字符串。所有时间以 UTC 保存，仅用于排序、审计和内部逻辑，产品 UI 不要求展示。

## 6.2 `characters`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `name` | text | 显示名称 |
| `roleplay_prompt` | text | 核心扮演 Prompt |
| `avatar_path` | text nullable | 数据目录内相对路径 |
| `max_hp` | integer | DM 手动设置，必须大于 0 |
| `active_sheet_version_id` | UUID nullable | 当前有效角色卡版本 |
| `created_at` | datetime | 内部时间 |
| `updated_at` | datetime | 内部时间 |
| `revision` | integer | 乐观并发版本号 |

`development_profile` 不直接放在本表，使用独立状态表以支持删除 Campaign 后安全重建。

## 6.3 `character_sheet_versions`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `character_id` | UUID | 所属角色 |
| `stored_path` | text | UUID 文件名相对路径 |
| `original_filename` | text | 仅展示，不参与路径 |
| `sha256` | text | 文件指纹 |
| `parse_status` | enum | `PENDING/VALID/FAILED` |
| `parser_version` | text | 解析器版本 |
| `parsed_snapshot` | JSON nullable | 定性身份与实际能力快照 |
| `parse_error_code` | text nullable | 安全错误代码 |
| `created_at` | datetime | 上传时间 |

只有 `VALID` Version 可以成为 `active_sheet_version_id`。失败的新文件不能覆盖旧版本。

## 6.4 `character_profiles`

| 字段 | 类型 | 说明 |
|---|---|---|
| `character_id` | UUID | 主键兼外键 |
| `content` | text | 当前 Character Development Profile |
| `status` | enum | `READY/NEEDS_REBUILD/GENERATING/FAILED` |
| `revision` | integer | 编辑与重建版本 |
| `updated_by` | enum | `DM/SYSTEM` |
| `updated_at` | datetime | 内部时间 |

当 Campaign 重置或永久删除时：

1. 删除对应来源记忆；
2. 在同一事务中清空受影响 Profile 并设为 `NEEDS_REBUILD`；
3. Agent Context 在状态不是 `READY` 时不读取该 Profile；
4. 后台根据剩余记忆重建。

这样即使重建调用失败，也不会继续向 Agent 提供已删除 Campaign 的残留信息。

## 6.5 `campaigns`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `name` | text | Campaign 名称 |
| `description` | text nullable | 描述 |
| `lifecycle_status` | enum | `PREPARATION/ACTIVE/COMPLETED` |
| `archived_at` | datetime nullable | 归档不是生命周期 |
| `created_at` | datetime | 内部时间 |
| `updated_at` | datetime | 内部时间 |
| `revision` | integer | 乐观并发 |

数据库使用 Partial Unique Index 保证全站最多一个 ACTIVE Campaign：

```sql
CREATE UNIQUE INDEX ux_campaign_single_active
ON campaigns(lifecycle_status)
WHERE lifecycle_status = 'ACTIVE';
```

## 6.6 `campaign_memberships`

| 字段 | 类型 | 说明 |
|---|---|---|
| `campaign_id` | UUID | 联合主键 |
| `character_id` | UUID | 联合主键 |
| `joined_at` | datetime | 加入时间 |
| `joined_session_id` | UUID nullable | 中途加入时的 Session |
| `joined_after_message_id` | UUID nullable | 审计加入边界 |

角色实际可见性不通过时间比较推导，而由每条消息的 `message_recipients` 快照决定。

1～6 人限制和同 Campaign 内角色名不重复由 Campaign Service 在事务中校验。不要把 6 设计成数据库永久字段宽度。

## 6.7 `sessions`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `campaign_id` | UUID | 所属 Campaign |
| `title` | text | Session 标题 |
| `status` | enum | `ACTIVE/ENDED` |
| `next_sequence_no` | integer | 原子分配消息顺序 |
| `started_at` | datetime | 内部时间 |
| `ended_at` | datetime nullable | 内部时间 |

数据库 Partial Unique Index 保证同一 Campaign 最多一个 ACTIVE Session。

## 6.8 `session_character_states`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | UUID | 联合主键 |
| `character_id` | UUID | 联合主键 |
| `current_hp` | integer | DM 可见精确值 |
| `max_hp_snapshot` | integer | 当前 Session 的 Max HP 快照 |
| `updated_at` | datetime | 内部时间 |

约束：

```text
0 <= current_hp <= max_hp_snapshot
max_hp_snapshot > 0
```

修改角色 `max_hp` 时，只同步当前 ACTIVE Session 对应状态，并把 `current_hp` 设为新的 Max HP；ENDED Session 不更新。

Agent 不读取这两个整数，而读取 `HealthStatusPolicy` 生成的定性状态。

## 6.9 `session_runtimes`

每个 Session 一行：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | UUID | 主键 |
| `status` | enum | `IDLE/AGENTS_EVALUATING/VALIDATING_MESSAGE/WAITING_FOR_DM/ERROR/ENDED` |
| `generation` | integer | 旧 Run 失效令牌 |
| `active_agent_run_id` | UUID nullable | 当前有效 Run |
| `last_trigger_message_id` | UUID nullable | 最新触发消息 |
| `waiting_message_id` | UUID nullable | 需要 DM 裁决的角色消息 |
| `waiting_request` | text nullable | UI 展示的裁决请求 |
| `consecutive_ai_messages` | integer | 两条 DM 消息之间的 AI 气泡数 |
| `updated_at` | datetime | 内部时间 |

达到 12 条时设为 `IDLE`，不创建下一 Run。DM 新 IN_GAME 消息把计数归零。

## 6.10 `messages`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `session_id` | UUID | 所属 Session |
| `sequence_no` | integer | Session 内追加顺序 |
| `sender_type` | enum | `DM/CHARACTER/SYSTEM` |
| `sender_character_id` | UUID nullable | Character 发送者 |
| `kind` | enum | `IN_GAME/OOC/SYSTEM` |
| `audience` | enum | `PUBLIC/PRIVATE/DM_ONLY` |
| `content` | text | 不原地修改 |
| `client_request_id` | UUID nullable | 防止浏览器重复提交 |
| `origin_agent_run_id` | UUID nullable | AI 消息来源 |
| `created_at` | datetime | 内部时间 |

约束与索引：

- `UNIQUE(session_id, sequence_no)`；
- `UNIQUE(client_request_id)`，NULL 除外；
- Character 消息必须有 `sender_character_id`；
- DM 和 SYSTEM 消息不得伪造 Character Sender；
- AI 候选只有成功发布时才创建 Message。

## 6.11 `message_recipients`

| 字段 | 类型 | 说明 |
|---|---|---|
| `message_id` | UUID | 联合主键 |
| `character_id` | UUID | 联合主键 |

只要角色能够感知该消息，就存在一行。DM 始终可读取全部消息，因此不需要作为 Recipient 保存。

规则：

- PUBLIC：保存发送时全部 Campaign Membership 的快照；
- PRIVATE：只保存 DM 选择的角色；
- DM_ONLY Character Message：至少保存发送角色自己，其他角色无记录；
- 中途加入角色不会被补入旧消息 Recipient；
- Context 和角色摘要从 Recipient Join 开始查询，不先加载全量消息再过滤。

## 6.12 `message_corrections`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `target_message_id` | UUID | 被纠正消息 |
| `ooc_message_id` | UUID | OOC 指令消息 |
| `correction_type` | enum | `LATEST_REPLACE/FACTUAL_CORRECTION/INVALIDATE` |
| `replacement_message_id` | UUID nullable | 重新生成或 DM 正确版本 |
| `export_policy` | enum | `OMIT/REPLACE` |
| `status` | enum | `PENDING/APPLIED/FAILED` |
| `created_at` | datetime | 内部时间 |

Message 本身不保存 `is_deleted` 或被覆盖后的新正文。由 `EffectiveMessageProjection` 根据 Correction 关系和当前查看者构建：

- UI 当前有效时间线；
- Character Context；
- 角色摘要与长期记忆；
- Campaign Markdown；
- `campaign.json`。

Projection 必须显式接收查看模式：

```python
EffectiveMessageProjection.for_dm(session_id)
EffectiveMessageProjection.for_character(session_id, character_id)
EffectiveMessageProjection.for_export(campaign_id)
```

OOC 可以是公开或私密的，因此 Correction 不是对所有角色统一生效：

- 对存在于 OOC Message Recipient Snapshot 中的角色，应用纠正；
- 对无权看到该 OOC 的角色，仍保留其原先实际知道的版本；
- 角色 Summary、Memory 和 Context 使用 `for_character`；
- DM UI 使用 `for_dm`，同时显示 Correction 的可见范围；
- Export 使用同一规则核心，但根据 `export_policy` 输出省略或替代版本；
- 较早事实纠正时，DM UI 保留原消息并显示“后来已纠正”，角色 Context 使用其有权看到的纠正事实。

禁止在上述使用方各自实现一套 OOC 规则。

## 6.13 `character_session_summaries`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `session_id` | UUID | 所属 Session |
| `character_id` | UUID | 所属角色 |
| `kind` | enum | `ROLLING/FINAL` |
| `content` | text | 角色可编辑内容 |
| `status` | enum | `PENDING/READY/FAILED` |
| `revision` | integer | 编辑版本 |
| `updated_by` | enum | `DM/SYSTEM` |
| `updated_at` | datetime | 内部时间 |

唯一约束：`UNIQUE(session_id, character_id, kind)`。

摘要生成器只能调用角色级可见消息查询，不得读取 DM Summary。

## 6.14 `dm_session_summaries`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | UUID | 主键 |
| `content` | text | DM 全局摘要 |
| `status` | enum | `PENDING/READY/FAILED` |
| `updated_at` | datetime | 内部时间 |

该表永远不能被 Character Context Repository 引用。

## 6.15 `character_memories`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `character_id` | UUID | 所属角色 |
| `content` | text | 定性记忆 |
| `source_type` | enum | `CAMPAIGN/DM_MANUAL` |
| `source_campaign_id` | UUID nullable | Campaign 来源 |
| `source_session_id` | UUID nullable | Session 来源 |
| `pinned` | boolean | 固定记忆 |
| `created_at` | datetime | 内部排序 |
| `updated_at` | datetime | 内部时间 |

Check Constraint：

- `CAMPAIGN` 必须有 Campaign 和 Session 来源；
- `DM_MANUAL` 不依赖 Campaign 来源；
- 不保存数值重要度、情绪分数、好感度或关系值。

## 6.16 `agent_runs`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `campaign_id` | UUID | 归属 Campaign，便于级联删除 |
| `session_id` | UUID | 所属 Session |
| `trigger_message_id` | UUID | 触发事件 |
| `generation` | integer | 创建时的 Runtime Generation |
| `status` | enum | `PENDING/RUNNING/COMPLETED/CANCELLED/FAILED` |
| `stop_reason` | enum nullable | `PUBLISHED/ALL_SILENT/WAITING_FOR_DM/LIMIT_REACHED/STALE/DM_STOP/DM_PREEMPTED/ERROR` |
| `selected_character_id` | UUID nullable | 最终被选角色 |
| `published_message_id` | UUID nullable | 实际发布消息 |
| `eligible_count` | integer | 被调用角色数 |
| `response_count` | integer | RESPOND 数 |
| `random_seed` | integer nullable | 平局排序审计 |
| `started_at` | datetime | 内部时间 |
| `finished_at` | datetime nullable | 内部时间 |

同一 Session 只能有一个 Runtime 指向的有效 RUNNING AgentRun。

## 6.17 `llm_invocations`

统一记录 Character、Validator、Summary、Memory 和 Profile 调用：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `campaign_id` | UUID nullable | 归属 Campaign |
| `session_id` | UUID nullable | 归属 Session |
| `agent_run_id` | UUID nullable | Runtime 调用所属 Run |
| `character_id` | UUID nullable | 角色相关调用 |
| `purpose` | enum | `CHARACTER/VALIDATOR/SUMMARY/MEMORY/PROFILE` |
| `provider` | text | Gemini、DeepSeek 等 |
| `model` | text | 模型名 |
| `prompt_version` | text | Prompt 文件版本 |
| `status` | enum | `RUNNING/SUCCEEDED/FAILED/CANCELLED` |
| `decision` | text nullable | SILENCE/RESPOND 或校验结果 |
| `input_tokens` | integer nullable | 供应商统计 |
| `output_tokens` | integer nullable | 供应商统计 |
| `duration_ms` | integer nullable | 调用耗时 |
| `retry_count` | integer | 重试次数 |
| `error_code` | text nullable | 脱敏错误码 |
| `created_at` | datetime | 内部时间 |

默认不保存完整 Prompt、完整 Context 或未发布 Candidate 正文。

---

# 7. 关键事务与一致性规则

## 7.1 DM 发送消息

同一数据库事务内：

1. 验证 Campaign 和 Session 可写；
2. 检查 `client_request_id`，已存在则返回原结果；
3. Runtime Generation 加一；
4. 旧 Active AgentRun 标记为 `CANCELLED/DM_PREEMPTED`；
5. 分配 Message Sequence；
6. 写入 Message；
7. 写入 Recipient Snapshot；
8. 清除 WAITING_FOR_DM；
9. IN_GAME 时连续 AI 计数归零；
10. Runtime 设为 `AGENTS_EVALUATING`；
11. 创建新的 AgentRun；
12. 提交事务。

事务提交后：

- Runtime Supervisor 尝试取消旧 asyncio Task；
- 启动新 AgentRun；
- SSE 通知所有标签页刷新消息和 Runtime。

## 7.2 AI 原子发布

同一事务内：

1. 再次读取 Session Runtime；
2. 比较 Generation 和 Active AgentRun ID；
3. 验证 Session 仍 ACTIVE；
4. 验证连续 AI 数量未达到 12；
5. 分配 Message Sequence；
6. 写入最终 Message 和 Recipient Snapshot；
7. 更新 AgentRun 的 Published Message；
8. 连续 AI 数量加一；
9. 若需要 DM，Runtime 设为 WAITING_FOR_DM；
10. 若计数达到 12，Runtime 设为 IDLE，当前 Run 以 LIMIT_REACHED 结束；
11. 否则在同一事务中创建以新消息为 Trigger 的后继 AgentRun，并把它设为 Active Run；
12. 提交事务。

候选校验通过不代表有权发布；只有此事务比较成功才可以发布。

事务提交后，Runtime Supervisor 启动后继 AgentRun。这样 AI 连续对话不会在“消息已经发布、下一 Run 尚未登记”的空档中产生错误；若 DM 随即发来新消息，新的 Generation 仍会使该后继 Run 失效。

## 7.3 停止 AI

同一事务内：

- Generation 加一；
- Active Run 标记 `CANCELLED/DM_STOP`；
- Active Run ID 清空；
- Runtime 设为 IDLE；
- 保留已发布消息。

之后尽力取消本地 Task。取消失败也不会影响正确性。

## 7.4 OOC 修订最新消息

分为两个阶段：

### 阶段一：建立修订请求

事务内：

- 校验 Target 是当前 Session 最新有效非 OOC 消息；
- Generation 加一并取消旧 Run；
- 追加 OOC Message；
- 创建 `message_corrections(PENDING)`；
- Runtime 进入 `VALIDATING_MESSAGE`，暂不启动普通全角色 Run。

### 阶段二：生成或提交替代版本

- AI Target：只调用原 Character 重新处理；
- DM Target：使用 DM 表单中提供的正确版本；
- 新内容通过与普通消息相同的校验；
- 事务内写入 Replacement Message 并把 Correction 设为 APPLIED；
- 原正文仍保留在数据库，但对已收到该 OOC 的角色不再出现在有效事实视图；
- Replacement 成为新的触发事件，并在同一事务中登记普通后继 AgentRun。

Correction 一旦进入 PENDING，原消息就不再作为已收到该 OOC 角色的有效事实；UI 显示“正在纠正”。

失败时 Correction 设为 FAILED、Runtime 设为 ERROR，原消息对已收到该 OOC 的角色仍保持无效；DM 可以重试或改为 INVALIDATE。如果原角色选择 SILENCE，则 Correction 改为 INVALIDATE，不创建 Replacement。不要因为重新生成失败而把已明确指出的错误重新放回 Agent Context。

若原角色选择 SILENCE，OOC Message 本身成为普通后继 AgentRun 的 Trigger；若是较早事实的 `FACTUAL_CORRECTION`，无需特殊重生成阶段，提交 OOC 与 Correction 后即可直接以 OOC Message 触发所有有权看到它的角色。OOC 只改变事实认知，不作为场内事件写入摘要或长期记忆。

## 7.5 Session 结束

事务内先完成不可失败的状态变化：

- Generation 加一；
- 取消 Active Run；
- Session 设为 ENDED；
- Runtime 设为 ENDED；
- 保存最终 HP；
- 创建摘要和记忆任务状态行 `PENDING`。

事务提交后异步执行：

- DM Summary；
- 每个角色 FINAL Summary；
- 每个角色长期记忆提取。

单项失败只把对应状态设为 FAILED，并提供重试，不回滚 Session 结束。

## 7.6 Campaign 重置或永久删除

事务开始前收集受影响 Character IDs。

事务内：

- 使 Runtime Generation 失效；
- 删除 Campaign 来源 Memory；
- 清空受影响 Character Profile 并标记 NEEDS_REBUILD；
- 重置时删除 Session 级数据并保留 Campaign/Membership；
- 永久删除时级联删除 Campaign 级数据；
- 提交。

事务提交后：

- 根据角色剩余 Memory 重建 Profile；
- 重建前 Agent 不读取该 Profile；
- 永久删除的 Campaign 数据不能进入重建输入。

---

# 8. Context 与认知隔离

## 8.1 唯一 Context 入口

所有 Character、Summary、Memory 调用必须经过：

```python
ContextBuilder.build_for_character(
    character_id=...,
    session_id=...,
    trigger_message_id=...,
    purpose=...,
)
```

禁止 Agent Service 自行组合 SQL 查询结果。

## 8.2 构建顺序

```text
角色身份与 Prompt
→ 当前有效 Sheet Snapshot
→ Profile（仅 READY）
→ 角色自己的旧 Campaign Summary
→ 角色自己的 Long-Term Memory
→ 当前 Session Rolling Summary
→ 当前角色 Recipient 可见的 Effective Messages
→ 定性 Health View
→ 当前 Trigger
→ Token Budget 裁剪
```

## 8.3 数据库查询级隔离

角色消息查询必须以 `message_recipients.character_id = :character_id` 为必要 Join 条件。

以下数据不得先加载后依赖 Prompt 过滤：

- 其他角色私密消息；
- DM_ONLY 消息；
- DM Summary；
- 角色加入前消息；
- 其他角色 Summary；
- 其他角色 Memory；
- 其他角色 Prompt；
- 未发布 Candidate。

## 8.4 Memory Selector

MVP 不引入向量数据库。定义可替换接口：

```python
class MemorySelector(Protocol):
    async def select(
        self,
        character_id: str,
        trigger_text: str,
        token_budget: int,
    ) -> list[CharacterMemory]: ...
```

MVP 策略：

1. 全部 pinned Memory；
2. 当前 Campaign 相关 Memory；
3. 最近的未固定 Memory；
4. 在 Token Budget 内截断。

将来需要时可以替换为 Embedding 或混合检索，不改变 Character Agent 接口。

## 8.5 Token Budget

预算从高到低保留：

1. 全局角色约束；
2. Roleplay Prompt；
3. Trigger Message；
4. 最新 OOC 修正事实；
5. 最新 DM 事实和最近原始消息；
6. 能力说明；
7. Rolling Summary；
8. Pinned Memory；
9. 其他长期记忆；
10. 较旧原始消息。

Context Builder 输出每个板块实际估算 Token，供 Debug 页面查看，但不保存私密正文。

## 8.6 HP 视图

`HealthStatusPolicy` 是纯函数：

```text
current_hp / max_hp_snapshot
→ HEALTHY / LIGHTLY_HURT / HEAVILY_HURT / CRITICAL / UNCONSCIOUS
```

阈值与 PRD 保持一致：

- `current_hp > 75% max_hp_snapshot`：`HEALTHY`；
- `50% < current_hp <= 75%`：`LIGHTLY_HURT`；
- `25% < current_hp <= 50%`：`HEAVILY_HURT`；
- `0 < current_hp <= 25%`：`CRITICAL`；
- `current_hp <= 0`：`UNCONSCIOUS`。

只有该枚举及中文描述进入 Agent Context，准确 HP 不进入。

---

# 9. API 与前端通信

## 9.1 API 风格

- 使用 `/api/v1` 前缀；
- 查询使用标准 GET；
- 普通字段编辑使用 PATCH；
- 生命周期与破坏性操作使用显式 Command Endpoint；
- 所有发送消息请求带客户端生成的 `clientRequestId`；
- 错误统一返回稳定的 `errorCode` 和可展示信息；
- 不把供应商原始错误或密钥返回前端。

示例：

```text
POST   /api/v1/characters
PATCH  /api/v1/characters/{id}
POST   /api/v1/characters/{id}/sheet-versions:preview
POST   /api/v1/characters/{id}/sheet-versions/{versionId}:activate

POST   /api/v1/campaigns
POST   /api/v1/campaigns/{id}:activate
POST   /api/v1/campaigns/{id}:complete
POST   /api/v1/campaigns/{id}:reopen
POST   /api/v1/campaigns/{id}:reset
DELETE /api/v1/campaigns/{id}

POST   /api/v1/campaigns/{id}/sessions
POST   /api/v1/sessions/{id}:end
POST   /api/v1/sessions/{id}/messages
POST   /api/v1/messages/{id}/corrections
PATCH  /api/v1/sessions/{id}/characters/{characterId}/hp

POST   /api/v1/sessions/{id}/runtime:stop
POST   /api/v1/sessions/{id}/runtime:retry-latest
GET    /api/v1/sessions/{id}/events
```

## 9.2 SSE

SSE 只负责服务器向页面推送“数据发生变化”的通知，页面仍通过 REST 获取完整状态。

事件类型：

```text
message.created
message.effective_view.changed
runtime.changed
hp.changed
summary.changed
memory.changed
campaign.changed
```

事件 Payload 只带必要 ID 和版本号，不直接广播私密消息正文。

SSE 断线重连后，前端重新获取当前 Session Snapshot，因此不需要持久化 SSE 消息队列。

## 9.3 前端状态原则

- TanStack Query 保存服务器状态；
- Chat Timeline、Runtime、HP 不复制到长期全局 Store；
- SSE 到达后只使对应 Query 失效；
- 输入框草稿是本地组件状态；
- 乐观更新只用于无风险 UI，不对消息发布、HP 或生命周期状态做假提交；
- 所有页面刷新后都可只依靠 API 恢复。

## 9.4 OpenAPI 类型

FastAPI 生成 OpenAPI，使用脚本生成 `frontend/src/api/generated.ts`。禁止手工维护第二套重复 DTO 类型。

---

# 10. 本地文件与配置

## 10.1 数据目录

通过 `AI_TRPG_DATA_DIR` 配置：

```text
AI_TRPG_DATA/
├── app-data.sqlite3
├── uploads/
│   ├── avatars/
│   └── character-sheets/
├── temp/
└── exports/
```

项目仓库内不创建正式运行数据库。

## 10.2 文件写入

- 文件名使用 UUID；
- 原文件名只保存在数据库；
- 上传先写入 `temp/`；
- 验证成功后使用原子 Rename 移入正式目录；
- 校验扩展名、MIME、文件签名和大小；
- 计算 SHA-256；
- 解析器不信任 Excel 公式结果和外部链接；
- ZIP 导出防止路径穿越；
- 删除临时文件采用明确路径，不使用宽泛通配符。

## 10.3 环境变量

```text
AI_TRPG_DATA_DIR=
AI_TRPG_LLM_PROVIDER=google|deepseek
AI_TRPG_CHARACTER_MODEL=
AI_TRPG_VALIDATOR_MODEL=
AI_TRPG_SUMMARY_MODEL=
AI_TRPG_MAX_PARALLEL_LLM_CALLS=6
AI_TRPG_LOG_LEVEL=INFO
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=
```

API Key 只来自环境变量或本机未跟踪配置文件，不进入数据库、导出、日志或前端。

## 10.4 模型配置

定义用途级模型配置，而不是在代码各处写死模型名：

```python
class ModelSettings:
    character_model: str
    validator_model: str
    summary_model: str
    memory_model: str
    profile_model: str
```

MVP 可以让五个用途都指向同一便宜模型，但保留以后拆分的能力。

---

# 11. 后台任务与并发

## 11.1 Runtime Supervisor

单进程内维护：

```python
dict[session_id, asyncio.Task]
```

职责：

- 启动当前 AgentRun；
- 尝试取消过期 Task；
- 限制全局并行 LLM 调用数；
- 捕获顶层异常；
- 将未处理异常转换为 Run FAILED；
- Task 完成后清理注册表。

不得使用 FastAPI `BackgroundTasks` 作为 Runtime Supervisor，因为需要跨请求取消和查看 Task。

## 11.2 并发限制

- 角色判断最多并行 6 个；
- Validator 只检查最终候选；
- Memory/Summary 后台调用也共享全局 Semaphore；
- SQLite 写事务短小，不在事务内等待 LLM；
- 网络调用开始前读取 Context Snapshot；
- 网络调用结束后通过 Generation 再确认是否可提交。

## 11.3 启动恢复

应用启动时：

- 将数据库中 `PENDING/RUNNING` AgentRun 标记为 FAILED；
- 清空无效 `active_agent_run_id`；
- ACTIVE Session Runtime 进入 ERROR 或 IDLE，并提供重试最新事件；
- 不自动重新调用模型；
- `WAITING_FOR_DM` 可以原样恢复，因为它是已发布消息后的业务状态，不是未完成 Run。

---

# 12. 代码规范建议

## 12.1 Python

- Python 文件使用 `snake_case`，类使用 `PascalCase`；
- 所有公共函数写完整参数和返回类型；
- 启用 Pyright strict 或逐模块收紧；
- 使用 Ruff 负责格式化与 Lint；
- 使用 `from __future__ import annotations`；
- 不使用裸 `dict` 传递核心业务数据，使用 dataclass、TypedDict 或 Pydantic Model；
- 不在 Route 中写业务判断；
- 不在 ORM Model 中调用 LLM；
- 不用布尔值表示多状态生命周期，统一使用 Enum；
- 不捕获裸 `Exception` 后静默继续；
- 外部异常在基础设施边界转换为稳定的应用错误；
- 所有数据库写入通过 Unit of Work；
- 不在数据库事务中等待网络或模型调用；
- 时间统一使用带时区 UTC；
- ID 统一由应用层生成，便于事务前引用；
- Prompt 使用独立版本文件，不在 Python 中散落长字符串。

## 12.2 TypeScript / React

- `strict: true`；
- 禁止无理由使用 `any`；
- API DTO 从 OpenAPI 生成；
- 页面负责组合，业务组件放在对应 Feature；
- 组件不直接拼 API URL；
- Query Key 集中定义；
- 所有 Mutation 统一处理错误码；
- 不在前端重新实现 Campaign、OOC 或权限规则；
- Runtime 状态以服务器为准；
- 无障碍地标、按钮名称和键盘操作作为基础要求；
- 只做桌面断点，但避免固定像素导致普通笔记本无法使用。

## 12.3 数据库

- 表名和字段统一 `snake_case`；
- 每次 Schema 改动必须有 Alembic Migration；
- 正式启动不调用 `create_all()`；
- 测试数据库可以从 Migration 创建；
- 外键开启 `PRAGMA foreign_keys=ON`；
- 明确设置级联或 RESTRICT，不依赖 ORM 默认；
- 破坏性删除必须由 Service 显式执行；
- JSON 只用于角色卡快照等整体读取结构，不把核心关系藏进 JSON；
- Message Recipient 必须是关系表，不能只用 JSON 数组。

## 12.4 日志与隐私

允许记录：

- ID；
- 状态变化；
- Provider/Model；
- Token；
- 耗时；
- 重试次数；
- 脱敏错误码。

默认禁止记录：

- API Key；
- 完整 Prompt；
- 完整角色记忆；
- 私密消息正文；
- 未发布候选正文；
- Chain of Thought；
- Excel 原始内容。

## 12.5 Prompt 规范

- Prompt 文件名包含版本；
- Prompt 变更必须写 Changelog 或 ADR；
- Prompt 中明确区分系统规则、角色资料、可见事实和触发事件；
- 数据块使用固定标签，避免文本边界模糊；
- 角色资料被视为数据，不允许覆盖系统规则；
- 记录每次调用使用的 `prompt_version`；
- 禁止要求模型输出隐藏推理；
- 测试只验证结构化决定与最终文本规则，不验证内部思维过程。

---

# 13. 测试策略

## 13.1 单元测试

必须覆盖：

- Campaign 状态转换；
- 唯一 ACTIVE Campaign 策略；
- Membership 上限；
- Health Status 映射；
- Speaker Priority；
- Candidate 确定性校验；
- Token Budget 裁剪；
- Effective Message Projection；
- OOC Export Policy；
- Memory Source 校验。

## 13.2 隐私与认知隔离测试

这是最高优先级测试集，至少包含：

1. PUBLIC 消息只对发送时成员可见；
2. 中途加入角色看不到加入前 PUBLIC 消息；
3. 私密 DM 消息不会进入未选角色 Context；
4. Agent DM_ONLY 消息不会进入队友 Context；
5. DM Summary 永不进入 Character Context；
6. 角色 Summary 只使用自己的 Recipient 消息；
7. OOC 作废正文不再进入 Context；
8. 被删除 Campaign 的 Memory 和 Profile 不再进入 Context；
9. 其他角色 Prompt、Memory 和 Sheet 不会进入当前角色调用；
10. Debug API 不返回未选候选正文。

建议使用 Golden Context 测试：构造一组公开、私密、中途加入和 OOC 数据，断言每个角色最终得到的 Context 精确内容。

## 13.3 并发测试

必须覆盖：

- DM 消息到达时旧 Run 不能发布；
- Stop 后供应商迟到响应不能发布；
- 两个标签页重复提交同一 `client_request_id` 只创建一条消息；
- 两个候选同时完成时只发布 Coordinator 选择的一条；
- 12 条上限不会发布第 13 条；
- Session 结束与 AI 提交竞争时，AI 提交失败；
- OOC 修订开始后旧候选失效。

## 13.4 Agent Contract 测试

使用 PydanticAI TestModel、FunctionModel 或假的 Model Adapter：

- SILENCE；
- 合法 PUBLIC 回复；
- 合法 DM_ONLY 回复；
- 漏标 DM Resolution；
- 结构化输出错误后重试；
- 越权正文被 Validator 退回；
- 单角色失败不影响其他角色；
- 全角色失败进入 ERROR。

CI 中不调用真实 Gemini 或 DeepSeek。

## 13.5 E2E

Playwright 至少覆盖：

- 创建角色并确认 Excel 解析；
- 创建并启动 Campaign；
- DM 首条消息触发角色；
- WAITING_FOR_DM；
- DM Stop；
- 私密消息；
- 最新消息 OOC 替换；
- 刷新后恢复；
- 结束 Session；
- 导出；
- 重置和永久删除确认。

---

# 14. 开发阶段建议

## Stage 0：工程骨架

- FastAPI、React、SQLite、Alembic；
- 配置和数据目录；
- 基础错误格式；
- SSE Event Hub；
- Lint、类型检查和测试命令。

## Stage 1：角色与 Campaign

- Character；
- Sheet Version 与解析预览；
- Campaign 生命周期；
- Membership；
- Session 和 HP。

## Stage 2：单角色 Agent 闭环

- Message、Recipient、Runtime；
- Context Builder；
- PydanticAI Character Agent；
- Validator；
- 一个气泡原子发布；
- WAITING_FOR_DM 和 Stop。

在单角色闭环稳定前，不开始多 Agent。

## Stage 3：多角色运行

- LangGraph Reaction Graph；
- 并行判断；
- Speaker Coordinator；
- Generation 抢占；
- 连续 12 条上限；
- 多标签页测试。

## Stage 4：私密与 OOC

- Recipient Snapshot；
- DM PRIVATE；
- Character DM_ONLY；
- Message Correction；
- Effective Message Projection；
- Privacy Golden Tests。

## Stage 5：记忆与导出

- Rolling/Final Summary；
- DM Summary；
- Long-Term Memory；
- Profile 更新与安全重建；
- Campaign/Character Export；
- Reset/Delete。

## Stage 6：真实模型评测

以同一组固定剧本比较 Gemini 与 DeepSeek：

- 结构化输出成功率；
- SILENCE 合理性；
- 人设区分度；
- 超游率；
- 叙事越权率；
- 漏标 DM 裁决率；
- 输入/输出 Token；
- 首次响应耗时；
- 连续 12 条对话总消耗。

根据测试结果选择默认模型，不让具体供应商进入 Domain 或 Runtime 规则。

---

# 15. MVP 明确推迟的技术能力

- 多用户、多 DM 和登录；
- 多 ACTIVE Campaign；
- 分布式 Worker；
- PostgreSQL、Redis 和任务队列；
- 向量检索和 Embedding Memory；
- 严格法术位、物品和能力次数系统；
- 移动端；
- Docker；
- Campaign 导入恢复；
- 消息全文搜索；
- 角色离开 ACTIVE Campaign；
- Agent 自主操作数据库；
- 关系数值化；
- Chain of Thought 保存或展示。

---

# 16. 架构验收标准

在进入完整 UI 开发前，后端原型应证明：

1. 两个角色收到同一公开消息，但各自 Context 中不存在对方秘密；
2. 新角色中途加入后无法读取历史公开消息；
3. 两个 Character Agent 可以并行返回候选，但只发布一个；
4. DM 在模型运行期间发送新消息后，旧候选即使迟到也不能发布；
5. 需要裁决的消息发布后，不会自动创建下一 Run；
6. Stop 后所有未发布候选失效；
7. OOC 替换后 UI、Context、Summary 和 Export 使用同一有效版本；
8. 删除 Campaign 后，对应 Memory 立即消失，Profile 在重建前不进入 Agent Context；
9. 后端重启后未完成 Run 标记失败，可重试最新事件；
10. 不依赖 Redis、Docker、外部数据库或托管 Agent Memory 即可完成上述流程。

满足以上条件后，这套轻量架构足以支撑 MVP，并且保留将 SQLite、Memory Selector、单进程 Supervisor 或模型供应商替换为更大规模实现的清晰边界。
