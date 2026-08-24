# AI TRPG MVP 技术架构

> 本文是当前开发架构入口。既有功能的完整背景见 [AI_TRPG_MVP_TECH_ARCHITECTURE.md](./AI_TRPG_MVP_TECH_ARCHITECTURE.md)，当前产品规则以 [PRD.md](./PRD.md) 为准。若旧版完整文档与本文关于 AI DM、角色关系、故事上下文、技能检定或 Campaign 连续时间线的设计冲突，以本文为准。

## 1. 架构目标

架构需要在本地单用户条件下，以尽可能少的基础设施可靠实现：

- 1～6 个独立 Character Agent；
- 严格的角色级认知和私密隔离；
- 一次只发布一个完整消息气泡；
- DM 新消息抢占未发布 AI 输出；
- AI 需要裁决时全局等待 DM；
- OOC 修订和按角色计算的有效消息；
- 一个 Campaign 一条连续时间线，并可安全暂停和继续；
- PREPARATION 阶段以模组内容生成开场草稿，发布开场时才启动 Campaign；
- 非战斗模式中由正式角色回复自动触发下一份 AI DM 草稿；
- AI DM 只生成可编辑草稿，未经真人 DM 确认绝不发布；
- AI DM 草稿支持公开或指定角色私密发送，并保持短回复；
- 新角色回复必须淘汰未发送的旧 DM 草稿并生成最新草稿；
- 保留 DM 手动输入意图或回复初稿后，由 AI DM 结合模组和角色回复润色的可选入口；
- 十八项技能加值、后端 D20 和不可变检定记录；
- 跨 Campaign 的角色记忆和成长；
- 自动生成并随共同故事实时演化的角色关系；
- Character Agent 读取完整既往故事，同时保持短回复；
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
13. **AI DM Runtime 与 Character Runtime 分离。** 前者只生成草稿，后者才可以按既有规则发布角色消息。
14. **草稿不是消息。** AI DM 草稿、技能检定和骰子结果默认不进入 Character Context。
15. **真人确认是投骰边界。** AI DM 只能建议检定，后端只有收到 DM 的确认命令才生成随机数。
16. **一个 Campaign 只有一条内部运行记录。** 不再创建、结束或切换多个 Session。
17. **暂停是生命周期状态，不是新时间线。** 暂停和继续不得重置消息序号、HP、待裁决事项或上下文。
18. **模组是 AI DM 的长期权威输入。** 模组只进入 AI DM Context，不进入 Character Context。
19. **角色正式回复是 AI DM 的主触发事件。** 非战斗模式下发布角色消息后，Character Runtime 必须等待真人处理自动生成的 DM 草稿。
20. **手动提示是可选覆盖层。** `MANUAL_ASSIST` 可以只改文笔、扩写细节或重写结构，但不能绕过草稿审核和发布事务，也不与自动草稿使用不同的上下文。
21. **角色关系是系统派生事实。** DM 不手工录入；Relationship Agent 只根据双方共同可见、确实发生的故事更新关系。
22. **角色连续性分三层构建。** Roleplay Prompt、动态关系与共同经历、完整既往故事共同进入 Character Context。
23. **长上下文不等于长输出。** Character Agent 与 AI DM 均以明确的句数、字符数和生成 Token 上限约束回复。
24. **最新角色回复拥有草稿优先权。** 新回复到达时，所有未发送的非开场草稿立即失效；迟到模型结果不得覆盖新草稿。
25. **私密 DM 在发布边界实施隔离。** 草稿可建议接收者，但发布时仍由 Message Service 校验当前成员并生成 Recipient Snapshot。
26. **AI 称呼以自然表达为主。** Character Agent 和 AI DM 允许第一、第二人称代词；姓名和明确身份称呼用于消除歧义及保护陌生角色身份。

## 4. 总体结构

```text
┌───────────────────────────────────────────────────────┐
│ React Desktop Web                                     │
│ Character / Campaign / Play / Skills / Memory / Debug │
│ REST Commands + SSE Notifications                     │
└──────────────────────────┬────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────┐
│ FastAPI                                                │
│                                                       │
│ API Routes                                             │
│   └─ Application Services                             │
│        ├─ Character & Sheet                           │
│        ├─ Campaign Lifecycle                          │
│        ├─ Message & OOC                               │
│        ├─ AI DM Draft & Skill Check                   │
│        ├─ Character Relationship                      │
│        ├─ Runtime Supervisor                          │
│        ├─ Context & Memory                            │
│        └─ Export                                      │
│                                                       │
│ Agent Runtime                                          │
│   ├─ Character Runtime Supervisor                     │
│   ├─ AI DM Draft Supervisor                           │
│   ├─ PydanticAI Agents                                │
│   ├─ Relationship Agent                               │
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

一条需要 Character Agent 反应的已发布 DM 消息对应一次 `AgentRun`，一个 Run 最多发布一条新角色消息。

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

在 NARRATIVE 模式下，是否停下由角色自己在 `requires_dm_resolution` 中声明，而不是按固定节奏。纯角色互动会继续串联后继 Character AgentRun；只有以下三种情形会结束链条并触发 `CHARACTER_REPLY` AI DM Draft：

```text
requires_dm_resolution = true      → WAITING_FOR_DM，waiting_request 为角色的原始提问
向世界提问的确定性兜底命中          → WAITING_FOR_DM
consecutive >= MAX_CONSECUTIVE_AI_MESSAGES  → IDLE
全员沉默且本轮由角色消息触发        → IDLE
```

候选集合始终排除触发消息的发送者：角色不回复自己刚说的话。缺少这一条时，发言者会被自己的消息重新触发；多角色阵容里协调器的公平性排序掩盖了它，但单角色战役或只发给一人的私密消息下，唯一候选就是他自己，角色会一路自问自答直到触及上限，并在过程中替 NPC 编造回答。

确定性兜底 `_question_needs_the_world` 只在下列条件同时成立时命中：正文含问号、未点名任何队友、正文中没有出现队友姓名、且触发消息来自 DM。它覆盖模型漏报 `requires_dm_resolution` 的情况——多等一次只是多一份可以忽略的草稿，漏等则等于让 AI 替世界发言。

前两者以刚发布的角色消息为草稿来源，第三者以触发消息为来源。全员沉默若发生在 DM 消息之后（没人接 DM 的话），不生成草稿——DM 刚说完，不该立刻再给他一段。

这样设计的取舍是：世界反馈仍然全部经过真人确认（因为触及世界的发言必定声明裁定），但角色之间的对话不会每句话都被打断。代价是准确性依赖 Character Agent 正确声明 `requires_dm_resolution`，因此该规则在 Prompt 中以四类具体情形加一条判断标准给出，而不是笼统的"结果不确定时"。

在 COMBAT 模式下，Character Message 不触发 AI DM Draft。当前实现中 COMBAT 仍会串联后继 Character Run，并以 `MAX_CONSECUTIVE_AI_MESSAGES = 5` 为上限；该上限同时是 `session_runtimes.consecutive_ai_messages` 的 CHECK 约束。COMBAT 是否应当完全不串联，与本节描述尚存分歧，待确认后统一。

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

MVP 不使用 LangGraph Persistent Checkpointer。Graph State 只存在于当前进程内；业务状态由 SQLite 的 `agent_runs`、内部 `session_runtimes` 和 `llm_invocations` 保存。

### 5.3 Character Agent 输出

```python
class CharacterDecision:
    decision: Literal["SILENCE", "RESPOND"]
    inner_beat: str                       # 内联 CoT，不入库、不展示
    content: str
    visibility: Literal["PUBLIC", "DM_ONLY"]
    urgency: Literal["NORMAL", "HIGH", "IMMEDIATE"]
    addressed_character_ids: list[str]
    requires_dm_resolution: bool
    resolution_request: str | None
