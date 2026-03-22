# OpenSpec 概念定义

## 概述

**OpenSpec** 是 AS400 SDD 框架中用于描述系统规范的开放标准。它定义了规范的生命周期、类型、验证规则和最佳实践。

## 核心理念

1. **声明式规范** - 所有规范以结构化 Markdown/YAML 形式存在
2. **可版本化** - 规范可追溯、可对比、可回滚
3. **可验证** - 规范通过 Judge 自动校验
4. **开放协作** - 多 Agent 可同时访问和引用同一规范

## OpenSpec 类型

### 1. RequirementSpec (需求规范)
| 属性 | 值 |
|------|-----|
| 来源 | RA Agent |
| 格式 | `analysis.md` |
| 关键字段 | program_name, process_steps, data_entities, business_rules, open_questions |
| Judge 方法 | `evaluate_spec` |

### 2. DesignSpec (设计规范/SDD)
| 属性 | 值 |
|------|-----|
| 来源 | SD Agent |
| 格式 | `sdd.md` |
| 关键字段 | 程序入口, 业务规则, 处理流程, 错误处理, 测试策略, 文件定义 |
| Judge 方法 | `evaluate_spec` |

### 3. TestSpec (测试规范)
| 属性 | 值 |
|------|-----|
| 来源 | TD Agent |
| 格式 | `tests.md` |
| 关键字段 | TC-ID, 前置条件, 步骤, 预期结果 |
| Judge 方法 | `evaluate_tests` |

### 4. CodeSpec (代码规范)
| 属性 | 值 |
|------|-----|
| 来源 | CG Agent |
| 格式 | `{program_name}.rpgle` |
| 关键字段 | ctl-opt, dcl-f, monitor, on-error, 状态处理 |
| Judge 方法 | `evaluate_code` |

## 规范生命周期

```
需求输入
    ↓
[RequirementSpec] ← RA Agent
    ↓
[DesignSpec] ← SD Agent (SDD)
    ↓
[TestSpec] ← TD Agent
    ↓
[CodeSpec] ← CG Agent
    ↓
[ReviewSpec] ← CR Agent
    ↓
[ExecutionReport] ← TE Agent
```

## 验证规则

### RequirementSpec/DesignSpec 必须包含
- `#` 标题标记
- `程序` 或 `程序名`
- `业务规则`
- `处理流程`
- `错误处理`
- `测试` 相关描述

### TestSpec 必须包含
- `TC-` 测试用例编号
- `前置条件`
- `步骤`
- `预期结果`
- 覆盖 02/08/09 状态

### CodeSpec 必须包含
- `ctl-opt` 编译选项
- `dcl-f` 文件声明
- `monitor` / `on-error` 错误处理
- 状态处理分支 (02/08/09)
- 日志写入 (ORDLOGPF)

## StageSpec 配置

StageDriver 使用 YAML 配置定义 stage：

```yaml
pipeline:
  stages:
    - name: REQUIREMENTS
      agent: ra_agent
      input_keys: ["requirement_text"]
      output_key: "analysis"
      judge: "evaluate_spec"
      artifact: "{output_dir}/analysis.md"
```

## 最佳实践

1. **先规范后实现** - 遵循 SDD 理念，规范驱动开发
2. **规范即文档** - 规范文档直接可作为项目文档
3. **自动化验证** - 每阶段规范必须通过 Judge 校验
4. **上下文透明** - 规范中包含执行上下文，便于追溯
5. **单一数据源** - 规范存储在单一知识库，避免碎片化
