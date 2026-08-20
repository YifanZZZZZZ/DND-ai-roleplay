# AI TRPG 网站 MVP 产品需求

> 本文是项目入口版 PRD，保留产品定位、核心功能和用户流程。完整规则与验收标准见 [AI_TRPG_Website_MVP_PRD_v0.3.md](./AI_TRPG_Website_MVP_PRD_v0.3.md)。

## 1. 产品定位

AI TRPG 是一个由真人 DM 主持、多个 AI Character Agent 参与的本地网页跑团工具。

产品目标不是自动生成一个没有人类主持的游戏，也不是让多个通用助手协作完成任务，而是长期塑造一组持续存在的角色：他们拥有独立的人格、能力、经历、认知边界和记忆，并随着多次 Campaign 逐渐变得更加丰富。

### 1.1 核心角色

#### 真人 DM

DM 是唯一世界与规则裁决者，负责：

- 描述场景、NPC 和世界变化；
- 决定攻击、检定、法术、伤害和治疗结果；
- 发布公开或私密信息；
- 使用 OOC 纠正错误；
- 维护 HP；
- 管理 Character、Campaign 和 Session；
- 停止 AI 自动对话；
- 编辑角色摘要、长期记忆和成长档案。

#### Character Agent

Character Agent 只扮演自己的角色，可以：

- 根据人设、能力、经历和当前认知思考；
- 自主决定说话、行动或沉默；
- 与队友交谈、提出计划或发起行动；
- 向 DM 发起秘密行动；
- 在需要世界或规则反馈时停下并等待 DM。

Character Agent 不可以：

- 控制 NPC、敌人、其他角色或环境；
- 宣布行动结果；
- 读取其他角色的 Prompt、秘密或记忆；
- 读取自己加入 Campaign 前的消息；
- 修改 HP、法术位、物品或其他游戏数据；
- 输出机械数值或主动申请技能检定；
- 展示内心独白、模型推理或出戏表达。

### 1.2 目标用户与平台

- MVP 只供一个真人 DM 使用；
- 不做登录和注册；
- 主要运行在本地电脑；
- 只保证桌面浏览器体验；
- 同一时间全站只允许一个 ACTIVE Campaign。

### 1.3 成功标准

以 5 名角色为主要测试规模、最多 6 名角色时，系统能够让多个拥有独立人设、认知和长期记忆的 Character Agent，在真人 DM 主持下持续产生自然、有区别、重视伙伴关系且不越过叙事权限的互动。

## 2. 产品原则

1. DM 永远拥有最终叙事和规则裁决权。
2. Character 是全局长期实体，不和单个 Campaign 绑定。
3. 每个角色只能知道自己实际经历或被告知的内容。
4. 私密隔离必须由系统保证，不能只依赖 Prompt。
5. 跑团叙事不是回合制；AI 根据最新已发布事件持续判断。
6. 每次 Agent 响应最多生成并发布一个完整气泡。
7. AI 消息需要 DM 裁决时，所有 AI 立即停止。
8. DM 新消息优先于所有未发布 AI 候选。
9. 普通消息不允许编辑或删除，错误通过 OOC 修订。
10. AI 不写入机械状态；MVP 只严格维护 HP。
11. 所有角色关系使用定性记忆，不建立数值好感系统。
12. 已发布消息、角色配置、记忆和运行状态自动保存。

## 3. 核心功能列表

### 3.1 全局角色库

- 创建和编辑全局 Character；
- 设置角色名称和可选头像；
- 编辑 Roleplay Prompt；
- 上传固定模板 Excel Character Sheet；
- 解析并预览种族、职业、背景、能力、法术、装备与说明；
- DM 手动设置 Max HP；
- 查看和编辑 Character Development Profile；
- 查看、添加、编辑、删除和固定长期记忆；
- 导出角色 Prompt、成长档案、记忆和能力快照。

角色可以参加多个 Campaign，其 Prompt、能力、Max HP、成长档案和长期记忆跨 Campaign 保留。

### 3.2 Excel Character Sheet

- 所有角色使用同一个固定模板；
- Excel 用于提供角色真实拥有的身份、能力、法术、装备和说明；
- 不从 Excel 读取当前 HP 或 Max HP；
- 不向 Agent 提供未选择能力或数据库页；
- 上传后必须先解析预览，再确认激活；
- 解析失败不能覆盖原有效角色卡；
- 替换角色卡不修改 HP、消息或记忆。

### 3.3 Campaign 管理

- 创建 PREPARATION Campaign；
- 在筹备阶段选择 1～6 名角色；
- 启动为全站唯一 ACTIVE Campaign；
- ACTIVE 后允许新增角色，但不允许角色离队；
- 完成 Campaign；
- 在没有其他 ACTIVE Campaign 时重新开启；
- 归档 PREPARATION 或 COMPLETED Campaign；
- 重置全部跑团进度；
- 永久删除 Campaign；
- 删除或重置前提供导出入口。

