# AS400 SDD 自动开发框架 (as400-sdd-framework)

本框架基于 **SDD（Specification Driven Development）** 与 Harness Engineering 的 **多 Agent 协作理念**，实现 AS400 上的闭环自动开发流程：

> 需求分析 → 验证 → 生成 Spec → 验证 → 测试设计 → 验证 → 生成代码 → 验证 → 测试验收

## 架构概述

```
+-------------------------+
|  Requirement Analysis   |
+------------+------------+
             |
             v
+------------+------------+
|  Spec Design (SDD)      |
+------------+------------+
             |
             v
+------------+------------+
|  Test Design             |
+------------+------------+
             |
             v
+------------+------------+
|  Code Generation          |
+------------+------------+
             |
             v
+------------+------------+
|  Code Review (Judge)      |
+------------+------------+
             |
             v
+------------+------------+
|  Test Execution           |
+------------+------------+
             |
             v
+------------+------------+
|  Completed / Human Gate   |
+---------------------------+
```

## 核心理念（对标 Harness Engineering）

- **Agentic Flows**：多个专用 Agent 协作完成需求→Spec→测试→代码→验收
- **Knowledge Context**：轻量知识图谱（PF/LF/业务规则）辅助推理
- **LLM-as-Judge**：每阶段均有可解释验证与打分门禁
- **Human-in-the-loop**：任意阶段可触发人工介入点

## 目录结构

详见项目根目录结构，关键目录：
- `core/`：状态机、Orchestrator、Judge、LLM 客户端
- `agents/`：RA/SD/TD/CG/CR/TE 各 Agent
- `prompts/`：提示词模板
- `templates/`：SDD/测试/RPGLE 模板
- `examples/`：完整示例

## 运行方式

### Mock 模式（无需真实 LLM）
```bash
./scripts/demo.sh
```

### 正式模式（Ollama）
```bash
# 修改 config/pipeline.yaml:
# provider: ollama
# model: qwen2.5-coder

./scripts/run_pipeline.sh examples/order_processing/requirement.txt
```

## API 参考（核心入口）

```python
from core.orchestrator import Orchestrator

orchestrator = Orchestrator(provider="mock")
result = orchestrator.run("examples/order_processing/requirement.txt")
print(result["status"])
```

## 验收标准
- 完整闭环运行
- 每阶段具备 Judge 校验
- 可在 mock 模式跑通

---

如需扩展，可在 `knowledge/` 下维护真实 PF/LF 定义，并将 `LLM provider` 切换到 Ollama 或 OpenAI 兼容 API。
