# Character Agent 改造目标态（逐点对照）

每一节的结构都是：**现在是什么 → 改完是什么 → 需要你确认的点**。

改动集中在 4 个文件：
`agents/character_agent.py`、`runtime/supervisor.py`、`runtime/coordinator.py`、`runtime/message_validator.py`，
外加 1 个新表字段（§1.3）和 1 个新前端输入框（§1.3、§1.7）。

---

## §1.1 人格从 JSON 字段 → 动态 System Prompt

### 现在

```python
# character_agent.py（模块级常量，所有角色共用）
CHARACTER_INSTRUCTIONS = """你是一个长期参与 DND 跑团的角色扮演 Agent。..."""

Agent(model, instructions=CHARACTER_INSTRUCTIONS, ...)

# supervisor.py
payload = {"角色扮演指引": character.roleplay_prompt, "小队可观察健康状态": [...], ...}
return json.dumps(payload, ensure_ascii=False, indent=2)
```

模型看到：system = 通用禁令；user = 一个 JSON，人格是其中一个平级的键。

### 改完之后

`CharacterAgent.respond()` 的签名从 `respond(context: str)` 改成 `respond(system_prompt: str, context: str)`，
Agent 实例**每次调用现构造**（或用 `agent.run(..., instructions=...)` 动态覆写）。

`supervisor` 新增 `_build_system_prompt(character, voice_samples)`，产出如下**纯 Markdown**（不再 json.dumps）：

````markdown
你就是卡莱拉。不是在扮演她，你就是她。
下面是你的全部人格。你说的每一句话、做的每一个动作，都必须从这里长出来。

<你是谁>
# 身份

你是【卡莱拉】，来自【堕影冥界恐怖领域坦帕斯特的一座偏远村庄】，你认为自己是【一个只是想活下去，并让死去的人终于能安息的人】。

# 简短背景
...（roleplay_prompt 原文逐字照抄，Markdown 结构完全保留）...

# 说话与外在表现
- 语气和用词：【说话短促、直接，常带一点防御性的讽刺。...】
...
</你是谁>

<你会怎么说话>
...（见 §1.3 voice_samples）...
</你会怎么说话>

<硬性边界>
1. 你只能决定卡莱拉自己的言行。NPC、敌人、环境、别人的反应，以及任何行动的成败，都由 DM 裁定——你可以描写"我伸手去推门"，绝不能写"门开了"。
2. 你只知道下面上下文里给你的东西。不要编造、猜测或说出没给你的信息。
3. 这是 D&D 的奇幻世界。不要出现现代科技、网络用语或现实世界常识。当前上下文里的设定优先于你对 D&D 的一般印象。
4. 不要提到任何规则术语和数字：生命、属性、加值、豁免、难度、骰子、检定、回合。
5. 正文只写别人能看见和听见的：台词、动作、姿态、神态、声音。不写内心独白。
6. 一次只说一段话，只做一件事。
7. 想做一件结果不确定的事时，只描写你如何尝试，并把 requires_dm_resolution 设为 true。
</硬性边界>

<你要输出什么>
- 一句台词，或一个动作，或者"一个动作 + 一句台词"。目标 60 字以内，最多 240 字符。
- 不要复述、改写或总结别人刚说过的话。你的回应要给出新东西：一个态度、一个追问、一个决定、一个建议，或一个行动。
- 没有自然反应就选 SILENCE。宁可沉默，不要为了让场面热闹而说废话。
- 只有做只有你和 DM 知道的秘密行动时才用 DM_ONLY，平常用 PUBLIC。
</你要输出什么>
````

**关键差异**：`instructions` 里 90% 的内容是**这个角色独有的**，通用规则被压到最后两个 block。

### 需要你确认

- [ ] 开场那句「你就是卡莱拉。不是在扮演她，你就是她。」——有些人觉得这种"入戏咒语"有效，有些人觉得幼稚。要不要保留？
- [ ] `roleplay_prompt` 里的方括号【】是模板占位符的残留。要不要在注入前剥掉？（我倾向剥掉，方括号会让模型觉得这是"待填空的模板"而非"已确定的事实"）

---

