# GitHub 同类项目调研报告

## 调研对象

| 项目 | Stars量级 | 核心亮点 | 与我们框架的差距/可借鉴点 |
|------|----------|---------|------------------------|
| SWE-agent (Princeton) | ⭐⭐⭐⭐⭐ | YAML驱动配置、ACI工具接口、submit流程中置入review提示 | 可借鉴: 单YAML驱动全部行为，history_processor做上下文裁剪 |
| OpenHands/OpenDevin | ⭐⭐⭐⭐⭐ | CodeAct模式(代码即行动)、ConversationMemory、Condenser压缩 | 可借鉴: memory condenser防止上下文爆炸；工具注册表 |
| smol-ai/developer | ⭐⭐⭐⭐ | plan→file_paths→code三步分治、prompt文件化 | 可借鉴: 先plan得到文件列表再逐文件生成，而非整体生成 |
| Anthropic claude-quickstarts | 官方参考 | MessageHistory + 工具执行loop、MCP集成 | 可借鉴: MessageHistory管理、工具循环、MCP接口标准 |
| GPTScript | ⭐⭐⭐ | 声明式工具链（.gpt脚本）、任意系统集成 | 可借鉴: 声明式Pipeline DSL，减少胶水代码 |
| AutoGen AgentChat | ⭐⭐⭐⭐⭐ | 预设Teams模式、RoundRobin/Swarm/Selector | 可借鉴: Swarm模式做并行Agent，Selector做智能路由 |

---

## 关键差距分析（我们的框架 vs 业界）

### 1. 上下文管理 (Context / Memory)
- **现状**: 每个Agent独立执行，无会话历史记忆
- **业界做法**: OpenHands用ConversationMemory+Condenser压缩历史；SWE-agent用cache_control保留最近N条
- **改进方向**: 加 `SessionContext` 类，跨Agent传递执行历史摘要

### 2. 工具接口标准化 (Tool Interface)
- **现状**: Agent直接写死处理逻辑
- **业界做法**: Anthropic官方用 Tool 基类 + to_dict() + execute()；OpenHands有工具注册表
- **改进方向**: 统一 `Tool` 基类，支持 MCP 接入

### 3. 配置驱动 (Config-Driven)
- **现状**: 配置分散(pipeline.yaml/agents.yaml/validation.yaml)
- **业界做法**: SWE-agent 用单一 YAML 驱动所有 agent 行为(templates/tools/processors)
- **改进方向**: 合并为单一 `sdd_config.yaml`，所有提示词也可以在配置中覆盖

### 4. 生成文件列表先行 (File Planning)
- **现状**: 代码生成直接产出单个文件
- **业界做法**: smol-dev 先 plan() 得到文件列表 → 再逐文件 generate_code()
- **改进方向**: CGAgent先输出 `files_to_generate[]`，再并行生成每个文件

### 5. 提交前自动审查 (Pre-Submit Review)
- **现状**: 代码审查是独立阶段，审查结果不强制反馈修改
- **业界做法**: SWE-agent 在 SUBMIT_REVIEW_MESSAGES 中嵌入检查清单，要求agent自查后再提交
- **改进方向**: 在 CRAgent 中加入强制自查清单（diff验证、测试重跑、清理临时文件）

### 6. 并行执行 (Parallelism)
- **现状**: 所有阶段串行执行
- **业界做法**: AutoGen的Swarm/并行Team支持多Agent同时工作
- **改进方向**: TEST_DESIGN 和 CODE_GENERATION 可以并行（测试和代码同时生成后合并验证）

---

## 立即可落地的改进清单（优先级排序）

### P0 - 核心补强
1. **SessionContext** - 跨Agent的执行摘要传递，防止信息丢失
2. **pre-submit checklist** - 代码生成后必须过检查清单才能进入下一阶段
3. **files_to_generate planning** - CGAgent先规划文件列表

### P1 - 质量提升
4. **ConversationMemory** - 保存每轮对话历史，支持回溯
5. **统一Tool基类** - 为未来MCP接入做准备
6. **单一主配置文件** - 减少配置分散

### P2 - 性能与扩展
7. **并行Agent执行** - TD/CG可并行
8. **声明式Pipeline DSL** - 减少Python胶水代码

---

## 结论

我们框架的核心架构（状态机+多Agent+LLM-as-Judge）是业界验证的成熟模式。
主要差距在：**上下文管理**、**工具标准化**、**配置驱动**三个维度。

这三点改进完成后，框架将达到 SWE-agent/OpenHands 同等的工程成熟度。

