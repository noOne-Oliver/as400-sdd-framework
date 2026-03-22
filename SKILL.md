# SKILL — AS400 SDD 自动开发框架

## 概述

**AS400 SDD Framework** 是一个基于 **SDD（Specification Driven Development）** 与 **多 Agent 协作理念**的自动化开发框架，运行在 IBM i / AS400 环境下。

**核心流程：**
```
需求分析 → 规格设计 → 测试设计 → 代码生成 → 代码评审 → 测试执行
  (RA)        (SD)        (TD)        (CG)         (CR)         (TE)
       验证        验证         验证         验证         验证
```

---

## 功能清单

### 核心能力

| 功能 | 说明 |
|------|------|
| **多 Agent 协作** | 6 个专用 Agent（RA/SD/TD/CG/CR/TE）顺序协作 |
| **LLM-as-Judge 验证** | 每阶段输出经过 Judge 评分（结构化规则，可切换 LLM） |
| **并行执行** | TD（测试设计）和 CG（代码生成）可并发运行 |
| **上下文跨阶段传递** | SessionContext 记录每阶段摘要，注入下游 Agent |
| **SessionContext** | 完整执行历史（phase/agent/score/artifacts/timestamp）|
| **文件规划** | CGAgent 先规划文件列表，再逐文件生成 |
| **Pre-submit Checklist** | CR 阶段 6 项强制检查（状态码/monitor/日志/dcl-f/*inlr/无TODO）|
| **知识图谱** | KnowledgeGraph 支持跨运行的 KB 搜索与记忆 |
| **KGMemory** | 跨 session 持久化历史 KG 命中结果 |
| **工具注册表** | ToolRegistry + ShellTool / FileTool，可扩展 |
| **声明式 Stage 驱动** | StageDriver 可将 pipeline YAML 化 |
| **单一配置入口** | `config/sdd_config.yaml` 统一管理所有配置 |
| **CI/CD 集成** | `.github/workflows/ci.yml` 自动测试 |

---

## 快速使用

### 环境要求
- Python 3.9+
- PyYAML ≥ 6.0
- requests ≥ 2.31.0
- pytest ≥ 8.0.0（测试用）

### 安装
```bash
cd as400-sdd-framework/
pip install -r requirements.txt
```

### 运行

**Mock 模式（无需 LLM）**
```bash
python3 run.py \
  --requirement examples/order_processing/requirement.txt \
  --provider mock
```

**自定义输出目录**
```bash
python3 run.py \
  --requirement examples/order_processing/requirement.txt \
  --output-dir /tmp/my-output \
  --provider mock
```

### 单元测试
```bash
python3 -m pytest tests/ -v
```

---

## 验证方法

### 1. 单元测试（全部通过即算验证）
```bash
python3 -m pytest tests/ -v
# 预期：54 passed, 1 warning
```

### 2. 端到端流水线
```bash
python3 run.py \
  --requirement examples/order_processing/requirement.txt \
  --provider mock
```
**预期输出：**
- `status: "completed"`
- 所有产物文件生成到 `examples/order_processing/` 下
- `session_context.json` 包含 6 个阶段记录
- `files_plan.json` 包含生成文件清单

### 3. 产物完整性检查
```bash
# 检查这 8 个文件必须存在
ls examples/order_processing/analysis.md
ls examples/order_processing/sdd.md
ls examples/order_processing/tests.md
ls examples/order_processing/ORDPRC.rpgle
ls examples/order_processing/review.md
ls examples/order_processing/execution_report.md
ls examples/order_processing/session_context.json
ls examples/order_processing/files_plan.json
```

### 4. CI 验证（本地模拟）
```bash
# pytest job
python3 -m pytest tests/ -v --tb=short

# artifact 完整性
python3 -c "
import json, os
ctx = json.load(open('examples/order_processing/session_context.json'))
assert len(ctx['phases']) == 6, f'Expected 6 phases, got {len(ctx[\"phases\"])}'
print('session_context.json: 6 phases OK')
artifacts = set(f for f in os.listdir('examples/order_processing/') if not f.startswith('.'))
expected = {'analysis.md','sdd.md','tests.md','ORDPRC.rpgle','review.md','execution_report.md'}
assert expected.issubset(artifacts), f'Missing: {expected - artifacts}'
print('All 8 artifacts present')
"
```

---

## 架构详解

### 目录结构
```
as400-sdd-framework/
├── run.py                    # CLI 入口（单入口）
├── config/
│   └── sdd_config.yaml       # 唯一配置入口（llm/pipeline/validation/tools/knowledge）
├── core/
│   ├── orchestrator.py       # Pipeline 调度器（含并行 TD‖CG）
│   ├── state_machine.py      # 状态机（7 个状态 + 合法的状态转换）
│   ├── judge.py              # Judge（结构化规则验证，score ≥ 7 通过）
│   ├── session_context.py    # 跨 Agent 执行历史记录
│   ├── knowledge_graph.py    # 知识库搜索（.md/.txt/.yaml 文件索引）
│   ├── kg_memory.py          # 跨 session 持久记忆
│   ├── config_loader.py      # SDDConfig 统一配置加载器
│   ├── stage_driver.py       # 声明式 YAML Stage 驱动（未来用）
│   └── llm_client.py         # LLM 客户端（mock/ollama/openai）
├── agents/
│   ├── base_agent.py         # 基础 Agent（execute/validate/retry_with_feedback）
│   ├── ra_agent.py           # 需求分析 Agent
│   ├── sd_agent.py           # 规格设计 Agent
│   ├── td_agent.py           # 测试设计 Agent
│   ├── cg_agent.py           # 代码生成 Agent（含 FileSpec + plan_files）
│   ├── cr_agent.py           # 代码评审 Agent（含 6 项 checklist）
│   └── te_agent.py           # 测试执行 Agent
├── tools/
│   ├── base_tool.py          # BaseTool ABC + ToolResult
│   ├── tool_registry.py      # 单例工具注册表
│   ├── shell_tool.py         # Shell 命令工具（白名单模式）
│   └── file_tool.py          # 文件读写工具（base_dir 限制）
├── prompts/                  # 各 Agent 的 prompt 模板
├── templates/                # SDD/测试/RPGLE/CL 代码模板
├── validation/               # 结构化验证规则（spec/code/test）
├── knowledge/                # 知识库（coding_standards/PF定义/业务规则）
├── examples/
│   └── order_processing/     # 完整示例（含 ORDPF/CUSTMF/INVPF/ORDLOGPF）
└── tests/                   # 54 个单元测试
```

### Pipeline 状态机
```
IDLE → REQUIREMENTS → SPEC_DESIGN → TEST_DESIGN
                                         ↓
                              CODE_GENERATION → CODE_REVIEW → TEST_EXECUTION
                                                                        ↓
                                                                   COMPLETED
```
- 每个状态只允许特定的后续状态（由 `StateMachine._allowed_transitions` 定义）
- `WAITING_HUMAN` 可从任意阶段触发人工介入，完成后回到下一阶段

### Judge 评分规则

**SPEC_DESIGN：** 缺少 `#`/`程序`/`业务规则`/`处理流程`/`错误处理`/`测试` → 扣分，≥7 通过

**TEST_DESIGN：** 缺少 `TC-`/`前置条件`/`步骤`/`预期结果`/未覆盖 `02`/`08`/`09` → 扣分

**CODE_GENERATION：** 缺少 `ctl-opt`/`dcl-f`/PF文件/`monitor`/`on-error`/`日志写入` → 扣分

**通过阈值：** score ≥ 7（满分 10）

---

## 产物说明

每次 Pipeline 完成后，输出目录包含：

| 产物 | 说明 |
|------|------|
| `analysis.md` | 需求分析报告 |
| `sdd.md` | 软件设计说明书（含 Mermaid 流程图）|
| `tests.md` | 测试用例设计（TC-001 ~ TC-N）|
| `ORDPRC.rpgle` | 生成的 RPGLE 源代码 |
| `review.md` | 代码评审报告 + Checklist 结果 |
| `execution_report.md` | 测试执行报告（4/4 PASS）|
| `session_context.json` | 6 阶段执行历史（agent/score/artifacts）|
| `files_plan.json` | 代码生成文件规划（FileSpec 列表）|

---

## 扩展指南

### 新增 Agent
1. 在 `agents/` 下创建 `{name}_agent.py`，继承 `BaseAgent`
2. 实现 `execute(input_data: dict) -> dict`
3. 在 `core/orchestrator.py` 中注册到 `agent_registry`
4. 在 `config/sdd_config.yaml` 的 `agents` 节点添加配置

### 新增工具
1. 在 `tools/` 下继承 `BaseTool`
2. 实现 `name`/`description`/`schema`/`execute()`
3. `ToolRegistry.get_instance().register(MyTool())`

### 新增 Judge 规则
修改 `core/judge.py` 中的 `evaluate_spec`/`evaluate_tests`/`evaluate_code`，或切换 LLM provider 获得动态评分。

### 接入真实 LLM
修改 `config/sdd_config.yaml`：
```yaml
llm:
  provider: openai-compatible
  model: qwen2.5-coder
  base_url: https://your-api.endpoint/v1
```

---

## 特点

- **确定性验证**：Judge 基于结构化规则，不依赖 LLM也能评分（mock 模式 100% 可复现）
- **零外部依赖**：mock 模式无需 Ollama / GPU / 网络
- **可解释性**：每个阶段都有 judge_result（score / issues / recommendations）
- **上下文透明**：SessionContext 完整记录每阶段谁执行、评分多少、产物摘要
- **无破坏性变更**：配置驱动，所有硬编码路径均可覆盖
- **CI 就绪**：GitHub Actions workflow 开箱即用

---

## 限制

- **代码生成质量取决于 LLM**：mock 模式只生成满足结构规则的占位代码，不代表生产可用
- **AS400 编译验证需要真实环境**：pipeline 不包含 CRTPGM / CRTRPGMOD 等 IBM i 编译步骤
- **无 IDE 集成**：产物需手动复制到 IFS 并在 5250 终端编译
- **知识库需手动维护**：新增 PF/LF 定义需同步更新 `knowledge/` 目录
- **Python 3.9 兼容**：`Optional[X]` 替代 `X | None` 类型注解
- **并发限制**：TD ‖ CG 并行依赖 Python `ThreadPoolExecutor`，不跨机器横向扩展
