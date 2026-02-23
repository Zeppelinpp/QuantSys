---
name: "代码生成"
description: "生成交易策略代码"
commands:
  - /generate
---

## 使用说明

根据用户描述生成交易策略代码。

### 参数

- **描述** - 策略逻辑描述 (必需)
- **名称** - 策略名称 (可选)
- **类型** - 策略类型：momentum, mean_reversion, breakout (可选)

### 示例

```
/generate "RSI超卖反弹策略，RSI<30买入，RSI>70卖出"
/generate "双均线金叉策略" --name dual_ma --type momentum
```

### 因子策略生成

```
/generate "用WQ002和WQ017的等权组合做多因子策略" --factors WQ002 WQ017
/generate "当WQ002>0.7买入，<0.3卖出" --factors WQ002
```

### 输出

- 生成的策略代码
- 保存路径
- 使用建议

@see ./templates/ - 代码模板
