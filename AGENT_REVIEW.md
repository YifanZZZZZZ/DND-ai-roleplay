# AI TRPG — Agent 层问题复盘

阅读范围：`PRD.md`、`ARCHITECTURE.md`（第 5 / 10 章重点）、`backend/app/agents/*`、`backend/app/runtime/*`、`campaign_service` / `dm_draft_service` / `relationship_service` / `summary_service` / `skill_check_service` / `entities.py` / `enums.py`，以及你提供的「卡莱拉」roleplay prompt 范例。

结论先行：这套代码的**工程骨架（状态机、generation 抢占、隐私快照、草稿生命周期）质量相当高**，问题几乎全部集中在 **Agent 的上下文构建（Context）和提示词工程（Prompt）** 这一层——也就是 ChatGPT 最容易写成"能跑但没灵魂"的部分。架构文档里设计得最好的两个东西（`ContextBuilder` 唯一入口、语义 Validator Agent）恰好一个都没实现。

---

## 一、Character Agent 角色扮演差 —— 8 个具体原因

### 1.1 【最致命】人格被降级成 JSON 里的一个普通字段

`supervisor._build_context` 把一切 `json.dumps(payload, indent=2)` 成**一条 user message**，而 system prompt 是模块级常量 `CHARACTER_INSTRUCTIONS`。

于是模型看到的权重分布是：

| 位置 | 内容 | 模型的解读 |
|---|---|---|
| system | 16 条通用禁令 | **这是我的身份** |
| user JSON `"角色扮演指引"` | 卡莱拉的完整人格 | 这是一份参考资料 |

`"角色扮演指引"` 和 `"小队可观察健康状态"`、`"角色相识限制"` 是**平级的字典键**。模型不会把平级字段当成"我是谁"。

更糟的是：你的卡莱拉 prompt 是结构化 Markdown（`# 人格` / `# 说话与外在表现`），`json.dumps` 之后变成一行 `"# 身份\n\n你是【卡莱拉】..."`，标题层级的视觉显著性被彻底压平。

> **修复**：`instructions` 必须**按角色动态构造**，不能是模块常量。结构应为
> `system = 角色扮演指引原文（Markdown 保持原样） + 简短的越界禁令`，
> `user = XML 分段的世界状态`（`<最新触发事件>`…`</最新触发事件>`）。
> 停止对整个 payload 做 `json.dumps`——对 Markdown 人设是净损失。**这一条单独改，效果提升最大。**

### 1.2 禁令压倒人格：16 条规则里 12 条是"不要"

`CHARACTER_INSTRUCTIONS` 通读下来是一份"合规手册"：不要超游、不要提数值、不要复述、不要内心独白、不要铺陈、不要长、不要重复动作、不要输出思考…… 只有第 14、15 条是正向的"要有性格"，且排在最后被淹没。

LLM 在**否定式约束密集**时会稳定收敛到最安全的中性输出——这正是你感受到的"所有角色都像同一个语气相同的助手"。第 14 条自己都写了"不要把所有角色写成语气相同的中性助手"，说明写 prompt 的时候就已经预感到会这样，但解决方式是再加一条禁令，方向反了。

> **修复**：正向描述占主体（"你说话短促、带防御性讽刺，把关心改写成实用理由"），把禁令压缩成一个 5～6 条的 `<硬性边界>` 块放在末尾。

### 1.3 完全没有 few-shot 范例

卡莱拉的 prompt 里全是**抽象行为规则**："会把担心包装成嫌弃、警告、算账"、"被夸奖时故意挑一句不那么重要的毛病回应"。这些描述得很好，但模型从抽象规则生成具体台词时会退回到"平均值"。

> **修复**：`characters` 表加 `voice_samples`（JSON，3～5 组「情境 → 卡莱拉会怎么说」），注入 system prompt 末尾。这是提升 in-character 程度性价比最高的第二件事。

### 1.4 `thinking: disabled` + 强制结构化输出，双杀文学性

```python
output_type=CharacterDecision,          # pydantic_ai → JSON schema / function calling
model_settings={"temperature": 0.75, "max_tokens": 400,
                "extra_body": {"thinking": {"type": "disabled"}}}
```

两个问题：

1. 角色决策（**该不该开口、以什么姿态开口**）恰恰是需要一点推理的任务，`thinking` 被硬关掉。
2. 模型在**填 JSON 字段**时的语言质量显著低于自由文本生成——这是普遍现象，DeepSeek 上尤其明显。`content` 是一堆 schema 字段中的一个，模型在"正确填表"的模式下写台词。

