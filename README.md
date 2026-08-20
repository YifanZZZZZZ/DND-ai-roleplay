# AI TRPG

## 项目简介

一个由真人 DM 主持、多个长期存在的 AI 角色共同参与的本地网页跑团工具。

项目的重点不是让 AI 代替 DM 自动生成冒险，而是让 AI 稳定地扮演玩家角色：每个角色拥有独立人设、能力资料、可见信息、长期记忆与成长轨迹；DM 始终掌握世界、NPC、规则结果和叙事裁决权。

## 当前状态

项目目前处于产品和技术设计阶段，仓库中暂未创建可执行代码脚手架。

- [精简产品需求](./PRD.md)
- [精简技术架构](./ARCHITECTURE.md)
- [完整产品需求文档](./AI_TRPG_Website_MVP_PRD_v0.3.md)
- [完整技术架构文档](./AI_TRPG_MVP_TECH_ARCHITECTURE.md)

本文后面的运行命令描述代码脚手架完成后的预期开发方式；在 `pyproject.toml`、`backend/` 和 `frontend/` 创建前，这些命令不会运行。

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
- LangGraph
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

每条已发布消息创建一个独立 `AgentRun`。一个 Run 会并行询问所有有权看到该消息的角色，但最多只发布一个候选气泡。若该气泡需要 DM 裁决，当前 Run 结束，Session 进入 `WAITING_FOR_DM`；DM 回复后再创建新的 Run。

SQLite 是业务事实的唯一来源。Agent 不保存框架内部长期历史，也不能直接访问或修改数据库。

## 预期目录

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

> 以下命令将在工程脚手架创建后生效。

### 1. 环境要求

- Python 3.12 或更高版本；
- Node.js 和 npm；
- uv；
- Gemini 或 DeepSeek API Key。

### 2. 创建本地配置

```bash
cp .env.example .env
```

至少需要配置：

```dotenv
AI_TRPG_DATA_DIR=/absolute/path/to/AI_TRPG_DATA
AI_TRPG_LLM_PROVIDER=google
AI_TRPG_CHARACTER_MODEL=your-model-name
AI_TRPG_VALIDATOR_MODEL=your-model-name
AI_TRPG_SUMMARY_MODEL=your-model-name
GOOGLE_API_KEY=your-api-key
# 或 DEEPSEEK_API_KEY=your-api-key
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
uv run uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

终端二：

```bash
npm --prefix frontend run dev
```

随后打开 Vite 输出的本地地址。

### 7. 本地生产模式

```bash
npm --prefix frontend run build
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

生产模式下由 FastAPI 提供编译后的前端静态文件。

## 检查与测试

```bash
uv run ruff check .
uv run pyright
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run test:e2e
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