## §1.2 16 条禁令 → 7 条边界 + 4 条输出要求

### 现在 vs 改完

| | 现在 | 改完 |
|---|---|---|
| 总条数 | 16 | 11（7 边界 + 4 输出） |
| 否定式 | 12 条 | 5 条 |
| 人称 | "你是一个角色扮演 Agent" | "你就是卡莱拉" |
| "要有性格" | 第 14、15 条，排在最后 | 删除——由 §1.1 的人格正文和 §1.3 的范例承担 |

被删掉的条目及去向：

| 原条目 | 去向 |
|---|---|
| 1（只依据可知信息） | 合并进边界 2 |
| 2（不超游） | 合并进边界 1 |
| 3（D&D 世界观，5 行） | 压成边界 3 一行 |
| 4（不提数值） | 边界 4 |
| 5（裁决） | 边界 1 + 7 |
| 6、7（单气泡、可观察） | 边界 5、6 |
| 8（DM_ONLY） | 输出要求 4 |
| 9（SILENCE） | 输出要求 3 |
| 10（长度，3 重） | 输出要求 1，**只说一次** |
| 11（不复述） | 输出要求 2 |
| 12（关系不复述） | **删除**，改由 context 分段承担（§1.6） |
| 13（人称） | **删除**——这条本来就是在解除限制，没必要占一条 |
| 14、15（要有性格/加神态） | **删除**，由人格正文 + voice_samples 承担 |
| 16（不输出思考） | **删除**，structured output 本身就保证了 |

### 需要你确认

- [ ] 第 3 条 D&D 世界观从 5 行压成 1 行，你之前写得很细（"不得擅自引入当前世界尚未确认的官方设定、怪物知识"）。这条是你踩过坑才加的吗？如果是，我保留原文。

---

## §1.3 新增 voice_samples（few-shot）

### 现在

不存在。人格全靠抽象规则描述（"会把担心包装成嫌弃"），模型自己往具体台词翻译时会退回平均值。

### 改完之后

**数据层**：`characters` 表加一列

```python
voice_samples: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

一个 alembic migration。前端角色编辑页在 Roleplay Prompt 下面加一个 textarea，标签："说话范例（可选，3～5 组）"。

**内容格式**（自由文本，DM 想怎么写就怎么写；下面是给卡莱拉写的示范，可直接用）：

```
情境：队友受了伤，卡莱拉在给他包扎。
卡莱拉：（把药膏塞进他手里，视线移开）"自己涂。"停了一下，"……别死在半路上，我懒得埋人。"

情境：有人向她道谢。
卡莱拉：（肩膀僵了一瞬）"谢什么。"她挑了挑眉，"你那个结打得太松了，重打。"

情境：陌生人主动示好，说可以带路。
卡莱拉：（眯起眼，视线扫过对方的手）"先生很热心。"她没有动，"热心的人一般都想要点什么。你想要什么？"

情境：有人提到亡者、坟墓或"让死人别闹了"。
卡莱拉：（声音一下子低下去）"你最好别用那种语气说他们。"

情境：队伍要走一条明显危险的路，她不同意。
卡莱拉："那条路两边是崖，出事跑都没地方跑。"她抱紧兜帽下的书，"绕远一点会死吗？"
```

**注入位置**：§1.1 的 `<你会怎么说话>` block。为空时该 block 整个省略。

### 需要你确认

- [ ] 上面这 5 条卡莱拉的范例，语气对不对？这是模仿基准，写歪了整个角色就歪了。
- [ ] 要不要我为其余角色也各写一份初稿供你改？（需要你把他们的 roleplay prompt 给我）

---

## §1.4 结构化输出压制文学性 → 在 schema 里内置一步 CoT

### 现在

```python
class CharacterDecision(BaseModel):
    decision: Literal["SILENCE", "RESPOND"]
    content: str = Field(default="", max_length=240)   # 模型在"填表"模式下写台词
    ...
model_settings={"temperature": 0.75, "max_tokens": 400,
                "extra_body": {"thinking": {"type": "disabled"}}}