> **修复**：改成两段式——第一次自由文本输出（可带 `<内心>`/`<台词>` 标签），第二次用便宜模型或正则做结构化抽取；或至少把 `thinking` 打开做一次 A/B。

### 1.5 "要短"说了三遍，模型只会更保守

规则 10 里连着三重压缩："通常 1～3 句"+"不超过 120 汉字"+"绝不超过 240 字符"，再叠加规则 11「没有新反应就 SILENCE」、规则 15「不要每条都加神态」。

结果是模型倾向输出**最短的安全句**。而角色魅力恰恰在那一个多余的动作细节里（"拉低兜帽"、"视线扫过出口"）。

> **修复**：放宽到"一句台词 + 一个动作"，字数只在 schema 层硬限制，prompt 里说一次即可。

### 1.6 上下文噪音挤压人格段

`_build_context` 里几个字段是**无节制倾倒**：

- `"角色身份与能力": sheet.parsed_snapshot` —— 整个 Excel 解析出的 dict 原样塞入
- `"当前故事的完整可见记录"` —— 全量消息，**没有任何截断**
- `"完整故事档案"` —— 全部已结束 campaign 的摘要
- `"角色长期记忆"` —— `limit(20)` 按 `pinned, updated_at` 排

人格段在最前面，后面跟着几千 token 的流水账。同时这与 `ARCHITECTURE.md §10.4 Memory Selector` 定义的选择顺序（Pinned → 当前 Campaign → 最近未固定 → Token Budget 内截断）**完全不符**——代码里没有 Memory Selector，只有一句 `limit(20)`。跑几个 campaign 之后，早期的关键记忆会被时间戳挤掉。

### 1.7 "被点名"判定是子串匹配，直接失效

```python
is_directly_addressed=(character.name.casefold() in trigger.content.casefold())
```

但 PRD §3.8 / §2.24 明确鼓励 DM 和角色使用第二人称代词。DM 说「**你们两个先进去**」——匹配不到任何人。

后果：`SpeakerCoordinator` 的第一优先级（被点名）几乎永远不触发，选择规则退化成 `urgency → 最久没发言 → 随机`，也就是**近似轮流发言**。这会让人直观感觉"角色没有主动性、像在排队说话"。

同时：`CharacterDecision.addressed_character_ids` 和 `response_type` 这两个字段**模型输出了，但代码里从来没有被读过**。Coordinator 只看 `is_directly_addressed`。让模型填从不使用的字段，纯粹是浪费输出 token 并干扰生成。

### 1.8 MessageValidator 会误杀有性格的台词，且失败即中断跑团

```python
_mechanical_patterns = (re.compile(r"\d"), ...)
```

`r"\d"` 屏蔽**任何数字**。「我数到三」（阿拉伯数字场景）、「第 2 次了」会被判违规。`_result_claim_patterns` 的负向先行只豁免「尝试/试图」，「我推门，门纹丝不动」这类正常叙述有概率被判成"宣告结果"。

更严重的是失败处理：

```python
run.status = FAILED
runtime.status = RuntimeStatus.ERROR
```

**一次校验失败 → 整个 runtime 进 ERROR，跑团卡住，需要人工重试。**

而 `ARCHITECTURE.md §5.5` 写的是 Validator "只能通过、要求等待或**退回重试**"。现在既没有重试，也没有"换第二候选"（明明并行生成了 N 个候选，全被丢掉了）。

另外 **§5.5 的第二层「语义 Validator Agent」完全没实现**——只有正则层。PRD §6 验收里那些"是否替 DM 决定结果/是否泄露不可见信息"目前没有任何检查。

### 1.9 触发事件没有被标记

`trigger` 只有在 `kind == OOC` 时才单独放进 payload。正常情况下，触发消息只是 `"当前故事的完整可见记录"` 数组的最后一项，**没有任何标记**。模型不知道自己在对哪一句话反应，只能猜"大概是最后一条"。

---

## 二、AI DM 守不住模组 —— 根因是「系统里没有剧情状态」

### 2.1 【根因】没有任何剧情进度的数据结构

数据库里搜遍了：**没有 scene / act / beat / objective 表，没有 `current_scene_id`，没有已完成事件记录。**

`Campaign` 里和剧情有关的只有四个自由文本字段：`dm_guide`、`module_content`、`scene_notes`、`style_instructions`。

`_character_reply_context` 每次都把 **`module_content` 整篇原文** 丢给模型，然后期待它自己推断"我们现在在第几幕、下一个必须发生的事件是什么、哪些线索已经给过了"。这在长模组下必然失控——模型只会顺着最近 40 条对话的语气继续编。

