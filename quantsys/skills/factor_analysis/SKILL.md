---
name: "因子分析"
description: "浏览、检索和使用量化因子库（WorldQuant 101等），支持因子计算和因子策略生成"
commands:
  - /factor
---

## 使用说明

当用户涉及因子相关操作时，加载因子注册表并提供以下能力：

### 子命令

- `/factor list [类别]` — 展示所有或按类别筛选的因子列表
- `/factor search <关键词>` — 按名称、描述、标签搜索因子
- `/factor show <ID>` — 展示因子完整定义（公式、参数、数据要求）
- `/factor compute <ID> --symbol <代码> [--start DATE] [--end DATE]` — 计算因子值
- `/factor strategy <ID1> <ID2> ...` — 基于选定因子生成组合策略

### 使用因子注册表

```python
from quantsys.factor.registry import FactorRegistry

registry = FactorRegistry()
registry.discover()

# Level 2: 因子摘要
summary = registry.get_summary()

# Level 3: 选定因子详情
detail = registry.get_detail(["WQ002", "WQ017"])
```

### 计算因子值

```python
from quantsys.factor.engine import FactorEngine

engine = FactorEngine(registry)
result = engine.compute("WQ002", df)
batch = engine.compute_batch(["WQ002", "WQ017"], df)
```

### 生成因子策略

当用户要求基于因子生成策略时：
1. 使用 `registry.get_detail()` 获取选定因子的完整定义
2. 将因子定义注入 LLM prompt
3. 生成的策略需声明 `required_factors` 并使用 `self._get_factor(bar, factor_id)`
4. 保存到 `quantsys/strategy/generated/`

### 因子类别

- **momentum** — 动量因子：捕捉价格趋势延续
- **reversal** — 反转因子：捕捉价格均值回归
- **volatility** — 波动率因子：利用波动率变化获利

### 示例

```
/factor list momentum
/factor show WQ002
/factor compute WQ002 --symbol 000001.SZ --start 2024-01-01 --end 2024-12-31
/factor strategy WQ002 WQ017 WQ041
```