```

字段顺序是有意义的。结构化输出自上而下生成，`inner_beat` 位于 `content` 之前，因此模型必须先确定角色此刻的反应，再写台词。这是一次零额外请求、零额外延迟的内联思维链；该字段在提交结果时直接丢弃，只在 `llm_invocations` 中留档供调试。

`response_type` 已移除：产品中没有任何位置区分 SPEECH / ACTION / SPEECH_AND_ACTION，保留它只会让模型多填一个从不被读取的字段。

一次调用只返回一个完整候选。未选择候选只在当前 Run 内存中短暂存在，默认不持久化正文。

Character Agent 的 Prompt 要求正文为一句台词、一个动作或「一个动作 + 一句台词」，目标 80 个中文字符以内；Schema 硬限制为 240 字符，模型生成上限为 600 Tokens（较此前的 400 提高，用于容纳 `inner_beat` 而不挤压正文）。长度要求在 Prompt 中只出现一次。完整故事用于提高连续性，不得被解释为要求复述背景或生成长段落。

`CharacterDecision` 的 `content` 和 `resolution_request` 允许自然使用第一、第二人称，不做人称代词硬校验。Context Builder 仍显式提供 `当前角色名称`；已认识角色可按语境使用姓名或代词，未认识角色继续使用隐私过滤后的陌生人编号，避免通过称呼泄露身份。

### 5.4 Speaker Coordinator

Speaker Coordinator 使用纯 Python 规则，并对候选给出完整排序（`rank`），而不只是取最优者（`select` 是 `rank` 的第一项）。完整排序是发布前校验降级的前提。

优先级：

1. 被最新消息直接点名或提问；
2. `IMMEDIATE`；
3. 更高 urgency；
4. 更久没有实际发言；
5. 完全相同时使用记录了 Seed 的随机选择。

Coordinator 不使用 LLM，不改写候选，也不替角色决定行动。

第 1 档的点名判定依次尝试三层：

```text
messages.addressed_character_ids      # DM 发送时显式勾选
  ↓ 为空时
上一条角色消息继承的 addressed_character_ids
  ↓ 为空时
角色姓名子串匹配                       # 仅作兜底
```

只用姓名匹配时，「你们两个先进去」这类代词点名匹配不到任何人，第 1 档恒不触发，选择规则退化为「紧急度 → 最久没发言 → 随机」，表现为角色近似轮流发言。角色候选输出的 `addressed_character_ids` 在发布时写入消息，与消息本身的可见范围取交集并排除发言者自己。

### 5.5 发布前校验

第一层为确定性规则：

- 结构化输出合法；
- SILENCE 与正文一致；
- visibility 合法；
- 没有机械数值或明显检定申请；
- DM_ONLY、待裁决和单气泡字段一致；
- 正文长度在限制内；
- 正文不含破折号（`—`、`——`、`--`）。

机械数值的判定只在数字与规则术语共现时触发（`12点伤害`、`DC15`、`d20`），不再屏蔽全部数字，「我数到三」「第 2 次了」属于正常台词。注意 Python 将中日韩字符视为 word character，`\b` 在「个d20」「难度DC15」处不成立，因此使用拉丁字符 lookbehind 而非词边界。

第二层为语义 Validator Agent：

- 是否替 DM 决定 NPC、环境或规则结果；
- 是否把未知内容写成事实；
- 是否泄露不可见信息；
- 是否漏标 DM 裁决；
- 是否违反可观察内容原则。

Validator 只读取被选角色自己的过滤后 Context。它只能通过、要求等待或退回重试，不能替角色重写正文。

校验失败按三级降级处理，不中断跑团：

```text
候选未通过
→ 携带失败原因让同一角色重新生成一次
   → 仍未通过 → 丢弃该候选，顺延到 rank 的下一个
      → 全部候选耗尽 → 按 ALL_SILENT 结束，Runtime 回到 IDLE