> **修复方向**（这是本项目最值得做的一次架构改动）：
> 1. 开团前用一次 LLM 把模组解析成结构化的 `scenes[] / beats[]`：前置条件、**必须发生的事**、可能分支、出口条件、关键 NPC 与线索。存表，DM 可编辑。
> 2. Runtime 维护 `current_scene_id` + `completed_beat_ids`。
> 3. AI DM 每次只注入：**当前场景全文 + 相邻场景摘要 + 未完成 beat 清单**，而不是模组全文。
> 4. `DmDecision` 增加元信息字段：`advanced_beat_id`、`player_deviated: bool`、`deviation_note` —— 让 DM 能审计"AI 认为剧情走到哪了"，而不是只看到一段散文。这同时解决了 2.7。

### 2.2 DM 上下文里没有滚动摘要

`ARCHITECTURE.md §10.3` 明确要求 DM Context 包含 `DM Rolling Campaign Summary`。`_character_reply_context` 的 payload 里**没有**。只有 `.limit(40)` 的最近消息。跑过 40 条之后，模组前半段发生的事对 AI DM 直接不存在。

而 `SummaryService` 只在 `complete()` 时调用一次——**PRD §3.4「暂停时更新滚动摘要」根本没有实现**（`campaign_service.pause()` 里没有任何 summary 调用）。也就是说滚动摘要这个概念在代码里不存在。

### 2.3 【明确 bug】DM 看不到是谁在说话

```python
"近期正式对话": [{"sender": item.sender_type, "content": item.content} for item in messages]
```

`sender_type` 是枚举，只有 `DM` / `CHARACTER` / `SYSTEM`。**没有角色名字，也没有 audience 标记。**

AI DM 看到的是一串 `{"sender": "CHARACTER", "content": "..."}`——它无法知道是卡莱拉还是别人说的。在这种上下文下要求它维持 NPC 一致性和剧情连贯，是不可能的。

`ARCHITECTURE.md §10.3` 要求的是"**带可见范围和发送者标记的** Effective Messages"。这条改起来只要三行，收益立竿见影。

### 2.4 DM prompt 里没有一句"忠于模组"

现在的 instructions 是：不得掷骰、不得改数值、要简短、人称规则、PUBLIC/PRIVATE 规则。**关于剧情忠实度，零条。**

> **修复**：加入明确的优先级声明与禁止创造条款，例如：
> - 模组内容 > 场景笔记 > 最近对话；三者冲突时以模组为准。
> - 不得引入模组中未出现的具名 NPC、地点或情节转折。
> - 玩家行为偏离模组时，优先设计**自然的引导回归**；确实无法回归时，必须在草稿开头标注 `[脱离模组]` 供 DM 判断。

### 2.5 没有 DmContextBuilder，三条路径上下文互相不对等

`ARCHITECTURE.md §10.3` 定义了 `DmContextBuilder.build(...)` 统一入口。实际代码里有**三套各写各的**：

| 路径 | 实现 | 模组 | 场景笔记 | 对话历史 | 阵容 | 相识状态 |
|---|---|---|---|---|---|---|
| `generate_opening` | JSON | ✅ | ❌ | — | ✅ | ✅ |
| `_character_reply_context` | JSON | ✅ | ✅ | ✅(40, 无发送者) | ✅ | ✅ |
| `_manual_context` | **字符串拼接** | ✅ | ✅ | **❌ 完全没有** | ✅ | ❌ |

`MANUAL_ASSIST` 路径下 AI DM **看不到任何最近发生了什么** —— DM 手动辅助时（最需要 AI 帮忙润色的场景）模型的上下文最差。字段命名也各不相同（`"最新角色回复"` vs `"DM 手动辅助要求"`），四种触发共用同一套 instructions，没有按 `trigger_type` 分化。

### 2.6 `SKILL_CHECK_RESULT` 触发类型没有实现

枚举里有，PRD §4.8 / §3.13 要求"真人确认检定结果 → AI DM 生成结果叙事草稿"。实际：

- `SkillCheckService.create()` 投完骰**不触发任何草稿**。
- 唯一的检定路径是 `DmDraftService.create(source_skill_check_id=...)`，`trigger_type` 写死为 `MANUAL_ASSIST`。
- PRD §3.14「有 DC 时 AI DM **必须遵守**系统计算的成功/失败」——`check_context` 只是一行文本 `系统结论 PASS`，prompt 里没有"不得改变该结论"的指令，也没有任何事后校验。

