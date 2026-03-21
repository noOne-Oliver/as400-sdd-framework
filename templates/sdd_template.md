# 软件设计说明书 (SDD)

## 1. 文档信息
- 程序名: {program_name}
- 版本: 1.0
- 作者: AS400 SDD Framework
- 日期: {{DATE}}

## 2. 变更记录
| 版本 | 日期 | 变更人 | 说明 |
| --- | --- | --- | --- |
| 1.0 | {{DATE}} | AS400 SDD Framework | 初始版本 |

## 3. 功能概述
{summary}

## 4. 系统环境
- 平台: IBM i / AS400
- 语言: RPGLE (free-format), CL
- 数据源: PF/LF

## 5. 文件定义 (PF/LF/DDL)
{data_entities}

## 6. 程序规格
### 6.1 处理流程
{process_steps}

```mermaid
flowchart TD
    A[读取待处理订单] --> B{{客户有效?}}
    B -- 否 --> C[状态=08 客户无效]
    B -- 是 --> D{{库存充足?}}
    D -- 否 --> E[状态=09 库存不足]
    D -- 是 --> F[状态=02 已确认]
    C --> G[写入日志]
    E --> G
    F --> G
```

### 6.2 输入输出参数
- 输入: ORDPF, CUSTMF, INVPF
- 输出: ORDPF(更新状态), ORDLOGPF(写入日志)

### 6.3 业务规则
{business_rules}

### 6.4 错误处理
- 文件打开失败: 记录日志并退出
- 链接记录失败: 根据业务规则返回状态
- 未处理异常: monitor/on-error 捕获并记录

## 7. 测试策略
- 正常流程 (状态=02)
- 客户无效 (状态=08)
- 库存不足 (状态=09)
- 日志写入验证

## 8. 部署说明
- 编译 RPGLE/CL
- 在测试库执行
- 验证日志与状态更新

## 9. 待澄清问题
{open_questions}