```

只有全部模型调用都失败时才进入 ERROR。全部候选被拦下时，Runtime 记录 `CHARACTER_MESSAGE_REJECTED` 错误码与原因，前端显示为非阻塞提示条而非阻断式错误——此前一次校验失败会把整个 Campaign 打入 ERROR 并丢弃全部并行候选，一句含数字的台词就足以卡死跑团。

第二层语义 Validator Agent 尚未实现，当前只有确定性规则层。

### 5.6 WAITING_FOR_DM

NARRATIVE 模式下发布声明了 `requires_dm_resolution` 的 Character Message 后：

- 消息正常提交；
- Campaign 的内部 Runtime 进入 `WAITING_FOR_DM`；
- 保存触发消息与角色的 Resolution Request；
- 当前 AgentRun 正常结束；
- 不创建后继 Character AgentRun；
- 事务提交后自动启动 AI DM `CHARACTER_REPLY` 草稿生成。

未声明裁定的 Character Message 不进入该路径，而是照常创建后继 Character AgentRun。

草稿生成过程不修改 Runtime 状态。`WAITING_FOR_DM` 此时承载的是角色真实的提问，草稿完成或失败都不得清除它——早期实现会在草稿结束时把 Waiting Message 与 Request 一并清空，从而抹掉真人 DM 需要看到的那个问题。

真人发布审核后的 AI DM 草稿，或手动发送新的 IN_GAME DM 消息后，以该消息创建全新的 Character AgentRun。草稿生成本身不修改 Runtime 状态：此时的 `WAITING_FOR_DM` 承载的是角色原话提出的裁定请求，草稿成功或失败都必须原样保留。

### 5.7 DM 抢占

`session_runtimes.generation` 和 `active_agent_run_id` 共同决定发布权。

以下操作使 Generation 加一：

- DM 发送新消息；
- DM Stop；
- OOC 修订；
- Campaign 暂停；
- Campaign 完成、重置或删除。

提交 AI 消息前必须在事务中验证：

```text
run.generation == runtime.generation
AND run.id == runtime.active_agent_run_id
AND campaign.lifecycle_status == ACTIVE
```

即使供应商请求不能及时取消，迟到结果也无法发布。

### 5.8 AI DM 输出与运行边界

AI DM 使用独立 Pydantic 结构：

```python
class DmDecision:
    content: str
    audience: Literal["PUBLIC", "PRIVATE"]
    recipient_character_ids: list[str]
    improvised_notes: list[str]           # AI 在真人 DM 原话之外添加的内容
