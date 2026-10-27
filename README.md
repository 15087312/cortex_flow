# CortexFlow

本地优先、认知驱动的工作流编排引擎。

## 特色

- **本地优先**：运行在用户机器，访问本地模型/文件/感知
- **认知驱动**：流程可以思考，节点可以决策
- **动态路由**：AI 决定流程走向，而不是预定义
- **多层级模型**：large/supervisor/expert 分层调度
- **认知黑板**：结构化共享状态，按 tier 可见性控制
- **挂起恢复**：基于延续的事件驱动
- **感知集成**：视觉/音频/传感器作为一等输入

## 快速开始

```python
from cortexflow import Engine

# 加载工作流
engine = Engine()
flow = engine.load("workflow.yaml")

# 运行
result = await engine.run(flow, context={"task": "analyze data"})
```

## 文档

查看 [cortex_workflow_refined_design.md](./cortex_workflow_refined_design.md) 了解完整设计。

## 开发

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check src/
```

## License

MIT