```

### 改完之后（推荐方案：单次调用 + 内联 CoT，不加延迟不加成本）

利用 JSON schema **字段顺序 = 模型生成顺序**这个特性，在 `content` 之前插一个思考字段：

```python
class CharacterDecision(BaseModel):
    decision: Literal["SILENCE", "RESPOND"]
    # ↓ 新增：模型必须先想清楚"她此刻的反应是什么"，再写台词
    inner_beat: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=240)
    response_type: ... # ← 见 §1.7，考虑删除
    visibility: Literal["PUBLIC", "DM_ONLY"] = "PUBLIC"
    urgency: Literal["NORMAL", "HIGH", "IMMEDIATE"] = "NORMAL"
    addressed_character_ids: list[str] = ...
    requires_dm_resolution: bool = False
    resolution_request: str | None = ...
```

system prompt 里对应加一行：

```
inner_beat：先用一句话写下卡莱拉此刻真实的反应——她在意什么、警惕什么、想不想接话。
这句话不会被任何人看到，只是帮你把台词写准。然后再写 content。
```

`inner_beat` **不入库、不进消息、不展示**（`_commit_results` 里直接丢弃），只在 `llm_invocations` 里留档便于调试。

同时 `max_tokens` 400 → 600（多出的 token 给 inner_beat）。

### 备选方案（更贵，效果上限更高）

两段式：第一次自由文本生成（无 schema，纯散文，模型语言质量最高）→ 第二次用 `deepseek-chat` 做结构化抽取。
代价：每个角色每轮 2 次调用，5 个角色 = 10 次调用/轮，延迟约翻倍。

### 需要你确认

- [ ] 先做内联 CoT（推荐），还是直接上两段式？
- [ ] `thinking: disabled` 要不要同时打开做对比？（打开后延迟会明显上升，5 个角色并行更明显）

---

## §1.5 "要短"说三遍 → 只说一遍

### 现在

规则 10：`通常 1～3 句` + `不超过 120 汉字` + `绝不超过 240 字符` + `不要复述/总结/大段文学描写`
规则 15：`不要每条回复都强行加入神态` + `不要堆砌文学描写`
schema：`max_length=240`

五重压缩 → 模型输出最短的安全句。

### 改完之后

- **prompt 里只保留一句**："一句台词，或一个动作，或者'一个动作 + 一句台词'。目标 60 字以内，最多 240 字符。"
- 「不要堆砌神态」**整条删除**——现在的问题是神态太少不是太多。
- `max_length=240` 保留在 schema 层（真正的硬闸）。
- 措辞从"绝不超过""不要"改成正面的"一个动作 + 一句台词"——这实际上是在**鼓励**它加动作。

### 需要你确认

- [ ] 目标字数定 60 字还是 80 字？（现在是 120 字但实际输出远低于此，说明压制来自重复而非数字本身）

---

## §1.6 Context 从"无节制倾倒的 JSON" → 分段预算的 XML

### 现在

```python
payload = {
  "当前角色名称": ..., "角色身份与能力": sheet.parsed_snapshot,  # 整个 Excel dict
  "角色扮演指引": ..., "角色成长档案": ..., "角色长期记忆": [...20 条],
  "角色关系与共同经历": [...], "完整故事档案（按发生顺序）": [...全部],
  "小队可观察健康状态": [...], "角色相识限制": "...",
  "当前故事的完整可见记录": [...全量，无截断],
}
return json.dumps(payload, ensure_ascii=False, indent=2)
```

### 改完之后

`角色扮演指引` 和 `角色成长档案` 移入 system prompt（§1.1）。剩下的变成 **XML 分段的 user message**：

```xml
<你的能力与装备>
种族：人类｜职业：契约师（宗主：独角兽拉芮）｜背景：…
你会的：治疗术、护盾术、…
你带着的：黑皮书、绷带、…
</你的能力与装备>

<你记得的事>
- （pinned 记忆全部）
- （本次战役的记忆）
- （其余按时间倒序，装满预算为止）
</你记得的事>

<你和他们之间>
托里尔：一起从矿坑里逃出来过，他替你挡了一下。你嘴上说他鲁莽，但会留一份补给给他。
陌生人#1：（尚未认识）
</你和他们之间>