```

`improvised_notes` 是"允许 AI 替 NPC 接话并补充环境细节"这一授权的配套安全阀：放宽创作自由只有在核对成本足够低时才成立，因此模型必须逐条声明自己添加了什么，而不是把它埋进散文里。该字段随草稿持久化并在前端草稿下方单独展示。

Agent 返回值只写入 `dm_drafts`，没有调用 Message Service 或随机数生成器的能力。`content` 最多 800 字符；Prompt 要求通常为 1～4 句、目标不超过 300 个中文字符，模型生成上限为 900 Tokens。私密草稿最多指定 6 个角色；开场草稿强制为 PUBLIC。真人编辑后的正文最多 1200 字符。

模型给出的收件角色 ID 会与当前阵容取交集，非法 ID 直接剔除。若一个都不剩，草稿保持 PRIVATE 且收件人为空，由真人 DM 补选；**任何情况下都不因 ID 错误把 PRIVATE 降级为 PUBLIC**。此前的静默降级会把只给一个角色的秘密变成全体公告，且界面上没有任何痕迹。

AI DM 使用独立于 Character Agent 的模型配置 `AI_TRPG_DM_MODEL`，未设置时回落到 `AI_TRPG_CHARACTER_MODEL`。AI DM 承载模组、NPC 卡片与完整近期日志，通常需要比角色更强的模型。

`DmDecision` 不对第一、第二人称代词执行硬校验。AI DM Context 已提供当前阵容姓名和可见身份，模型可按自然语境使用代词；未知人物仍使用明确身份称呼，且不得泄露尚未相识角色的真实姓名。

AI DM 支持四种触发类型：

```text
OPENING
CHARACTER_REPLY
SKILL_CHECK_RESULT
MANUAL_ASSIST
```

- `OPENING`：在 PREPARATION 阶段由真人请求，只要求模组大纲，并读取阵容与已有角色关系；Campaign 名称属于产品元数据，不是额外的 AI DM 创作输入；
- `CHARACTER_REPLY`：非战斗模式下，每条正式 Character Message 发布后由系统自动触发；
- `SKILL_CHECK_RESULT`：真人确认检定结果后触发对应结果叙事；
- `MANUAL_ASSIST`：真人用最简单的语言写下想回什么，或给出一段回复初稿，要求 AI 保留其全部意图与信息并补上氛围、NPC 语气和画面。支持 `POLISH` / `EXPAND` / `REWRITE` 三种模式。

四种触发类型共享同一个上下文构建入口，唯一差别是是否包含真人 DM 的草稿，以及任务段落使用自动起草版还是润色版。此前三条路径各自手写上下文（OPENING 一套 JSON、CHARACTER_REPLY 另一套、MANUAL_ASSIST 是纯字符串拼接），字段命名互不一致，且 `MANUAL_ASSIST`——真人最需要帮助的那条路径——完全没有对话历史。

`CHARACTER_REPLY` 发布事务会提高 Character Runtime Generation、取消尚未发布的角色候选，并进入 `WAITING_FOR_DM`；事务提交后再启动 AI DM Draft Supervisor。草稿生成中和 READY 草稿等待审核时不得继续自动发布 Character Message。AI DM Draft Supervisor 使用独立 asyncio Task Registry，不在数据库事务中等待模型。

`MANUAL_ASSIST` 不是主流程依赖；没有手动提示时，OPENING 和 CHARACTER_REPLY 必须仍可独立生成完整草稿。手动辅助生成前同样抢占未发布 Character Run。

每次新的正式 Character Message 到达时，服务端先把同一 Campaign 中所有未发送的非开场 `GENERATING/READY/DRAFT` 草稿标记为 `STALE`，再创建新的 `CHARACTER_REPLY` 草稿。同一触发消息保持幂等。旧模型请求即使稍后返回，也必须重新读取草稿状态，不能覆盖 `STALE` 或更新后的草稿。成功或失败后，若本次任务仍拥有当前等待消息，则清除 Runtime 的 Waiting Message/Request 并恢复 `IDLE`。显式丢弃使用持久化 `DISCARDED` 状态。

### 5.9 AI DM 重启恢复

进程重启后不重放未知状态的供应商请求。所有 `GENERATING` Draft 标记为 `FAILED/INTERRUPTED`；READY、STALE、SENT 和 DISCARDED 保持不变。DM 可以显式重新生成。

### 5.10 Relationship Agent

每条正式 `IN_GAME` DM 或 Character Message 提交后，Relationship Service 自动执行一次 Campaign 级刷新，并在下一次 Character Agent 或 AI DM 草稿构建上下文前完成。DM 没有创建或编辑关系的入口，只能读取自动生成结果。

每一对角色只获得双方 Recipient Snapshot 的交集消息、既有关系历史和共同参与信息。Agent 只有在明确见面、交谈、相互识别或共同参与事件时才能建立关系；只被一方看见的私密故事不能成为双方关系事实。关系为全局、对称记录，保存首次相识 Campaign 和定性的共同经历历史，不保存数值好感度。

OOC 修订后按 Effective Message 重新计算。如果被修订后的共同故事不再支持本 Campaign 中刚建立的关系，系统可以移除该关系；其他 Campaign 已形成的历史不能被当前修订误删。关系刷新完成后再发出消息变更通知，使前端读取到一致的新关系。

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

负责全局角色、Roleplay Prompt、说话范例、头像、Max HP、十八项技能加值、当前角色卡版本、长期记忆、成长档案、自动关系的只读展示和角色导出。

不负责当前 Campaign HP、消息、检定历史或 Agent 调度。

### 7.1.1 Character Relationship

负责全局对称角色关系、首次相识 Campaign、共同经历历史、消息发布后的自动刷新和 OOC 后重新计算。关系只能由故事派生，API 和前端均不提供 DM 手工新增或修改能力。

### 7.2 Character Sheet

负责固定 Excel 模板校验、解析预览和版本激活。解析结果保存为整体 JSON Snapshot；解析失败的新版本不能替换旧有效版本。

### 7.3 Campaign

负责 `PREPARATION/ACTIVE/PAUSED/COMPLETED` 生命周期、归档、Membership、唯一 ACTIVE Campaign、中途加入、暂停、继续、完成、重置和永久删除。

Campaign 状态变化通过显式 Command Service 完成，不允许通用 PATCH 任意写状态。

### 7.4 Campaign Runtime Record

数据库暂时保留 `sessions` 表作为 Campaign 的一对一内部运行记录，负责 Message Sequence、HP Snapshot、Runtime 和连续 AI 消息数。它不再拥有用户可见的创建、结束或切换生命周期。

### 7.5 Message 与 OOC

负责消息、可见范围、Recipient Snapshot、不可修改正文、Correction 关系以及 UI、Agent、Summary 和 Export 使用的统一有效消息规则。

### 7.6 Runtime

负责 AgentRun、进程内 Task Supervisor、LangGraph、并行角色判断、发言排序、校验、有限重试、原子发布、WAITING_FOR_DM、Stop 和错误恢复。

### 7.7 AI DM Draft

负责模组大纲存储、NPC 卡片提取与维护、开场草稿、角色回复自动触发、统一的 AI DM Context、手动润色辅助、简短结构化草稿、AI 自行添加内容清单、公开/私密接收者、草稿替换、乐观编辑、过期检查、持久化丢弃和人工发布。AI DM Supervisor 与 Character Runtime Supervisor 分离，不能直接创建正式消息。

### 7.8 Skill Check

负责十八项技能加值、后端 D20、优势/劣势、DC 结果、DM 手工裁决、不可变历史和作废标记。随机数只在收到真人 DM 确认命令后生成。

### 7.9 Context 与 Memory

负责角色级可见消息查询、OOC 修订投影、当前 Campaign 完整可见故事、全部已结束 Campaign 的角色故事摘要、自动关系、长期记忆、定性健康状态和成长档案重建。Character Agent 的连续性输入不得只取最近固定条数或最近少数 Campaign。

### 7.10 Export

负责 Campaign ZIP 和 Character Export。导出必须使用同一个 Effective Message Projection，不得单独实现 OOC 规则。

### 7.11 Debug

负责显示 Run ID、触发事件、调用角色、SILENCE/RESPOND、排序、模型、Token、耗时、重试和错误码。

默认不保存完整 Prompt、私密 Context、Chain of Thought 或未发布候选正文。

## 8. 数据模型设计

### 8.1 实体关系

```text
characters
  ├── character_sheet_versions
  ├── character_skill_sets
  ├── character_profiles
  ├── character_memories
  ├── character_acquaintances（有序角色对）
  └── campaign_memberships ── campaigns
                                └── sessions (内部一对一运行记录)
                                     ├── session_character_states
                                     ├── session_runtimes
                                     ├── messages
                                     │    ├── message_recipients
                                     │    └── message_corrections
                                     ├── dm_drafts
                                     ├── skill_checks
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
- `voice_samples`：3～5 组「情境 → 这个角色会怎么说」的示例台词，与 Roleplay Prompt 一同进入该角色的系统提示词；
- `narration_notes`：叙述必须遵守的用词约定，优先级高于角色卡快照。同时进入该角色自己的系统提示词和 AI DM 的 `<队伍>` 段，使两个 Agent 对同一事物的称呼一致；
- `avatar_path`；
- `max_hp`；
- `active_sheet_version_id`；
- `revision`；
- `created_at`、`updated_at`。

#### `character_acquaintances`

以 `character_a_id + character_b_id` 为联合主键，并通过 `character_a_id < character_b_id` 保证同一角色对只有一条对称记录。保存 `met_campaign_id`、`relationship_history`、Created At 和 Updated At。`met_campaign_id` 在 Campaign 删除后置空，关系历史仍属于全局角色资产。该表只允许 Relationship Service 写入，对外仅提供只读查询。

`revision` 用于多标签页编辑时的乐观并发检查。

#### `character_skill_sets`

每个 Character 一行，保存固定十八项技能的最终加值 JSON、Revision 和 Updated At。API Schema 必须验证键集合完整且没有额外技能；所有修改原子替换整组数值。Skill Check 保存投掷时的 Modifier Snapshot，历史不引用当前值回算。

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
- `PREPARATION/ACTIVE/PAUSED/COMPLETED`；
- `play_mode`：`NARRATIVE/COMBAT`；
- `scene_notes`；
- `archived_at`；
- Revision 和内部时间。