中途加入的角色完全不知道加入前发生的公开或私密内容，但仍保留自己从其他 Campaign 获得的真实记忆。

### 3.4 Session

- DM 手动创建 Session；
- 一个 ACTIVE Campaign 同时最多有一个未结束 Session；
- 刷新、关闭网页或隔天回来不会结束 Session；
- 新 Session 继承上一 Session 的最终 HP；
- AI 在 Session 开始后保持安静，必须由 DM 发送第一条场内消息；
- DM 手动结束 Session；
- 结束后保存最终 HP、生成摘要和长期记忆；
- 已结束 Session 只读，不能重新开启或追加消息。

### 3.5 消息与可见范围

支持：

- DM 场内消息；
- DM OOC 消息；
- Character 公开消息；
- Character DM_ONLY 消息；
- PUBLIC、PRIVATE 和 DM_ONLY 可见范围；
- 发送时的可见角色快照。

规则：

- PUBLIC 只对发送时已经在 Campaign 中的角色可见；
- PRIVATE 只对 DM 选择的角色可见；
- DM_ONLY 只对发送角色与 DM 可见；
- 未收到私密消息的角色不知道该消息存在；
- 角色收到私密信息后可以自主选择是否公开；
- 消息正文发布后不允许普通编辑、删除或打断。

### 3.6 OOC 修订

- DM 可以发送公开或私密 OOC；
- OOC 使未发布旧候选失效；
- OOC 可以取消当前待裁决事项；
- OOC 不作为场内事件进入记忆，但纠正后的事实影响认知；
- 当前 Session 最新有效非 OOC 消息可以被替代；
- AI 消息由原角色根据 OOC 重新生成；
- DM 消息由 DM 在表单中提供正确版本；
- 如果角色纠正后选择沉默，原消息作废且不生成替代气泡；
- 较早事实只能从当前时点向后纠正，不回滚整段历史；
- UI、Agent Context、摘要、记忆和导出使用统一有效消息规则。

### 3.7 HP 与健康状态

- DM 查看并编辑准确 Current HP；
- Current HP 限制在 `0～Max HP`；
- 修改 Max HP 时，当前 ACTIVE Session 的 Current HP 自动设为新 Max HP；
- HP 修改立即保存，但不触发 AI，也不产生聊天消息；
- Agent 不读取准确数值；
- Agent 只读取自己和队友的定性状态：健康、轻伤、重伤、濒危、昏迷。

### 3.8 Character Agent

每次调用读取：

- 全局角色规则；
- Roleplay Prompt；
- Character Development Profile；
- 当前真实能力说明；
- 定性健康状态；
- 相关旧 Campaign 角色摘要；
- 当前角色长期记忆；
- 当前 Campaign 独立滚动摘要；
- 当前角色可见的最近消息；
- 最新触发事件。

每次输出：

- `SILENCE`；或
- 一个完整候选气泡；
- 可选的紧急性、点名对象、DM_ONLY 和待裁决信息。

角色消息只能包含可观察的台词、动作、姿态、神态和声音。

### 3.9 Multi-Agent Orchestrator

- 每条新消息发送给所有有权看到它的角色；
- 每个角色使用独立 Agent 调用；
- 所有角色可以独立选择沉默或回应；
- Orchestrator 根据点名、紧急性和发言公平性选择一个候选；
- 只校验最终候选；
- 一次只发布一个完整消息；
- 新发布消息重新触发所有有权感知的角色；
- 不按照固定顺序轮流发言；
- 全员沉默时回到 IDLE；
- 两条 DM 消息之间最多连续发布 12 条 AI 消息；
- 单角色失败不影响其他角色；
- 全部失败时进入 ERROR，并允许重试最新事件。

### 3.10 等待 DM 与停止

当最终角色消息需要 DM 裁决：

- 消息正常发布；
- 页面显示具体等待事项；
- 所有 AI 停止；
- Session 进入 WAITING_FOR_DM；
- DM 任意新 IN_GAME 消息视为完成当前裁决并触发新判断。

DM 可以随时：

- 点击“停止 AI 自动对话”；
- 在 AI 运行中发送新消息；
- 保留已经发布的消息；
- 使所有尚未发布的旧候选失效。

### 3.11 Context、Memory 与成长

每个角色独立维护：

1. Recent Context；
2. Rolling Session Summary；
3. Long-Term Character Memory。

Session 结束后：

