# 我用 6 个 Agent，让 AI 在 AS400 上帮我写代码

**一行需求进去，完整的 RPGLE 程序出来。**

这是真实发生的事情。整个框架从"能用"到"好用"，走了 4 个阶段，参考了 6 个顶级开源项目，烧掉了无数次 prompt，最终沉淀成这一套可运行的系统。

---

## 起点：一个问题

AS400（IBM i）是很多企业核心系统的命脉。

这些系统里跑着几百万行业务代码，全是 RPGLE。没人想动它，因为：

- **改了怕挂**
- **不改迟早也会挂**
- **招不到人会 RPGLE 的人**

但需求一直在来。

于是我想了一个问题：

> **能不能用 AI Agent，自动把业务需求变成可运行的 RPGLE 代码？**

---

## 文献调研：看了 6 个项目才动手

我没有闭门造车。先把业界最好的例子研究了一遍。

| 项目 | 谁做的 | 核心参考点 |
|------|--------|-----------|
| **SWE-agent** | Princeton（NeurIPS 2024）| 一个 YAML 文件驱动全部行为；提交前有强制自查清单 |
| **OpenHands**（OpenDevin）| 微软/OpenSource | ConversationMemory 防止上下文爆炸；工具有注册表 |
| **smol-ai/developer** | 小而美的 agent 库 | 先生成文件列表，再逐个写代码，而非一口气全写完 |
| **Anthropic 官方示例** | Claude 官方 | 工具 + MessageHistory + 循环执行 |
| **GPTScript** | 黑客圈流行 | 声明式 Pipeline DSL，用脚本就能串联工具 |
| **AutoGen** | 微软 | Swarm 多 Agent 并行，Selector 智能路由 |

结论是：状态机 + 多 Agent + LLM-as-Judge 这个组合，已经被验证过了。我们只需要把它搬到 AS400 这个垂直场景里。

---

## 第一版：能用就行

第一个版本非常粗暴——6 个 Python 函数，顺序调用，每个函数里塞一个 prompt。

```
需求 → RA → SD → TD → CG → CR → TE → 代码
```

运行正常，代码能出来。但问题很快暴露：

- Agent 之间"失忆"——每个 Agent 只知道自己的输入，不知道前面发生了什么
- 没有任何验证——质量全凭 LLM 自己发挥
- 没法重试——第一次失败了只能重来
- 配置散落各处——改个 prompt 要找三四个文件

---

## P0：把框架立起来

第一个正式版本，解决了三个问题：

### 1. SessionContext——Agent 有了记忆

每个阶段执行完，把关键摘要记录下来，传递给下一个 Agent。

```
[REQUIREMENTS] ra_agent score=7: ORDPRC 负责读取待处理订单...
[SPEC_DESIGN] sd_agent score=10: 设计说明已生成...
[TEST_DESIGN] td_agent score=9: 测试用例已覆盖 02/08/09...
```

下游 Agent 在自己的输出里带上这段"执行上下文"，验证上下文是否真的在跨阶段传递。

### 2. Pre-submit Checklist——代码不能带病出门

代码评审阶段之前，强制过 6 项检查：

| 检查项 | 说明 |
|--------|------|
| 状态码完整性 | 02 / 08 / 09 必须全部出现 |
| monitor/on-error | 必须有显式异常处理 |
| 日志写入 | 必须调用 WriteOrderLog |
| 文件操作 | 必须定义 dcl-f |
| 程序入口 | 必须设置 *inlr = *on |
| 无 TODO | 不允许占位注释 |

任何一项不通过，pipeline 自动重试。

### 3. File Planning——先规划再生成

代码生成之前，CGAgent 先输出一个文件清单：

```json
[
  {"filename": "ORDPRC.rpgle", "type": "rpgle", "priority": 1},
  {"filename": "ORDPRC.cl", "type": "cl", "priority": 2}
]
```

再按优先级逐个生成文件。批量生成，统一验收。

---

## P1：让框架更聪明

### 知识积累——KGMemory

同一个需求跑过一遍，框架会记住这次用到了哪些知识文件、提取了哪些业务规则。

第二次跑同样程序，KnowledgeGraph 自动召回历史记忆，prompt 上下文更丰富。

### 工具注册表——ToolRegistry

以后要接 AS400 编译命令、接 IBM i 的 API，只需要：

1. 写一个继承 `BaseTool` 的类
2. `ToolRegistry.get_instance().register(MyTool())`
3. Agent 直接调用 `self.call_tool("tool_name", ...)`，无需知道工具在哪里

工具可替换、可禁用、可叠加。

### 单一配置入口——config/sdd_config.yaml

原来配置散落在 `pipeline.yaml` + `agents.yaml` + `validation.yaml`。现在一个文件全部搞定：

```yaml
llm:
  provider: mock
  model: llama3.1
pipeline:
  stages: [REQUIREMENTS, SPEC_DESIGN, TEST_DESIGN, CODE_GENERATION, CODE_REVIEW, TEST_EXECUTION]
  max_retries: 3
tools:
  enabled: [shell, file]
validation:
  spec_rules_path: validation/spec_rules.yaml
```

---

## P2：让它跑得更稳、更快

### 并行执行——TD 和 CG 同时跑

Test Design 和 Code Generation 依赖同样的输入（SD 的输出），所以这两个阶段可以并行：