SQLite Partial Unique Index 保证全站只有一个 ACTIVE Campaign：

```sql
CREATE UNIQUE INDEX ux_campaign_single_active
ON campaigns(lifecycle_status)
WHERE lifecycle_status = 'ACTIVE';
```

#### `campaign_memberships`

联合主键为 `campaign_id + character_id`，并保存加入时间和加入消息边界。旧 `joined_session_id` 不再参与认知判断，后续迁移移除。

实际认知边界不依赖时间推导，而依赖每条消息的 Recipient Snapshot。

#### `sessions`

作为兼容现有外键的内部运行容器，保存 Campaign、下一个 Message Sequence 和内部时间。`campaign_id` 使用无条件唯一约束，保证每个 Campaign 最多一行；前端和公开 API 不暴露 Session 创建、结束或切换能力。Campaign 首次启动时自动创建，Campaign 删除时级联删除。

#### `session_character_states`

联合主键为 `session_id + character_id`，保存：

- `current_hp`；
- `max_hp_snapshot`；
- `updated_at`。

Agent 不读取这些整数，只读取 Health Status Policy 输出的定性状态。

#### `session_runtimes`

每个 Campaign 的内部运行记录一行：

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
- `addressed_character_ids` JSON：这条消息说给谁听，由 DM 发送时勾选或从发布角色的候选继承；
- Client Request ID；
- Origin AgentRun；
- Created At。

约束：

- `UNIQUE(session_id, sequence_no)`；
- `client_request_id` 防止标签页或网络重复提交；
- AI 候选只有成功发布后才创建 Message；
- `addressed_character_ids` 必须是该消息 Recipient 的子集：看不到消息的角色不可能被它点名。

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

物理表名暂时保留，语义改为 Campaign Character Summary；按内部运行记录、Character 和 `ROLLING/FINAL` 唯一，保存内容、状态、Revision 和 `DM/SYSTEM` 更新来源。

#### `dm_session_summaries`

物理表名暂时保留，语义改为 Campaign DM Summary；每个内部运行记录一行，只供 DM、AI DM 和 Export 使用。任何 Character Context Repository 都不得引用该表。

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

#### Campaign 模组字段

当前实现直接在 `campaigns` 保存 `module_content`，并兼容既有 `dm_guide`；筹备 UI 和 AI DM 的必填创作输入只有模组大纲。`scene_notes` 可在战役进行中作为可选补充；`style_instructions`、`opening_instructions` 等兼容字段不再构成筹备前置条件。模组只进入 AI DM Context，不进入任何 Character Context。

#### `dm_drafts`

物理表名为 `campaign_dm_drafts`。保存 Campaign、可空的内部运行记录、触发类型 `OPENING/CHARACTER_REPLY/SKILL_CHECK_RESULT/MANUAL_ASSIST`、触发消息、来源检定、可选 Prompt（真人 DM 的粗稿或叙事意图）、正文、可见范围、`recipient_character_ids` JSON、`improvised_notes` JSON、状态、Revision 和时间。

状态为：

```text
GENERATING / READY / DRAFT / STALE / SENT / DISCARDED / FAILED
```

OPENING 草稿生成时 Campaign 仍为 PREPARATION，因此 `session_id` 可以为空；发布开场时才创建唯一内部运行记录并回填关联。每条新的 Character 回复会把所有未发送的非开场 `GENERATING/READY/DRAFT` 草稿标记为 STALE；STALE 草稿不能发布。接收者列表在草稿阶段规模有界（最多 6 人），因此保存在 JSON；正式发布时仍由 Message Service 校验并写入规范化 `message_recipients` 快照。

#### `campaign_npcs`

每个 Campaign 一组具名 NPC 卡片。字段为 `campaign_id`、`name`、`role`、`personality`、`ideal`、`bond`、`flaw`、`knows`、`wants`、`voice`、`source`、`revision` 和时间，并对 `(campaign_id, name)` 建唯一索引。

`source` 取 `AUTO` 或 `DM`。筹备阶段由 NPC 提取 Agent 一次性从模组正文生成 `AUTO` 卡片；真人 DM 创建或编辑过的卡片标记为 `DM`，重新提取时不被覆盖，重新提取只刷新 `AUTO` 卡片并删除模组中已不再出现的 `AUTO` 卡片。

提取 Agent 使用低温度并被要求只填模组原文明确写出的内容，未写明的字段留空。NPC 卡片只进入 AI DM Context，不进入任何 Character Context。

#### `skill_checks`

保存 Character、技能、Modifier Snapshot、普通/优势/劣势、全部原始 D20、采用值、总值、DC、结果、原因、来源草稿、Client Request ID、`VALID/VOID` 状态、作废原因和时间。记录只追加；作废不能修改原始骰子字段。

## 9. 关键事务

### 9.1 DM 发送消息

一个事务内：

1. 校验 Campaign 为 ACTIVE，并解析唯一内部运行记录；
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

1. 比较 Generation、Active Run，并确认 Campaign 为 ACTIVE；
2. 写入最终 Message、Recipients 与点名列表；
3. 完成当前 Run；
4. 更新连续 AI 数；
5. 角色声明裁定，或向世界提问的确定性兜底命中，则进入 WAITING_FOR_DM 并保留角色原话的等待事项；
6. 达到 `MAX_CONSECUTIVE_AI_MESSAGES` 上限则进入 IDLE；
7. 否则创建后继 AgentRun，其候选集合排除本条消息的发送者；
8. 叙事模式下，第 5、6 步以及全员沉默都会在事务提交后触发 AI DM 草稿。

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

### 9.5 Campaign 暂停与继续

暂停事务确认 Campaign 为 ACTIVE，Generation 加一，取消 Active Run，把正在生成的 AI DM Draft 标记为 FAILED/INTERRUPTED，保留 READY Draft 和 WAITING_FOR_DM，然后把 Campaign 改为 PAUSED。事务提交后再更新滚动摘要，摘要失败不回滚暂停。

继续事务确认 Campaign 为 PAUSED 且没有其他 ACTIVE Campaign，然后恢复为 ACTIVE。继续不创建新内部运行记录，不重置状态，也不自动重放暂停前被取消的 Character Run。