<你以前经历过什么>
【失落矿坑】…（已结束战役的故事摘要，按时间顺序）
</你以前经历过什么>

<你身边的人现在什么状态>
你自己：轻伤
托里尔：健康
陌生人#1：重伤
</你身边的人现在什么状态>

<注意>
"陌生人#N"是你还不认识的人。你不知道也不能说出他们的真名。
</注意>

<刚刚发生了什么>
DM：石门后面传来水声。
托里尔：（举起火把）"我先下去看看。"
</刚刚发生了什么>

<你要回应的是这一句>
DM：你们两个先进去，我在这儿守着。
</你要回应的是这一句>
```

**具体收敛规则**：

| 段 | 现在 | 改完 |
|---|---|---|
| 能力与装备 | `parsed_snapshot` 整个 dict | 只取 种族/职业/背景/已选能力名/法术名/关键装备，**丢掉所有数值和数据库页**，渲染成人话 |
| 长期记忆 | `limit(20)` 按 pinned+时间 | 实现架构 §10.4 的 Memory Selector：pinned 全量 → 当前战役 → 其余按时间，总预算约 1200 字 |
| 以前经历 | 全部，无限制 | 全部保留（本身已是摘要），超预算时把最早的合并压缩 |
| 当前战役消息 | **全量，无截断** | 最近 60 条全文；更早的暂时保留（未来接滚动摘要，见 §2.2） |
| 关系 | 数组 | 渲染成"角色名：一段话" |

### 需要你确认

- [ ] `角色成长档案` 放 system（当成"我是谁"的一部分）还是留 user（当成"资料"）？我倾向 system。
- [ ] 记忆预算 1200 字 / 消息 60 条，这两个数你有偏好吗？
- [ ] "能力与装备"要精简到什么程度——完全不给数值，还是保留法术位数量之类？（PRD §3.7 只禁 HP 数值，法术位没明说）

---

## §1.7 修复"被点名"判定

### 现在

```python
is_directly_addressed=(character.name.casefold() in trigger.content.casefold())
```

DM 说「你们两个先进去」→ 匹配不到任何人 → 优先级第一档永远不触发 → 退化成"最久没说话的人先说"（看起来像轮流发言）。

同时 `addressed_character_ids` 和 `response_type` 两个字段模型每次都在填，**代码里从来没读过**。

### 改完之后（三层，从可靠到兜底）

**第一层——DM 显式点名（最可靠）**
DM 发消息的表单加一个可选的多选"点名"控件，存进 `messages.addressed_character_ids`（新列）。
DM 说「你们两个先进去」时勾选那两个人。

**第二层——继承角色候选的点名**
上一条是角色消息时，直接用它已经输出的 `addressed_character_ids`——这个字段终于被用起来了。
`_commit_results` 发布消息时把它一并写入 `messages.addressed_character_ids`。

**第三层——姓名子串匹配（保留为兜底）**

```python
addressed = set(trigger.addressed_character_ids or [])
if not addressed:
    addressed = {c.id for c in characters if c.name.casefold() in trigger.content.casefold()}
