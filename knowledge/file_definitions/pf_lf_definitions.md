# AS400 文件定义 (PF/LF)

本文档定义框架使用的标准物理文件(PF)和逻辑文件(LF)结构。

## 订单主文件 (ORDPF)

### DDS 定义
``` DDS
A          R ORDREC
A            ORDNO         R               REFFLD(ORDNO)
A            CUSTNO        R               REFFLD(CUSTNO)
A            ITEMNO        R               REFFLD(ITEMNO)
A            ORDQTY        R               REFFLD(QTY)
A            STATUS        R               REFFLD(STATUS)
A            ORDDATE       R               REFFLD(DATE)
A            ORDTIME       R               REFFLD(TIME)
A          K ORDNO
```

### 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| ORDNO | CHAR(10) | 订单号，主键 |
| CUSTNO | CHAR(10) | 客户编号 |
| ITEMNO | CHAR(15) | 商品编号 |
| ORDQTY | PACKED(9,0) | 订单数量 |
| STATUS | CHAR(2) | 订单状态 |
| ORDDATE | DATE | 订单日期 |
| ORDTIME | TIME | 订单时间 |

### 状态值定义
| 状态 | 值 | 描述 |
|------|-----|------|
| 01 | 待处理 | 订单已创建，等待处理 |
| 02 | 已确认 | 客户有效，库存充足，订单确认 |
| 08 | 客户无效 | 客户不存在或无效 |
| 09 | 库存不足 | 库存不满足订单需求 |

## 客户主文件 (CUSTMF)

### DDS 定义
``` DDS
A          R CUSTREC
A            CUSTNO         R               REFFLD(CUSTNO)
A            CUSTNAME       R               REFFLD(NAME)
A            CUSTADDR       R               REFFLD(ADDR)
A            CUSTPHONE      R               REFFLD(PHONE)
A            CUSTSTATUS     R               REFFLD(STATUS)
A          K CUSTNO
```

### 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| CUSTNO | CHAR(10) | 客户编号，主键 |
| CUSTNAME | CHAR(50) | 客户名称 |
| CUSTADDR | CHAR(100) | 客户地址 |
| CUSTPHONE | CHAR(20) | 联系电话 |
| CUSTSTATUS | CHAR(1) | 客户状态 (A=活跃, I=无效) |

## 库存文件 (INVPF)

### DDS 定义
``` DDS
A          R INVREC
A            ITEMNO         R               REFFLD(ITEMNO)
A            ITEMNAME       R               REFFLD(NAME)
A            ONHAND         R               REFFLD(QTY)
A            PRICE          R               REFFLD(PRICE)
A            REORDER        R               REFFLD(QTY)
A          K ITEMNO
```

### 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| ITEMNO | CHAR(15) | 商品编号，主键 |
| ITEMNAME | CHAR(50) | 商品名称 |
| ONHAND | PACKED(9,0) | 当前库存数量 |
| PRICE | PACKED(9,2) | 单价 |
| REORDER | PACKED(9,0) | 最低库存阈值 |

## 处理日志文件 (ORDLOGPF)

### DDS 定义
``` DDS
A          R ORDLOGREC
A            LOGID         R               REFFLD(ID)
A            ORDNO         R               REFFLD(ORDNO)
A            CUSTNO        R               REFFLD(CUSTNO)
A            STATUS        R               REFFLD(STATUS)
A            MESSAGE       R               REFFLD(DESC)
A            LOGTS         R               REFFLD(TIMESTAMP)
A          K LOGID
```

### 字段说明
| 字段 | 类型 | 描述 |
|------|------|------|
| LOGID | CHAR(10) | 日志序列号，主键 |
| ORDNO | CHAR(10) | 关联订单号 |
| CUSTNO | CHAR(10) | 关联客户号 |
| STATUS | CHAR(2) | 处理结果状态 |
| MESSAGE | CHAR(50) | 处理消息 |
| LOGTS | TIMESTAMP | 日志时间戳 |

## 通用字段参考 (REFFLD)

### 系统字段定义
| 字段名 | 类型 | 描述 |
|--------|------|------|
| ID | CHAR(10) | 主键标识 |
| CUSTNO | CHAR(10) | 客户编号 |
| ORDNO | CHAR(10) | 订单编号 |
| ITEMNO | CHAR(15) | 商品编号 |
| QTY | PACKED(9,0) | 数量 |
| PRICE | PACKED(9,2) | 价格 |
| NAME | CHAR(50) | 名称 |
| ADDR | CHAR(100) | 地址 |
| PHONE | CHAR(20) | 电话 |
| STATUS | CHAR(2) | 状态码 |
| DATE | DATE | 日期 |
| TIME | TIME | 时间 |
| DESC | CHAR(50) | 描述 |
| TIMESTAMP | TIMESTAMP | 时间戳 |