### 9.6 AI DM 草稿生成与发布

#### 开场草稿

PREPARATION 阶段只校验阵容、模组大纲和 AI DM 配置后创建 `OPENING + GENERATING` Draft；事务外调用模型。开场 Context 使用模组大纲、阵容和已有角色关系，输出强制 PUBLIC。返回时确认 Campaign 仍为 PREPARATION 且 Draft 仍为当前任务，否则标记 STALE。

开场发布使用单一事务：校验 Draft 为 `OPENING + READY` 且 Revision 匹配；确认没有其他 ACTIVE Campaign；创建 Campaign 唯一内部运行记录和 HP Snapshot；把 Campaign 改为 ACTIVE；将草稿正文作为 Sequence 1 的 PUBLIC DM Message 发布；把 Draft 标记为 SENT 并关联运行记录。任一步失败均不得产生半启动 Campaign 或孤立开场消息。

#### 角色回复自动草稿

正式 Character Message 的发布事务确认 `play_mode = NARRATIVE` 后，提高 Character Runtime Generation、取消其他未发布候选并进入 WAITING_FOR_DM。提交后先将所有未发送的非开场草稿标记为 STALE，再为最新消息创建一个 `CHARACTER_REPLY + GENERATING` Draft；同一来源消息的重复触发保持幂等，不要求前端再发送“生成草稿”命令。

模型返回后重新读取 Draft，确认 Campaign 仍为 ACTIVE 且为 NARRATIVE、Draft 仍为当前生成任务、触发 Character Message 仍有效；不满足时不得写回迟到结果。READY 或 FAILED 后通过 SSE 通知前端。若本次任务仍对应 Runtime 当前等待消息，同时清除 Waiting Message/Request 并恢复 `IDLE`，避免草稿生成结束后卡在旧等待状态。

#### 手动辅助与普通发布

`MANUAL_ASSIST` 接受真人 DM 的粗稿或一句叙事意图，以及 `POLISH/EXPAND/REWRITE` 模式。Context Builder 始终补入模组、场景笔记、NPC 卡片、带发送者姓名与可见范围的最近对话和最新正式角色回复；手动输入只是追加的一段，不能替代这些权威上下文。生成前使用现有 Generation 机制取消未发布 Character Run，并使同水位旧 READY 草稿变为 STALE。

发布事务校验 Draft 为 READY、Revision 匹配且未过期；PRIVATE 时校验 1～6 个接收者均为当前 Campaign 成员，然后复用 Message Service 创建正式 DM Message、Recipient Snapshot 和后继 AgentRun，并把 Draft 标记为 SENT。显式丢弃把草稿持久化为 DISCARDED，之后不会重新出现在待发送列表中。数据库事务中不等待模型。

### 9.7 Skill Check

投骰事务必须携带唯一 Client Request ID，并由真人 DM 命令提供最终 Character、Skill、Roll Mode、DC 和原因。后端读取当前 Modifier，使用 `secrets.randbelow(20) + 1` 生成一颗或两颗 D20，保存所有原始值和快照后提交。AI DM 无法调用该内部随机函数。

有 DC 时系统计算 `total >= dc`；无 DC 时结果保持 UNRESOLVED，必须由 DM 追加 `SUCCESS/FAILURE/PARTIAL_SUCCESS` 裁决后才能生成结果叙事。该裁决不修改骰子字段。

### 9.8 Campaign 完成

先在事务内完成 Campaign、取消所有 Runtime、保存最终 HP 并创建 PENDING Summary/Memory 状态；事务外再调用 LLM。单项失败不回滚 Campaign 完成。

### 9.9 Campaign 重置或删除

事务内先删除 Campaign 来源 Memory、清空并禁用受影响的系统生成 Profile，再删除 Campaign 及其内部运行数据；事务提交后根据剩余 Memory 重建 Profile。

## 10. Context 与 Memory

### 10.1 唯一入口

Prompt 与 Context 的组装从 Runtime 与 Service 中分离出来，放在专门的模块里，使措辞可以被评审、被版本化、被离线回归测试，而不必牵动数据库或调度代码：

```text
backend/app/agents/character_prompt.py   # PROMPT_VERSION = "character/v2"
backend/app/agents/dm_prompt.py          # PROMPT_VERSION = "dm/v2"
```

角色侧提供 `build_system_prompt()` 与 `build_context()`；AI DM 侧提供 `compose_system_prompt()` 与 `build_context()`。Character、Summary 和 Memory Agent 都必须通过该入口获取角色数据。

### 10.2 构建顺序

角色的**身份**进入该角色专属的系统提示词，**世界状态**进入用户消息。二者不能混同：早期实现把整个 payload 做 `json.dumps`，Roleplay Prompt 沦为与"小队健康状态"平级的一个字典键，其 Markdown 结构也被压平，模型因此把人设当参考资料而非自身身份，所有角色收敛为语气相同的中性助手。

系统提示词（按角色动态构造）：

```text
入戏引导
→ <你是谁>        Roleplay Prompt 原文，Markdown 结构逐字保留
→ <你会怎么说话>   Voice Samples
→ <你后来变成了什么样>  Development Profile
→ <用词约定>      Narration Notes，声明其优先于能力与装备
→ <硬性边界>      8 条越界约束，含"不得重复他人已说内容"
→ <你要输出什么>   inner_beat、长度、身体反应、禁破折号、SILENCE、可见范围
```

`inner_beat` 的提问从"此刻的反应是什么"扩展为三问：别人刚才已经说了什么、此刻真实的反应是什么、要说的是否与他人重复。第三问把去重从一条容易被忽略的禁令变成生成前必须回答的问题。

上下文（XML 分段，不再整体 JSON 序列化）：

```text
<你的能力与装备>            Sheet Snapshot 压缩为可读文本
→ <你记得的事>              Long-Term Memory，受字数预算约束
→ <你和他们之间>            自动生成的关系与共同经历
→ <你以前经历过什么>        按时间排序的已结束 Campaign 故事摘要
→ <你身边的人现在什么状态>  定性 Health View
→ <注意>                    陌生人编号约束
→ <刚刚发生了什么>          最近若干条 Effective Messages
→ <你要回应的是这一句>      Trigger Message，单独成段、置于末尾
```