is_directly_addressed = character.id in addressed
```

**顺带**：`response_type` 建议**从 schema 删除**——架构文档里定义了，但产品里没有任何地方区分 SPEECH / ACTION / SPEECH_AND_ACTION。留着只是让模型多填一个字段。

### 需要你确认

- [ ] 第一层要不要做？需要动前端 + 一个 migration。不做的话就只有第二、三层，DM 用代词点名时仍然失效。
- [ ] `response_type` 删掉，还是你后面打算用它做前端气泡样式区分？

---

## §1.8 Validator：从"误杀 + 卡死"到"精准 + 可恢复"

### 现在

```python
_mechanical_patterns = (
    re.compile(r"\d"),                        # ← 屏蔽任何数字
    re.compile(r"\b(?:d[24681020]|dc|ac|hp|str|dex|con|int|wis|cha)\b", re.I),
    re.compile(r"(?:技能|属性|能力值|豁免|检定|加值|骰子|投骰|难度等级|伤害骰)"),
)
```

失败 → `run.status = FAILED` + `runtime.status = ERROR` + 整个跑团卡住等人工重试。
并行生成的其他候选**全部被丢弃**。

### 改完之后

**（a）正则收紧，不再误杀**

```python
_mechanical_patterns = (
    # 数字只在与规则术语共现时拦截
    re.compile(r"\d+\s*点?\s*(?:伤害|生命|治疗)"),
    re.compile(r"(?:DC|AC|HP)\s*\d+", re.I),
    re.compile(r"\bd\s?(?:4|6|8|10|12|20|100)\b", re.I),
    re.compile(r"(?:豁免|检定|加值|骰子|投骰|难度等级|伤害骰|先攻)"),
)
```

「我数到三」「第二次了」「三个人」不再被拦。

**（b）失败改为可恢复的三级降级**

```
候选 A 校验失败
  → 带着失败原因让 A 重生成一次（最多 1 次）
    → 还失败 → 丢弃 A，从剩余候选里选下一个（coordinator 已经有排序）
      → 全部候选都失败 → 按 ALL_SILENT 结束，runtime 回 IDLE
        （只有 LLM 调用全失败才进 ERROR）
