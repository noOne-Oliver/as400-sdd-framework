# AS400 RPGLE 编码规范

本文档定义框架生成代码的编码标准和最佳实践。

## 1. 文件结构

### 1.1 头部声明
``` RPGLE
**FREE
ctl-opt dftactgrp(*no) actgrp(*new) option(*srcstmt:*nodebugio);
```

### 1.2 文件声明 (dcl-f)
``` RPGLE
// 更新+读取文件
dcl-f ORDPF usage(*update:*input) keyed usropn;

// 仅读取文件
dcl-f CUSTMF usage(*input) keyed usropn;

// 仅写入文件
dcl-f ORDLOGPF usage(*output) usropn;
```

### 1.3 数据结构 (dcl-ds)
``` RPGLE
dcl-ds OrderRec extname('ORDPF') end-ds;
dcl-ds CustRec extname('CUSTMF') end-ds;
```

### 1.4 变量声明 (dcl-s)
``` RPGLE
dcl-s EndOfFile ind inz(*off);
dcl-s ProcessStatus char(2) inz(*blanks);
dcl-s ProcessMessage char(50) inz(*blanks);
```

## 2. 主程序结构

``` RPGLE
dcl-proc Main;
    // 打开文件
    open ORDPF;
    open CUSTMF;
    open INVPF;
    open ORDLOGPF;

    monitor;
        // 主循环处理
        setll *loval ORDPF;
        dou EndOfFile;
            reade '01' ORDPF OrderRec;
            if %eof(ORDPF);
                EndOfFile = *on;
                leave;
            endif;

            // 业务处理
            // ...

        enddo;

    on-error;
        // 错误处理
        WriteOrderLog('SYSTEM': 'SYSTEM': '99': '未处理异常');
    endmon;

    *inlr = *on;
end-proc;
```

## 3. 子过程规范

### 3.1 子过程定义
``` RPGLE
dcl-proc IsValidCustomer;
    dcl-pi *n ind;
        customerNumber packed(9:0) const;
    end-pi;

    // 实现
    chain customerNumber CUSTMF CustRec;
    return not %eof(CUSTMF);
end-proc;
```

### 3.2 参数传递
- 使用 `const` 修饰输入参数
- 使用 `packed(n:m)` 表示打包十进制数
- 返回 `*n ind` 表示布尔值

## 4. 错误处理

### 4.1 monitor/on-error 结构
``` RPGLE
monitor;
    // 可能失败的代码
    update ORDPF OrderRec;
on-error;
    // 错误处理逻辑
    WriteOrderLog('ERR': 'ERR': '99': '更新失败');
endmon;
```

### 4.2 状态码判断
``` RPGLE
select;
    when ProcessStatus = '02';
        // 正常处理
    when ProcessStatus = '08';
        // 客户无效
    when ProcessStatus = '09';
        // 库存不足
endsl;
```

## 5. 日志写入

``` RPGLE
dcl-proc WriteOrderLog;
    dcl-pi *n;
        orderNumber char(10) const;
        customerNumber char(10) const;
        resultStatus char(2) const;
        resultMessage char(50) const;
    end-pi;

    clear OrdLogR;
    OrdLogR.ORDNO = orderNumber;
    OrdLogR.CUSTNO = customerNumber;
    OrdLogR.STATUS = resultStatus;
    OrdLogR.MESSAGE = resultMessage;
    OrdLogR.LOGTS = %timestamp();
    write ORDLOGPF OrdLogR;
end-proc;
```

## 6. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 程序 | 大写，4-6字符 | ORDPRC |
| 文件 | 大写，PF/MF/LF后缀 | ORDPF, CUSTMF |
| 记录 | Rec 后缀 | OrderRec, CustRec |
| 子过程 | 驼峰命名 | IsValidCustomer |
| 变量 | 驼峰命名 | endOfFile |
| 指示器 | *off/*on 初始化 | EndOfFile ind inz(*off) |

## 7. 代码格式化

- 使用 `**FREE` 自由格式
- 缩进 2 空格
- 操作符前后有空格
- 逗号后跟空格
- 注释使用 `//` 或 `/* */`