- 生成 DM 全局摘要，仅供 DM 查看；
- 为每个角色生成只包含该角色可知信息的独立摘要；
- 提取值得跨 Session 保存的长期记忆；
- 单项生成失败不阻止 Session 结束，可稍后重试。

Campaign 完成后：

- 根据角色自己的记忆更新成长档案；
- 不自动改写 Roleplay Prompt；
- 不建立数值关系系统。

### 3.12 导出与删除

Campaign 导出包含：

- 最终有效公开、私密和 DM_ONLY 对话；
- 角色和 DM 摘要；
- 参与角色当前 Roleplay Prompt；
- 来源属于该 Campaign 的角色记忆；
- 消息发送者和可见范围。

角色导出包含：

- Roleplay Prompt；
- Character Development Profile；
- 全部长期记忆及来源；
- 当前能力、法术、装备和背包快照。

Campaign 重置或永久删除时，必须移除其来源记忆并重建受影响角色成长档案；不得影响角色来自其他 Campaign 或 DM 手动添加的记忆。

## 4. 核心用户流程

### 4.1 创建角色

```text
进入全局角色库
→ 创建角色
→ 输入名称
→ 上传可选头像
→ 填写 Roleplay Prompt
→ 上传固定模板 Excel
→ 输入 Max HP
→ 查看解析预览
→ 确认创建
```

### 4.2 筹备 Campaign

```text
创建 Campaign
→ 输入名称与描述
→ 从全局角色库选择 1～6 名角色
→ 检查角色配置完整性
→ 确认当前没有其他 ACTIVE Campaign
→ 启动 Campaign
```

### 4.3 开始 Session

```text
进入 ACTIVE Campaign
→ 创建或继续 Session
→ 恢复角色 HP
→ 进入跑团页面
→ AI 保持安静
→ DM 发送第一条 IN_GAME 消息
```

### 4.4 DM 消息触发角色

```text
DM 发送消息
→ 保存消息和接收者快照
→ 旧候选失效
→ 有权看到消息的角色独立判断
→ Orchestrator 选择一个候选
→ 最终候选通过发布前检查
→ 一次性发布完整气泡
→ 新气泡成为下一事件
```

### 4.5 等待 DM

```text
角色发起需要外部结果的行动
→ 发布角色消息
→ 页面显示待裁决事项
→ 所有 AI 停止
→ DM 发送 IN_GAME 裁决
→ 清除等待状态
→ 角色根据最新事实重新判断
```

### 4.6 OOC 修订最新 AI 消息

```text
DM 点击“纠正此消息”
→ 输入 OOC
→ 原消息和旧候选失效
→ 原 Character 根据纠正重新处理
→ 新版本通过校验
→ 替代原气泡并显示 OOC 修订标志
→ 相关角色根据有效版本继续
```

### 4.7 结束 Session

```text
DM 点击结束 Session
→ 取消未发布输出
→ 保存最终 HP
→ 生成 DM 摘要
→ 生成角色独立摘要
→ 提取长期记忆
→ Session 变为只读
```

### 4.8 完成 Campaign

```text
结束当前 Session
→ DM 点击结束 Campaign
→ Campaign 变为 COMPLETED
→ 更新参与角色成长档案
→ Campaign 默认只读
```

### 4.9 重置或永久删除 Campaign

```text
选择重置或永久删除
→ 可选先导出
→ 输入 Campaign 名称二次确认
→ 停止未完成 Agent Run
→ 删除 Session、消息、摘要和来源记忆
→ 重建受影响角色成长档案
→ 重置时保留 Campaign 和阵容
→ 永久删除时移除 Campaign 本身
```

## 5. MVP 暂不包含

- 多用户、登录、权限和云端账号；
- 多个同时 ACTIVE 的 Campaign；
- ACTIVE Campaign 角色离队；
- AI DM、NPC Agent 或世界自动生成；
- 移动端；
- 消息全文搜索；
- Campaign 导入恢复；
- 严格法术位、物品数量和能力次数追踪；
- 网站内掷骰；
- 数值关系、好感度或情绪系统；
- 语音、图片生成和聊天附件；
- Docker 和分布式部署。

## 6. 验收重点

MVP 至少必须证明：

- 新角色无法读取加入前消息；
- 私密消息不会进入无权角色的 Context、Summary 或 Memory；
- DM Summary 永不进入 Character Agent；
- 多个角色可以独立判断，但一次只发布一个气泡；
- 需要裁决后没有 AI 继续说话；
- DM Stop 或新消息能可靠阻止旧候选发布；
- OOC 后所有有效视图不再使用错误版本；
- Campaign 删除后对应记忆不再进入角色 Context；
- 页面刷新后仍能恢复当前 Session 和已发布消息；
- 5 名角色的主要运行规模可接受，最大支持 6 名角色。

