# AI TRPG

## 项目简介

一个由真人 DM 主持、多个长期存在的 AI 角色共同参与的本地网页跑团工具。

项目的重点不是让 AI 代替 DM 自动生成冒险，而是让 AI 稳定地扮演玩家角色：每个角色拥有独立人设、能力资料、可见信息、长期记忆与成长轨迹；DM 始终掌握世界、NPC、规则结果和叙事裁决权。

## 当前状态

项目已经完成 Stage 0、Stage 1、Stage 2，并完成 Stage 3 的多角色运行闭环。

当前可运行能力：

- FastAPI、React/Vite、SQLite 和 Alembic 工程骨架；
- 全局角色资料创建；
- 固定模板 Excel 角色卡安全上传、解析预览和确认激活；
- 角色定性身份、实际能力、法术、装备白名单快照；
- Campaign 创建、阵容与唯一 ACTIVE Campaign 约束；
- Session 创建、结束和唯一 ACTIVE Session 约束；
- HP 查看与修改，修改 Max HP 时同步当前 Session 并自动回满；
- 角色库、角色卡上传、战役阵容、生命周期、Session 与 HP 的桌面端操作页面；
- 两栏跑团主页面、DM 场内消息、消息接收者快照与实时状态刷新；
- `clientRequestId` 幂等发送、Generation 抢占令牌和“停止 AI 自动对话”控制；
- DeepSeek OpenAI 兼容接口与 PydanticAI 结构化角色输出；
- 每条新消息并行询问所有可见角色，协调器只发布一条不冲突的候选气泡；
- 角色可保持沉默，或在需要结果裁决时等待 DM；发布后会重新广播，连续发言最多 12 条；
- OOC 纠正会使错误消息失效，并以带标识的有效替代消息继续运行；
- 角色拥有可编辑的成长档案、长期记忆、头像与按可见范围生成的 Session 记录；
- 支持角色与 Campaign 的 JSON 导出，以及完成后 Campaign 的永久删除；
- 角色上下文仅包含自己可见的消息、角色卡定性资料、长期记忆及定性健康状态；
- 模型调用审计记录（模型、状态、耗时和输入/输出 token）；
- OpenAPI 自动生成前端 DTO；
- 角色、Campaign、Session 与消息可见范围的集成测试。

当前角色卡解析器只支持项目约定的“DND 5E2024 人物卡〈悲灵 v1.0.0〉”固定模板。真实 Character Agent 已优先接入 DeepSeek；未配置 API Key 时，DM 消息会安全保存且不会伪造 AI 回复。尚未实现的主要部分是 Multi-Agent Orchestrator、OOC 修订、记忆自动沉淀和导出。

- [精简产品需求](./PRD.md)
- [精简技术架构](./ARCHITECTURE.md)
- [完整产品需求文档](./AI_TRPG_Website_MVP_PRD_v0.3.md)
- [完整技术架构文档](./AI_TRPG_MVP_TECH_ARCHITECTURE.md)

## 项目特点

- 真人 DM 拥有最终叙事权和规则裁决权；
- 支持 1～6 名 AI 角色参与一个 Campaign；
- Character 是跨 Campaign 长期存在的全局实体；
- 每个角色只能读取自己实际知道的公开、私密和历史信息；
- 每个角色可以自主选择发言、行动或保持沉默；
- 每次 Agent 响应最多发布一个完整消息气泡；
- 需要外部结果时，所有 AI 停止并等待 DM；
- DM 可以随时停止未发布 AI 输出或发送新消息接管对话；
- 支持公开消息、DM 私密消息和角色对 DM 的秘密行动；
- 支持 OOC 纠正并让相关角色重新处理；
- 支持角色级滚动摘要、长期记忆和成长档案；
- 严格维护当前 HP，但只向 AI 提供定性健康状态；
- 支持 Campaign 和角色资料导出；
- Campaign 重置或永久删除时同步移除其来源记忆。

## 技术栈

### 前端

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- CSS Modules + CSS Variables

### 后端

- Python
- FastAPI
- PydanticAI
- LangGraph（将在多角色编排阶段接入）
- SQLAlchemy 2.x
- Alembic
- SQLite + aiosqlite
- openpyxl