Trigger Message 必须从历史中摘出单独成段。作为消息数组的最后一项时它没有任何标记，角色只能猜自己该对哪一句反应。OOC 触发时该段替换为 `<出戏更正>`，并注明这不是场内发生的事。

空的段落不产生空标签：首次开团时角色卡、记忆、关系与既往战役均为空，上下文只剩触发消息本身，全部重量落在系统提示词上。

这三类连续性数据分别对应“角色是谁”（Roleplay Prompt 与 Voice Samples）、“与其他人发生过什么”（动态关系）和“此前经历过什么”（完整故事）。

预算与选取规则：

- Long-Term Memory 按「固定 → 当前 Campaign → 最近」排序后按字数预算截断，实现 10.4 的 Memory Selector；此前只有一句 `limit(20)` 按固定标记与更新时间排序，跑过几个战役后早期关键记忆会被时间戳挤掉；
- 当前 Campaign 消息取最近若干条，触发消息本身从中排除；
- Sheet Snapshot 只保留种族、职业、背景、语言、已选能力与法术名及简短描述、关键装备，丢弃全部解析元数据；整份 Snapshot 直接倾倒会用数千 Token 的参考资料淹没人设。

已结束 Campaign 的故事摘要仍然全量保留。Campaign 完成时生成故事摘要不按条数或字符截断输入；若未来因供应商上下文上限必须压缩，应使用可审计的分段归并，而不是静默丢弃较早故事。

### 10.3 AI DM Context

AI DM 使用独立入口，不复用按角色过滤的 Context。全部触发类型共用同一个构建函数：

```text
<模组内容>        权威剧情来源，超长时按字数预算截断并注明
→ <场景笔记>      可选
→ <出场人物>      NPC 卡片；卡片外的具名 NPC 不得创造
→ <队伍>          角色姓名与 ID（PRIVATE 收件人从这里选）
→ <角色相识状态>
→ <最近对话>      [可见范围] 发送者姓名：正文
→ <检定结果>      可选，标注结论不可更改
→ <角色请求裁定>  可选
→ <最新角色回复>
→ <DM 的草稿>     仅润色路径存在
```

`<最近对话>` 每条都带发送者姓名与可见范围。此前这里是 `{"sender": "CHARACTER", "content": ...}`——`sender_type` 只有 `DM/CHARACTER/SYSTEM` 三值，没有姓名也没有可见范围，AI DM 面对一串匿名 `CHARACTER` 无从维持 NPC 一致性与剧情连贯。

系统提示词由三段拼接而成（不使用 `str.format`，因为主持风格是任意用户文本，可能包含花括号）：忠于模组的硬规则 + 可选的主持风格 + 任务段落。任务段落按是否存在 `<DM 的草稿>` 二选一：自动起草版要求根据最新角色回复推进场景；润色版要求保留真人 DM 的全部意图与信息，只补氛围、NPC 语气和画面。

忠于模组的硬规则包括：模组内容 > 场景笔记 > 最近对话；不得新增模组中没有的具名 NPC、地点或情节转折（无名路人除外）；不得改写模组已写定的事实；不得投骰或宣布检定成败；已给出结论的检定只能写对应叙事。此前 AI DM 的提示词中关于剧情忠实度一条都没有。

AI DM 不在检定前读取角色技能加值，避免模型根据成功概率代替 DM 调整规则裁决。

OPENING Context 不包含尚不存在的消息时间线，只包含模组大纲、不含私密 Prompt 的阵容信息和已有角色关系，不要求主持风格或开场说明。CHARACTER_REPLY Context 必须明确标记最新触发消息；未发布 Character Candidate、其他 AI DM Draft 和草稿编辑历史不得进入 Context。

AI DM 初版不使用向量检索，当前实现整篇注入模组正文。当模组规模增长到注入全文不再合理时，应引入结构化的地点与线索模型，只注入当前场景及相邻场景，并把剧情进度显式建模为状态而非让模型每轮从原文重新推断；该方向记录在 `DM_AGENT_DESIGN.md`，尚未实现。AI DM Prompt 同时给出简短输出和 PUBLIC/PRIVATE 接收者规则。

### 10.4 Memory Selector

MVP 不使用向量数据库。定义可替换接口，初版按以下顺序选择：

1. Pinned Memory；
2. 当前 Campaign Memory；
3. 最近未固定 Memory；
4. 在 Token Budget 内截断。

未来可以替换为 Embedding 或混合检索，而不改变 Character Agent 接口。