```
SD 完成后
    ├── TD Agent ──┐
    └── CG Agent ──┴──→ 汇合 → CR
```

用 `ThreadPoolExecutor` 实现。CG 等待 TD 的测试用例结果，两者都通过 judge 才进入下一阶段。

### StageDriver——把硬编码变成声明式

每次加一个新阶段，不用改 `orchestrator.py` 了。只需要在 YAML 里写：

```yaml
- name: CODE_GENERATION
  agent: cg_agent
  input_keys: [analysis, sdd, tests, context_summary]
  output_key: code
  judge: evaluate_code
  artifact: "{program_name}.rpgle"
```

`StageDriver` 读这个配置，自动组装 input_data、调用 agent，写产物。

### CI/CD——每次 push 都自动验证

GitHub Actions 在每次 push 时自动：

1. 运行全部 54 个单元测试
2. 跑完整端到端 pipeline
3. 检查 8 个产物文件是否齐全
4. 验证 `session_context.json` 结构正确

---

## 完整架构：一张图讲清楚

```
输入：requirement.txt
         │
         ▼
    ┌─────────┐
    │   RA    │ 需求分析 → analysis.md
    │ Agent   │ SessionContext 记录
    └───┬─────┘
        ▼
    ┌─────────┐
    │   SD    │ 规格设计 → sdd.md
    │ Agent   │ SessionContext 记录
    └───┬─────┘
        ▼
    ┌────────┐    ┌────────┐
    │  TD    │ ┣━│  CG    │  并行执行
    │ Agent  │ │ │ Agent  │
    └───┬────┘ │ └───┬────┘
        │         │
        ▼         ▼
    ┌─────────┐
    │   CR    │ 代码评审 + 6项 Checklist
    │ Agent   │ SessionContext 记录
    └───┬─────┘
        ▼
    ┌─────────┐
    │   TE    │ 测试执行 → execution_report.md
    │ Agent   │
    └───┬─────┘
        ▼
   完成！产物全部就位

Judge 在每个阶段出口把关：
  score ≥ 7 → 通过
  score < 7 → 重试（最多3次）
```

---

## 运行效果

```bash
python3 run.py \
  --requirement examples/order_processing/requirement.txt \
  --provider mock
```

输出：
```
status: "completed"
```

产物：
```
analysis.md          # 需求分析
sdd.md              # 软件设计说明书
tests.md            # 测试用例
ORDPRC.rpgle        # 源代码
review.md           # 评审报告
execution_report.md # 测试报告
session_context.json # 6阶段完整记录
files_plan.json     # 文件生成规划
```

---

## 关键数字

| 指标 | 数值 |
|------|------|
| Agent 数量 | 6 个（RA/SD/TD/CG/CR/TE）|
| 单元测试 | 54 个 |
| Pipeline 阶段 | 6 个 |
| Checklist 检查项 | 6 项 |
| 最大重试次数 | 3 次 |
| Judge 通过阈值 | score ≥ 7 |
| Python 代码行数 | ~2400 行 |
| 知识图谱 | TF-IDF 语义搜索 |
| 并行执行 | threading.Event 高效同步 |

---

## 2026-03-22 优化更新

### 1. 并行执行优化
**问题**：TD‖CG 并行使用 `time.sleep(0.1)` 轮询，效率低且浪费 CPU。

**改进**：使用 `threading.Event` 替代轮询，CG 线程在 TD 完成前阻塞，TD 完成后立即唤醒 CG。

```python
# Before: sleep polling
while td_done["result"] is None:
    time.sleep(0.1)

# After: event-based synchronization
td_event.wait()  # Block until TD completes
```

### 2. 知识图谱增强
**问题**：仅支持关键词匹配，无法理解语义相似性。

**改进**：引入 TF-IDF 评分算法，结合关键词命中率和语义相似度：
- Keyword score × 0.4 + TF-IDF score × 0.6
- 跳过隐藏文件（.kg_memory.json）
- 增加空查询保护

### 3. OpenSpec 概念文档
新增 `knowledge/open_spec_concept.md`，定义框架内规范类型：
- RequirementSpec（需求规范）
- DesignSpec（设计规范/SDD）
- TestSpec（测试规范）
- CodeSpec（代码规范）

### 4. 测试覆盖
- 所有 54 个单元测试通过
- Pipeline 端到端验证通过

---

## 约束与边界

**它能做的：**
- 在 mock 模式下，无需任何外部依赖，100% 本地运行
- 生成满足结构规则的 RPGLE 代码框架
- 完整的端到端验证闭环
- 每次运行的结果可复现

**它不能做的：**
- 生成的代码不等于生产可用（需要人工 review 和 IBM i 环境编译验证）
- 不能自动完成 CRTPGM / CRTRPGMOD 编译（需要真实 5250 环境）
- 知识库需要人工维护（新增 PF/LF 定义需要同步更新 `knowledge/`）

---

## 最后

这个框架的价值，不是 AI 写代码本身。

而是它证明了：**在 AS400 这个极度保守的环境里，AI Agent 的协作模式是可行的。**

状态机保证流程不乱，Judge 保证质量有底，SessionContext 保证上下文不断。

剩下的——真实的 LLM、真实的 IBM i 编译环境——只是时间问题。