```

现在"偶尔一句漂亮台词含数字 → 跑团卡死"的情况消失。

**（c）架构 §5.5 的语义 Validator Agent**——本轮**不做**，留到第二梯队。

### 需要你确认

- [ ] "全部候选校验失败 → 按沉默处理"可以接受吗？还是你希望它显式报错让你知道出问题了？（我可以让它进 IDLE 但在前端挂一个非阻塞的警告条）

---

## §1.9 标记触发事件

### 现在

`trigger` 只在 `kind == OOC` 时才单独放进 payload。正常情况下它只是 `"当前故事的完整可见记录"` 数组的最后一项，无任何标记。

### 改完之后

见 §1.6 的 `<你要回应的是这一句>`——触发消息**从历史里摘出来单独成段，放在整个 context 最末尾**（最靠近生成位置，注意力权重最高）。

OOC 触发时改成：

```xml
<出戏更正——这是 DM 在游戏之外纠正你，不是场内发生的事>
你刚才那句话说错了，你并不知道守卫的名字。
</出戏更正——这是 DM 在游戏之外纠正你，不是场内发生的事>
```

---

## 改动清单汇总

| 文件 | 改动 |
|---|---|
| `agents/character_agent.py` | 删 `CHARACTER_INSTRUCTIONS` 常量；`respond()` 接收动态 system prompt；`CharacterDecision` 加 `inner_beat`、删 `response_type`；`max_tokens` 400→600 |
| `runtime/supervisor.py` | 新增 `_build_system_prompt()`；`_build_context()` 重写为 XML 分段 + 预算；`is_directly_addressed` 三层判定；发布时写入 `addressed_character_ids`；丢弃 `inner_beat` |
| `runtime/coordinator.py` | 不变（它已经是对的，只是输入坏了） |
| `runtime/message_validator.py` | 正则收紧 + 返回可重试的失败类型 |
| `db/models/entities.py` | `characters.voice_samples`、`messages.addressed_character_ids` |
| alembic | 1 个 migration |
| 前端 | 角色编辑页加"说话范例"；DM 发送框加"点名"多选（可选） |

---

## 等你确认的 12 个决定

1. §1.1 保留"你就是卡莱拉"这句入戏引导？
2. §1.1 剥掉 roleplay_prompt 里的【】方括号？
3. §1.2 D&D 世界观那 5 行是踩坑加的吗（决定压缩还是保留）？
4. §1.3 卡莱拉的 5 条 voice_samples 语气对不对？
5. §1.3 要我为其他角色也写初稿吗？
6. §1.4 内联 CoT（推荐）还是两段式？
7. §1.4 要不要同时打开 thinking 做对比？
8. §1.5 目标字数 60 还是 80？
9. §1.6 成长档案放 system 还是 user？
10. §1.6 记忆预算 1200 字 / 消息 60 条，可以吗？
11. §1.7 DM 显式点名控件做不做（要动前端）？`response_type` 删不删？
12. §1.8 全部候选失败时按沉默处理，可接受吗？

---

# 已实施（2026-08-23）

## 决定记录

| 编号 | 决定 |
|---|---|
| §1.1 | 保留入戏引导句；注入前剥掉 roleplay_prompt 的【】方括号 |
| §1.2 | D&D 世界观 5 行压成 1 行（确认只是顺手写细，非踩坑所加）；16 条禁令 → 7 条边界 + 6 条输出要求 |
| §1.3 | 新增 `characters.voice_samples`；卡莱拉的 5 条范例按原稿采用 |
| §1.4 | 内联 CoT（`inner_beat` 字段置于 `content` 之前），**不**做两段式，`thinking` 保持 disabled 以免增加延迟 |
| §1.5 | 目标 60 字；「要短」只在 prompt 里说一次 |
| §1.6 | 成长档案并入 system prompt；记忆预算 1200 字；当前战役消息 60 条 |
| §1.7 | 三层点名判定全做（含 DM 点名控件 + `messages.addressed_character_ids`）；删除 `response_type` |
| §1.8 | 校验失败 → 同角色重试 1 次 → 换下一候选 → 全失败按沉默 + 前端非阻塞警告条 |

## 改动文件

**新增**
- `backend/app/agents/character_prompt.py` — system prompt 与 context 的唯一组装点，带 `PROMPT_VERSION = "character/v2"`
- `backend/alembic/versions/fa0c1d2e3f45_character_voice_and_addressing.py`
- `backend/tests/test_character_prompt.py`

**修改**
- `backend/app/agents/character_agent.py` — 删除模块级 `CHARACTER_INSTRUCTIONS`；`respond(system_prompt, context)`；`CharacterDecision` 加 `inner_beat`、删 `response_type`；`max_tokens` 400→600
- `backend/app/runtime/supervisor.py` — `_build_context` → `_build_prompts`；新增 `_resolve_addressed`、`_select_publishable`、`_Selection`、`_RETRY_NOTE`
- `backend/app/runtime/coordinator.py` — 新增 `rank()`，`select()` 变成它的第一项
- `backend/app/runtime/message_validator.py` — 正则收紧；机械数值与结果宣告分成两类失败原因
- `backend/app/db/models/entities.py`、`api/schemas/{characters,messages}.py`、`api/routes/{characters,messages}.py`、`services/{character_service,message_service}.py`
- `frontend/src/pages/CharactersPage.tsx`、`SessionPlayPage.tsx` 及两个 CSS module
- `frontend/openapi.json`、`frontend/src/api/generated.ts`（手工同步，见下方待办）

## 验证状态

- 全部 backend 文件通过 AST 解析；无新增未使用 import
- `character_prompt` 的 8 项行为断言在离线环境下全部通过（人设逐字保留、方括号剥离、可选块省略、触发消息独立成段、OOC 取代触发块、记忆预算截断、空上下文不产生空标签、能力压缩）
- `MessageValidator` 13 条用例全部通过，其中「我数到三」「第2次了」「三个人」由拒绝转为放行，「个d20」「难度DC15」由放行转为拒绝（`\b` 对中文无效，已改用拉丁字符 lookbehind）
- **未执行完整 pytest**：本次改动在云端沙箱完成，PyPI 拉取被限流，依赖装不全；项目自带的 `.venv` 是 macOS 二进制，无法在该环境运行

## 待办（需要在你本机执行）

```bash
uv run alembic upgrade head          # 应用 fa0c1d2e3f45
uv run pytest                        # 已同步更新受影响的测试
uv run ruff check backend
cd frontend && npm run generate:api  # 用后端重新导出 openapi.json 覆盖手工同步的结果
npm run build
```

`generated.ts` 与 `openapi.json` 是手工按 openapi-typescript 的输出约定同步的，正确性依赖后端 schema 与我推断的一致——重新生成一次可以消除这个假设。

## 本轮没做的事

- 架构 §5.5 的第二层「语义 Validator Agent」仍未实现，只有确定性正则层
- prompt 版本化只落了一个 `PROMPT_VERSION` 常量，尚未写入 `llm_invocations`，也还没有回归评测集（对应复盘 §3.10）