### 10.5 Health View

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
POST   /api/v1/campaigns/{id}:pause
POST   /api/v1/campaigns/{id}:resume
POST   /api/v1/campaigns/{id}:complete
POST   /api/v1/campaigns/{id}:reset
DELETE /api/v1/campaigns/{id}
GET    /api/v1/campaigns/{id}/play
GET    /api/v1/campaigns/{id}/acquaintances
POST   /api/v1/campaigns/{id}/messages
POST   /api/v1/campaigns/{id}/messages:ooc
POST   /api/v1/campaigns/{id}/runtime:stop
POST   /api/v1/campaigns/{id}/runtime:retry
POST   /api/v1/campaigns/{id}/dm-drafts
GET    /api/v1/campaigns/{id}/dm-drafts
POST   /api/v1/campaigns/{id}/dm-drafts:generate-opening
PATCH  /api/v1/dm-drafts/{id}
POST   /api/v1/dm-drafts/{id}:publish
POST   /api/v1/dm-drafts/{id}:discard
GET    /api/v1/characters/{id}/skills
PUT    /api/v1/characters/{id}/skills
GET    /api/v1/campaigns/{id}/skill-checks
POST   /api/v1/campaigns/{id}/skill-checks
POST   /api/v1/skill-checks/{id}:adjudicate
POST   /api/v1/skill-checks/{id}:void
POST   /api/v1/skill-checks/{id}/dm-draft:generate
GET    /api/v1/campaigns/{id}/events
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
dm_draft.changed
dm_draft.failed
skill_check.created
skill_check.adjudicated
skill_check.voided
```

Payload 只带必要 ID 和 Revision，不广播私密正文。前端收到 `dm_draft.changed/failed` 后使草稿查询失效；收到 `message.created` 或有效消息变化后同时使关系查询失效。Relationship Service 在消息事件发出前完成刷新，因此重新读取时不会看到旧关系。

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
- 模型分别配置：`AI_TRPG_CHARACTER_MODEL`、`AI_TRPG_DM_MODEL`、`AI_TRPG_RELATIONSHIP_MODEL`、`AI_TRPG_SUMMARY_MODEL`；`AI_TRPG_DM_MODEL` 未设置时回落到 `AI_TRPG_CHARACTER_MODEL`，既有 `.env` 无需改动；
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
- JSON 只保存 Character Sheet Snapshot、草稿阶段最多 6 人的接收者列表等整体读取且有界的结构；
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
- Character Prompt 要求一句台词、一个动作或「一个动作 + 一句台词」，目标 80 个中文字符以内，并由 Schema 再执行 240 字符硬限制；长度要求在 Prompt 中只出现一次；
- AI DM Prompt 固定要求 1～4 句、目标不超过 300 个中文字符，并输出 PUBLIC/PRIVATE 与接收者；
- Relationship Prompt 只能依据双方共同可见的完整有效故事，不得把单方私密信息推断成共同关系；
- Character 与 AI DM Prompt 允许自然使用第一、第二人称，并要求在指代不清或角色尚未相识时使用隐私过滤后的明确称呼；
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
- Campaign 暂停与 Character AI 提交竞争时，AI 提交失败；
- Campaign 暂停、继续后沿用同一 Message Sequence、HP 和 WAITING_FOR_DM；
- 同一个 Campaign 不能创建第二条内部运行记录；
- AI DM Draft 未经发布命令不会创建 Message；
- OPENING Draft 在 PREPARATION 生成时不会创建内部运行记录或正式消息；
- 发布 OPENING Draft 会原子地激活 Campaign，并且只创建一条 Sequence 1 消息；
- NARRATIVE 模式下正式 Character Message 会自动且仅触发一个 CHARACTER_REPLY Draft；
- CHARACTER_REPLY Draft 生成和等待审核期间，后续 Character Candidate 不能发布；
- COMBAT 模式下正式 Character Message 不触发 AI DM Draft；
- MANUAL_ASSIST 缺失时自动开场与角色回复草稿仍正常工作；
- MANUAL_ASSIST 必须同时读取模组和最新角色回复，并且只能写入 Draft；
- 新消息会使旧 READY Draft 变为 STALE，STALE Draft 不能发布；
- 重复 Client Request ID 只产生一次投骰；
- 优势取两颗 D20 较高值，劣势取较低值，且两颗原始值都保留；
- 修改当前技能加值不改变历史 Modifier Snapshot；
- 无 DC 且没有 DM 裁决的 Skill Check 不能生成结果叙事；
- Skill Check 和 AI DM Draft 永不进入 Character Context。
- Character Context 同时包含 Roleplay Prompt、自动关系、全部已结束 Campaign 摘要和当前完整可见故事；
- Character Agent 超过 240 字符、AI DM 超过 800 字符时结构校验失败；
- 关系在角色明确见面或共同参与后自动建立，并在后续共同故事后自动更新；
- 仅一方可见的 PRIVATE/DM_ONLY 消息不会建立双方关系；
- OOC 移除本 Campaign 的相识依据后，自动关系重新计算且不会误删其他 Campaign 的既有关系；
- 新角色回复会使所有未发送的非开场 GENERATING/READY/DRAFT 草稿失效并生成新草稿；
- 同一角色消息重复触发只生成一份草稿，旧并发模型结果不能覆盖 STALE 草稿；
- 草稿成功、失败或丢弃后不会让 Runtime 卡在旧 Waiting Message；
- PRIVATE DM 草稿只能发布给 1～6 个当前成员，未选角色的 Recipient Snapshot 中不存在该消息；
- CharacterDecision 的正文和裁决请求允许第一、第二人称代词；
- DmDecision 正文允许第一、第二人称代词；
- 代词使用不能绕过 Recipient 隔离或陌生角色姓名脱敏规则；

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

## 16. 一次性数据清理与迁移顺序

本次从多 Session 模型迁移到 Campaign 连续时间线时，不保留现有 Campaign 历史，也不实现 Session 合并器。数据清理必须由显式的一次性命令执行，不能在应用启动时隐式发生。

### 16.1 保留与删除范围

保留：

- Character 基础资料、Roleplay Prompt、头像和 Max HP；
- 当前有效 Character Sheet 及上传文件；
- DM 手工添加的 Character Memory；
- DM 手工维护的 Character Profile；
- 新的十八项技能加值。

删除：

- 全部 Campaign、Membership 和内部 Session；
- Message、Recipient、OOC、HP Snapshot、Runtime 和 Agent Run；
- LLM Invocation、Campaign Summary、AI DM Guide、Draft 和 Skill Check；
- 所有带 Campaign 来源的 Character Memory；
- Campaign 导出文件。

由系统根据旧 Campaign 生成的 Character Profile 必须清空并设为 NEEDS_REBUILD；DM 手工编辑的 Profile 保留。角色头像和 Character Sheet 文件不得删除。

### 16.2 执行顺序

1. 停止后端进程并备份 SQLite 数据库；
2. 运行带明确确认参数的一次性 Campaign 数据清理命令；
3. 校验 `campaigns`、`sessions`、`messages`、`agent_runs` 和 Campaign 来源 Memory 数量均为零；
4. 执行 Alembic Schema Migration；
5. 为 `sessions.campaign_id` 建立无条件唯一约束；
6. 新增 PAUSED、Campaign DM Guide、Skill Set、Skill Check 和 DM Draft 结构；
7. 放宽并校验 `llm_invocations` 的归属关系，使 Character Run 和 DM Draft 调用恰好关联一种来源；
8. 重新生成 OpenAPI 和前端 DTO；
9. 运行迁移、集成、并发和隐私测试。

清理命令必须输出删除数量摘要，不打印正文；失败时整个数据库事务回滚。数据库备份和导出文件清理由独立步骤完成，不能让 Alembic Migration 操作仓库外任意路径。