### 开发与测试

- uv
- npm
- Ruff
- Pyright
- pytest + pytest-asyncio
- Vitest
- Playwright

## 核心架构

```text
React Web
   │
   ├── REST：读取数据和发送命令
   └── SSE：接收消息与运行状态变更通知
   │
FastAPI
   ├── Character / Campaign / Session / Message Services
   ├── Runtime Supervisor
   ├── PydanticAI Character Agents
   ├── LangGraph Reaction Graph
   ├── Context & Memory
   └── Export
   │
SQLite + Local File Storage
```

每条已发布消息创建一个独立 `AgentRun`。所有有权看到消息的角色会独立、并行地产生沉默或完整候选；纯 Python 协调器按点名、紧急性、发言公平性和记录的随机种子选择一条候选。未选择的候选不会写入消息历史。若该气泡需要 DM 裁决，当前 Run 结束，Session 进入 `WAITING_FOR_DM`；DM 回复后再创建新的 Run。

SQLite 是业务事实的唯一来源。Agent 不保存框架内部长期历史，也不能直接访问或修改数据库。

## 项目目录

```text
DND跑团/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   ├── domain/
│   │   ├── services/
│   │   ├── runtime/
│   │   ├── agents/
│   │   ├── context/
│   │   ├── db/
│   │   ├── files/
│   │   └── events/
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── app/
│       ├── api/
│       ├── pages/
│       ├── features/
│       └── components/
├── scripts/
└── docs/
```

## 如何运行

### 1. 环境要求

- Python 3.11 或更高版本；
- Node.js 和 npm；
- uv；
- DeepSeek API Key（仅在启用真实角色回应时需要）。

### 2. 创建本地配置

```bash
cp .env.example .env
```

当前至少需要配置数据目录：

```dotenv
AI_TRPG_DATA_DIR=/absolute/path/to/AI_TRPG_DATA
AI_TRPG_LLM_PROVIDER=deepseek
AI_TRPG_CHARACTER_MODEL=deepseek-v4-flash
AI_TRPG_DEEPSEEK_API_KEY=your-api-key
AI_TRPG_DEEPSEEK_BASE_URL=https://api.deepseek.com
```

运行数据库、上传文件和导出文件必须位于仓库外的 `AI_TRPG_DATA_DIR`，不得提交到 Git。

### 3. 安装后端依赖

```bash
uv sync
```

### 4. 安装前端依赖

```bash
npm --prefix frontend ci
```

### 5. 初始化或升级数据库

```bash
uv run alembic upgrade head
```

### 6. 启动开发环境

终端一：

```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

终端二：

```bash
npm --prefix frontend run dev
```

随后打开 Vite 输出的本地地址。

### 7. 构建前端

```bash
npm --prefix frontend run build
```

当前开发阶段由 Vite 提供前端。FastAPI 同源提供构建产物会在进入可发布版本前接入。

## 检查与测试

```bash
uv run ruff check .
uv run ruff format --check backend scripts
uv run pyright backend/app
uv run pytest
uv run alembic check
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

CI 中使用假的 Model Adapter 或 PydanticAI TestModel，不调用真实 Gemini 或 DeepSeek。

## 本地数据

建议结构：

```text
AI_TRPG_DATA/
├── app-data.sqlite3
├── uploads/
│   ├── avatars/
│   └── character-sheets/
├── temp/
└── exports/
```

以下内容不得提交到 Git：

- `.env`；
- API Key；
- SQLite 数据库；
- 上传的头像和 Excel；
- 导出文件；
- 调试日志中的私密内容。

## MVP 范围

MVP 是本地单用户桌面网页，不包含登录、多用户、多 ACTIVE Campaign、移动端、Docker、向量数据库、严格法术位/物品资源系统或 Campaign 导入恢复。

## 文档优先级

发生冲突时按以下顺序处理：

1. [完整 PRD](./AI_TRPG_Website_MVP_PRD_v0.3.md)；
2. [完整技术架构](./AI_TRPG_MVP_TECH_ARCHITECTURE.md)；
3. [PRD.md](./PRD.md)；
4. [ARCHITECTURE.md](./ARCHITECTURE.md)；
5. README。
