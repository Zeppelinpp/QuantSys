---
name: "数据查询"
description: "查询市场数据和股票信息"
commands:
  - /data
---

## 使用说明

查询市场数据、股票信息或数据状态。

### 子命令

- `status` - 查看数据状态
- `download` - 下载历史数据
- `update` - 增量更新数据

### 示例

```
/data status
/data download --symbol 000001.SZ --start 2023-01-01 --end 2024-01-01
/data update --batch
```

### 输出

- 数据库记录数
- 数据时间范围
- 下载进度