### 2.7 【隐私风险】PRIVATE 草稿静默降级为 PUBLIC

```python
def _normalize_visibility(self, campaign, result):
    if result.audience == "PRIVATE" and recipient_ids and set(recipient_ids).issubset(member_ids):
        return PRIVATE, recipient_ids
    return PUBLIC, []      # ← 模型意图是私密，但 ID 写错一个 → 全体可见
```

模型想发给某个角色的秘密，只要它幻觉了一个 ID，就会**静默变成全体公开**，DM 未必注意到。这直接违反 PRD §6「AI DM PRIVATE 草稿只会发布给所选角色」的精神。

> **修复**：ID 不合法时应把草稿标为 `FAILED` 或保留 PRIVATE 但清空收件人并强制 DM 补选，绝不能默认转公开。

### 2.8 `module_content` 与 `dm_guide` 双字段并存

`campaign.module_content or campaign.dm_guide` 这个 fallback 出现在 3 处。两个字段语义重叠、来源不明，DM 不知道该填哪个，AI 拿到的可能是空模组 + 旧 guide。

---

## 三、其他 Agent 层问题（含未达 PRD/架构的部分）

### 3.1 `ContextBuilder` 唯一入口不存在 —— 架构层最大偏离

`ARCHITECTURE.md §10.1` 要求「Character、Summary 和 Memory Agent 都必须通过该入口获取角色数据」。实际：

- Character → `RuntimeSupervisor._build_context`（硬编码在 runtime 里）
- Summary → `SummaryService._record`（就是把消息 content 拼起来）
- DM → `DmDraftService` 三套
- Relationship → `RelationshipService` 自己一套

后果：隐私过滤规则（陌生人化名、Recipient 快照）**只在 Character 路径实现过一次**，其他路径各写各的，无法保证一致，也无法单元测试。PRD §6 里"私密消息不会进入无权角色的 Context/Summary/Memory"这条验收，目前靠的是巧合而不是设计。

### 3.2 SummaryService 基本是坏的

```python
await self._upsert(session_id, None, SummaryAudience.DM, await self._record(game_session.id))
```

- **DM 摘要根本没过 LLM** —— 直接存 `"本节可见事实记录：\n" + 所有消息拼接`。这不是摘要，是转录稿。
- 角色摘要过 LLM，但 `except Exception: pass` —— 供应商失败时静默存入原始拼接文本，**没有任何日志、没有状态标记**，DM 无从得知。
- `memories` 上限 8 条，**无去重、不与既有记忆合并**。

### 3.3 【bug】`complete()` 里成长档案永远拿不到本次记忆

`campaign_service.complete()` 的执行顺序是：

1. 查询 `CharacterMemory where source_campaign_id == campaign.id and origin == AUTO`
2. 把查到的记忆追加进 `CharacterProfile`
3. ……最后才 `await SummaryService(...).build_for_campaign(...)` —— **而 AUTO 记忆是在这一步才被创建的**

所以第 1 步永远查到空列表，`if profile is not None and items:` 永远为假。**本次战役的成长记录永远不会写入成长档案。** 顺序颠倒即可修复。

（另：PRD §3.11 要求"根据角色自己的记忆更新成长档案"，现在的实现是字符串拼接 `【战役 X 的成长记录】\n- ...`，不是 LLM 生成的档案。`ProfileStatus.GENERATING / NEEDS_REBUILD` 两个状态定义了但没有任何代码使用。）

### 3.4 RelationshipAgent：每条消息全量重算，且阻塞主流程

```python
# supervisor._commit_results 末尾
if self._enable_relationship_updates:
    await RelationshipService(...).refresh_for_campaign(run.campaign_id)   # ← 同步 await
```

5 个角色 = 10 对，每对携带**完整共同故事全文**，`max_tokens=3200`。这发生在**每一条角色消息发布之后**，且是同步等待——直接拖慢跑团节奏，成本也随消息数线性膨胀。失败只 `logger.exception` 不重试。

> **修复**：脏标记 + 去抖（debounce）+ 只重算受本条消息影响的角色对 + 增量式（给「旧关系摘要 + 本次新增消息」而非全量故事）+ 移出主事务用后台 task。

另外 `self._enable_relationship_updates = agent_factory is DeepSeekCharacterAgent` —— 用"角色 Agent 工厂是不是默认值"来决定要不要更新**关系**，这是为了测试方便的 hack，语义完全错误。应该用 `settings.relationship_agent_is_configured`。

