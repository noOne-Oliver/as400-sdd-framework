# AS400 业务规则库

本文档定义框架使用的标准业务规则，供 Agent 在生成代码时参考。

## 订单处理规则 (ORDPRC)

### 核心业务规则

#### 规则 1: 订单状态机
```
01 (待处理) → 02 (已确认)
             → 08 (客户无效)
             → 09 (库存不足)
```

**状态转换条件**:
- **→ 02**: 客户有效(CUSTMF存在且STATUS='A') 且 库存充足(INVPF.ONHAND >= ORDQTY)
- **→ 08**: 客户无效(CUSTMF不存在 或 STATUS<>'A')
- **→ 09**: 库存不足(INVPF.ONHAND < ORDQTY)

#### 规则 2: 客户有效性检查
```
IF NOT EXISTS(CUSTMF WHERE CUSTNO = ORDPF.CUSTNO)
   OR CUSTMF.STATUS != 'A'
THEN
   STATUS = '08'
   MESSAGE = '客户无效'
END
```

#### 规则 3: 库存可用性检查
```
IF INVPF.ONHAND < ORDPF.ORDQTY
THEN
   STATUS = '09'
   MESSAGE = '库存不足'
END
```

#### 规则 4: 库存扣减
```
IF STATUS = '02'
THEN
   INVPF.ONHAND = INVPF.ONHAND - ORDPF.ORDQTY
   UPDATE INVPF
END
```

#### 规则 5: 订单状态更新
```
UPDATE ORDPF
SET STATUS = {新状态}
WHERE ORDNO = {ORDNO}
```

#### 规则 6: 处理日志写入
```
每次订单处理后，必须写入 ORDLOGPF:
- ORDNO: 订单号
- CUSTNO: 客户号
- STATUS: 处理结果状态
- MESSAGE: 处理消息
- LOGTS: 当前时间戳
```

### RPGLE 编码规范

#### 错误处理 (monitor/on-error)
``` RPGLE
monitor;
    // 主处理逻辑
    // 文件打开、读写操作
on-error;
    // 统一错误处理
    WriteOrderLog('SYSTEM': 'SYSTEM': '99': '未处理异常');
    *inlr = *on;
    return;
endmon;
```

#### 文件声明 (dcl-f)
``` RPGLE
dcl-f ORDPF usage(*update:*input) keyed usropn;
dcl-f CUSTMF usage(*input) keyed usropn;
dcl-f INVPF usage(*update:*input) keyed usropn;
dcl-f ORDLOGPF usage(*output) usropn;
```

#### 编译选项 (ctl-opt)
``` RPGLE
**FREE
ctl-opt dftactgrp(*no) actgrp(*new) option(*srcstmt:*nodebugio);
```

#### 状态码使用
``` RPGLE
// 正常结束
*inlr = *on;

// 异常退出
*inlr = *off;
return;
```

### 循环读取模式
``` RPGLE
setll *loval ORDPF;
dou EndOfFile;
    reade '01' ORDPF OrderRec;
    if %eof(ORDPF);
        EndOfFile = *on;
        leave;
    endif;
    // 处理逻辑
enddo;
```

### 命名约定

| 实体 | 前缀 | 示例 |
|------|------|------|
| 程序 | - | ORDPRC |
| 文件 | PF/MF/LF | ORDPF, CUSTMF |
| 记录 | Rec | OrderRec, CustRec |
| 子过程 | - | IsValidCustomer |
| 变量 | - | EndOfFile, ProcessStatus |
| 日志记录 | LogR | OrdLogR |

## 标准错误代码

| 代码 | 描述 | 处理 |
|------|------|------|
| 01 | 待处理 | 初始状态 |
| 02 | 已确认 | 处理成功 |
| 08 | 客户无效 | 业务拒绝 |
| 09 | 库存不足 | 业务拒绝 |
| 99 | 系统异常 | 需要人工介入 |
