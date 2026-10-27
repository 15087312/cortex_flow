# CortexFlow

[![CI](https://github.com/15087312/cortex_flow/actions/workflows/ci.yml/badge.svg)](https://github.com/15087312/cortex_flow/actions/workflows/ci.yml)

本地优先、认知驱动的工作流编排引擎。

## 特色

- **本地优先**：运行在用户机器，访问本地模型/文件/感知
- **认知驱动**：流程可以思考，节点可以决策
- **动态路由**：AI 决定流程走向，而不是预定义
- **多层级模型**：large/supervisor/expert 分层调度
- **认知黑板**：结构化共享状态，按 tier 可见性控制
- **挂起恢复**：基于延续的事件驱动
- **感知集成**：视觉/音频/传感器作为一等输入

## 环境要求

- Python 3.11+
- Node.js 18+（仅构建/开发前端时需要）

## 安装

```bash
git clone git@github.com:15087312/cortex_flow.git
cd cortex_flow

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 启动

```bash
python run.py
```

服务监听 `http://localhost:9000`，同时提供 `/api` 接口和前端页面（`frontend/dist` 已随仓库提交，无需先构建）。

首次访问会进入「创建管理员账号」页面，创建后即可登录使用。

### 前端开发

```bash
cd frontend
npm install
npm run dev        # http://localhost:5174，/api 代理到 9000
```

改完前端后重新构建，后端会自动服务新的 `dist`：

```bash
cd frontend && npm run build
```

## 在代码中使用

```python
from cortexflow import Engine

# 加载工作流
engine = Engine()
flow = engine.load("workflow.yaml")

# 运行
result = await engine.run(flow, context={"task": "analyze data"})
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CORTEXFLOW_DB_PATH` | `<项目根>/data/cortexflow.db` | SQLite 数据库路径 |
| `CORTEXFLOW_DISABLE_AUTH` | 未设置 | 设为 `1` 时跳过登录（仅本地调试） |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 未设置 | 模型供应商密钥，按需配置 |

## 测试

```bash
pytest
ruff check src/
```

## 目录结构

```
src/cortexflow/      引擎核心：DSL/编译器、运行时、节点、Agent、存储、FastAPI 服务
frontend/            Vue 3 前端（src 源码 + dist 构建产物）
examples/            示例工作流与验证脚本
tests/               pytest 用例
data/                本地运行时数据库（已被 .gitignore 忽略）
```

## 文档

查看 [cortex_workflow_refined_design.md](./cortex_workflow_refined_design.md) 了解完整设计。

## License

MIT