### 3.5 可观测性只覆盖 1/4 的 LLM 调用

```python
class LlmPurpose(StrEnum):
    CHARACTER = "CHARACTER"
```

DM / Relationship / Summary 三个 Agent 的调用**完全没有 `llm_invocations` 记录** —— 没有耗时、token、失败原因。`ARCHITECTURE.md §7.11` 的 Debug 面板、成本统计、失败排查全部只能看到角色 Agent。而你现在最想调的恰恰是 DM Agent。

### 3.6 所有 Agent 共用同一个模型和同一个配置开关

`DeepSeekDmAgent.__init__` 用的是 `settings.character_agent_is_configured` 和 `settings.character_model`。DM Agent **无法配置成更强的模型**——而 DM 恰恰是最需要长上下文和推理能力的角色。Relationship / Summary 有独立的 `*_model` 配置，DM 反而没有。

### 3.7 没有重试与降级

`retries=1` 是 pydantic_ai 的**输出校验重试**，不是网络重试。供应商 429 / 超时直接 fail。角色全失败 → runtime 进 ERROR 需人工介入。建议加 tenacity 指数退避 + 单角色失败时的静默降级。

### 3.8 `urgency` 由角色自己申报，无任何制衡

模型普遍会把自己的发言标成 `HIGH`（"我这句很重要"），几轮之后 urgency 全线通胀，优先级失效。

### 3.9 陌生人化名机制的两个隐患

```python
content = content.replace(state.character.name, alias)
```

- 角色名如果是常用字（"月"、"影"），会误伤正文里的普通词。
- `stranger_aliases` 每次调用**重新按 `character_id` 排序编号**。中途有角色加入时，编号会整体位移 —— 角色眼中的"陌生人#2"会突然变成另一个人。应持久化编号。
- 只 redact 其他 PC 的名字，**不处理 NPC 名字**。

### 3.10 没有 prompt 版本管理，也没有回归评测

这是你现在这个问题的元问题：prompt 全部硬编码在 `.py` 里，改一次没有任何方式验证是变好还是变坏。

> **建议**：prompt 抽成带版本号的模板文件（`prompts/character/v3.md`），`llm_invocations` 记录 `prompt_version`；再搭一个最小评测集——固定 20 组 context 快照，跑一遍，用另一个模型按「in-character 程度 / 是否越权 / 是否复述」打分。有了这个，后面所有 prompt 迭代才有依据。

### 3.11 `consecutive_ai_messages >= 12` 在 NARRATIVE 下是死代码

NARRATIVE 模式每发一条角色消息就进 `WAITING_FOR_DM`，DM 发新消息时 `message_service` 又归零 —— 计数器永远到不了 12。PRD §3.9 的"两条 DM 消息之间最多 12 条 AI 消息"只在 COMBAT 模式有意义，但 COMBAT 模式下角色消息**也不串联**（`play_mode != NARRATIVE` 分支才创建 followup run，逻辑写反了？值得复核 supervisor.py:592）。

---

## 四、优先级建议

**第一梯队（改动小、效果立竿见影）**

1. §1.1 — 把 roleplay prompt 提升为动态 system prompt，停止 `json.dumps` 整个 payload（角色扮演）
2. §2.3 — DM Context 的对话历史加上角色名和 audience（3 行代码，DM 剧情连贯性）
3. §1.7 — 修复"被点名"判定 + 让 coordinator 真正使用 `addressed_character_ids`
4. §3.3 — `complete()` 里 SummaryService 调用顺序前移（成长档案 bug）
5. §2.7 — PRIVATE 降级改为报错（隐私）

**第二梯队（中等改动）**

6. §1.2 + §1.3 — 重写 CHARACTER_INSTRUCTIONS 为正向描述 + 引入 `voice_samples`
7. §2.4 + §2.5 — 建 `DmContextBuilder`，按 trigger_type 分化 prompt，加入模组忠实度条款
8. §1.8 — Validator 失败改为重试 / 换候选，而不是 runtime ERROR
9. §3.4 — Relationship 刷新改为异步去抖 + 增量
10. §3.5 — 补齐 `LlmPurpose`，让 DM/Summary/Relationship 可观测

**第三梯队（架构级）**

11. §2.1 — **模组结构化：scenes / beats / 进度状态 + DmDecision 元信息**（这是"守剧情"的真正解法）
12. §3.1 — 抽出统一的 `ContextBuilder`
13. §3.10 — prompt 版本化 + 最小回归评测集
14. §1.4 — Character Agent 改两段式生成（自由文本 → 结构化抽取）
