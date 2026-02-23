# 因子库与 Agent 集成设计文档

> **目标**: 构建结构化因子库（Operator 算子 + YAML 目录 + Python 实现），让 Agent 具备因子浏览、计算和策略生成能力，同时升级 Agent system prompt 为量化专家身份。

---

## 1. 决策摘要

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 方向 | 因子库优先，ML 后续 | 因子库是 ML 的前置依赖 |
| 架构模式 | 混合模式（引擎 + Agent 自由生成） | 引擎提供基础能力，Agent 编排组合 |
| 因子范围 | 精选 ~20 个经典因子起步 | 覆盖主要类别，验证算子库完整性 |
| 数据源 | WorldQuant 101（论文公开） | 公式化因子，仅需 OHLCV，无外部依赖 |
| 计算策略 | 回测前一次性预计算 | 数据量小，pandas 向量化高效 |

---

## 2. 模块结构

```
quantsys/factor/
├── __init__.py
├── operators.py         # ~30 个基础算子（rank, delta, ts_rank, correlation...）
├── registry.py          # 因子注册表：发现、检索、列出因子
├── engine.py            # 计算引擎：调用算子组合，批量计算因子值
├── definitions/         # YAML 因子目录（Agent 可读的结构化元数据）
│   ├── wq101_momentum.yaml
│   ├── wq101_reversal.yaml
│   ├── wq101_volatility.yaml
│   └── wq101_liquidity.yaml
└── library/             # Python 因子实现
    ├── __init__.py
    ├── wq101.py         # WorldQuant 101 因子
    └── classic.py       # 经典学术因子（Amihud 等，预留）

quantsys/skills/
└── factor_analysis/
    └── SKILL.md         # /factor 命令

quantsys/agent/
└── core.py              # System prompt 升级
```

---

## 3. 算子库 (operators.py)

所有算子为纯函数，输入 `pd.Series`，输出 `pd.Series`，无状态可组合。

### 时间序列算子

| 算子 | 含义 | pandas 实现 |
|------|------|------------|
| `delay(x, d)` | 滞后 d 期 | `x.shift(d)` |
| `delta(x, d)` | x[t] - x[t-d] | `x - x.shift(d)` |
| `ts_sum(x, d)` | 滚动求和 | `x.rolling(d).sum()` |
| `ts_mean(x, d)` | 滚动均值 | `x.rolling(d).mean()` |
| `ts_stddev(x, d)` | 滚动标准差 | `x.rolling(d).std()` |
| `ts_min(x, d)` / `ts_max(x, d)` | 滚动极值 | `.rolling(d).min()` / `.max()` |
| `ts_argmin(x, d)` / `ts_argmax(x, d)` | 滚动极值位置 | `.rolling(d).apply(np.argmin)` |
| `ts_rank(x, d)` | 滚动排名百分位 | `.rolling(d).apply(rank_pct)` |
| `ts_corr(x, y, d)` | 滚动相关系数 | `x.rolling(d).corr(y)` |
| `ts_cov(x, y, d)` | 滚动协方差 | `x.rolling(d).cov(y)` |
| `decay_linear(x, d)` | 线性衰减加权均值 | `.rolling(d).apply(weighted_mean)` |
| `ts_product(x, d)` | 滚动乘积 | `.rolling(d).apply(np.prod)` |

### 截面算子

| 算子 | 含义 | 说明 |
|------|------|------|
| `rank(x)` | 截面百分位排名 | 多股票跨股排名；单股退化为时序归一化 |
| `scale(x)` | 归一化 | `x / x.abs().sum()` |

### 辅助算子

| 算子 | 含义 |
|------|------|
| `returns(close)` | `close.pct_change()` |
| `vwap(amount, volume)` | `amount / volume` |
| `adv(volume, d)` | `ts_mean(volume, d)` |
| `signedpower(x, a)` | `sign(x) * abs(x)^a` |
| `log(x)` / `sign(x)` / `abs(x)` | 数学函数 |

---

## 4. YAML 因子目录格式

```yaml
# definitions/wq101_reversal.yaml
factors:
  - id: "WQ002"
    name: "Alpha#002"
    source: "WorldQuant 101"
    category: "reversal"
    formula: "-1 * ts_corr(rank(delta(log(volume), 2)), rank((close - open) / open), 6)"
    description: "Volume change and price change correlation reversal signal"
    data_requirements: ["close", "open", "volume"]
    lookback_window: 8
    compute_fn: "quantsys.factor.library.wq101:alpha002"
    tags: ["reversal", "volume"]
    notes: "Effective in high-volatility regimes"
```

字段说明：
- `formula` — 论文原始公式（Agent 理解用，不直接执行）
- `compute_fn` — Python 实现引用（`module:function`），Registry 据此调度
- `data_requirements` — 所需输入列，用于数据校验
- `lookback_window` — 最小历史窗口长度

---

## 5. 精选 20 因子清单

| # | ID | 类别 | 简述 | 核心算子 |
|---|-----|------|------|---------|
| 1 | Alpha#002 | 反转 | 成交量与收盘价变化的相关性反转 | ts_corr, delta, rank |
| 2 | Alpha#003 | 反转 | 成交量与开盘价相关性反转 | ts_corr, rank |
| 3 | Alpha#004 | 反转 | 低位排名反转 | ts_rank, rank |
| 4 | Alpha#006 | 反转 | 开盘价与成交量的相关性 | ts_corr |
| 5 | Alpha#008 | 动量 | 开盘×收益-延迟收盘 | delay, rank |
| 6 | Alpha#009 | 动量 | 条件价格变动持续性 | ts_min, ts_max, delta |
| 7 | Alpha#012 | 动量 | 成交量方向×价格变动 | sign, delta |
| 8 | Alpha#014 | 反转 | 收益与成交量的滞后相关性 | returns, delta, ts_corr |
| 9 | Alpha#017 | 动量 | 收盘价排名的时序排名 | ts_rank, rank |
| 10 | Alpha#020 | 反转 | 开盘价相对高低的排名 | rank, delay |
| 11 | Alpha#023 | 动量 | 条件均值偏移 | ts_mean, delta |
| 12 | Alpha#026 | 反转 | 最大值与相关性交叉 | ts_max, ts_corr, rank |
| 13 | Alpha#028 | 波动率 | 成交量加权价格偏离度 | ts_corr, adv, scale |
| 14 | Alpha#033 | 反转 | 开盘价/收盘价比值排名 | rank |
| 15 | Alpha#035 | 动量 | 多窗口收益排名 | ts_rank, returns, delay |
| 16 | Alpha#041 | 动量 | 高低价差的幂变换 | signedpower, rank |
| 17 | Alpha#044 | 反转 | 最高价与成交量的相关性 | ts_corr, rank |
| 18 | Alpha#053 | 反转 | 收盘价相对高低位置 | ts_min, ts_max, delay |
| 19 | Alpha#054 | 波动率 | 开收差与高低差的比值 | rank, signedpower |
| 20 | Alpha#101 | 反转 | 开收价与高低价交叉 | rank |

选择原则：全部只依赖 OHLCV+amount；覆盖动量/反转/波动率三类；算子覆盖广。

---

## 6. Registry + Engine

### FactorMeta

```python
@dataclass
class FactorMeta:
    id: str
    name: str
    source: str
    category: str
    formula: str
    description: str
    data_requirements: List[str]
    lookback_window: int
    compute_fn: str          # "module.path:function_name"
    tags: List[str]
    notes: str
```

### FactorRegistry

```python
class FactorRegistry:
    def discover(self) -> None:
        """Scan definitions/*.yaml, resolve compute_fn to callable."""

    def get(self, factor_id: str) -> FactorMeta
    def list_factors(self, category: str = None) -> List[FactorMeta]
    def search(self, query: str) -> List[FactorMeta]

    def get_summary(self) -> str:
        """Level 2 summary for agent context (id + name + description only)."""

    def get_detail(self, factor_ids: List[str]) -> str:
        """Level 3 full definitions for selected factors."""
```

### FactorEngine

```python
class FactorEngine:
    def __init__(self, registry: FactorRegistry): ...

    def compute(self, factor_id: str, df: pd.DataFrame) -> pd.Series:
        """Compute a single factor via registered compute_fn."""

    def compute_batch(self, factor_ids: List[str], df: pd.DataFrame) -> pd.DataFrame:
        """Compute multiple factors, returns df with factor_{id} columns."""

    def validate_data(self, factor_id: str, df: pd.DataFrame) -> bool:
        """Check df has required columns and sufficient rows."""
```

---

## 7. 回测引擎集成

**不改动 BacktestEngine 核心逻辑**，仅两处轻量变动：

### BaseStrategy 新增因子支持

```python
class BaseStrategy(ABC):
    # New fields
    required_factors: List[str] = []
    factor_data: Optional[pd.DataFrame] = None

    def _get_factor(self, bar: BarEvent, factor_id: str) -> Optional[float]:
        """Lookup pre-computed factor value for current bar's timestamp."""
        if self.factor_data is None:
            return None
        mask = self.factor_data["timestamp"] == bar.timestamp
        row = self.factor_data.loc[mask]
        if row.empty:
            return None
        col = f"factor_{factor_id}"
        return row[col].iloc[0] if col in row.columns else None
```

### BacktestEngine.run() 注入因子数据

```python
# After _load_data(), before strategy.on_start():
if hasattr(self.strategy, 'required_factors') and self.strategy.required_factors:
    from quantsys.factor.registry import FactorRegistry
    from quantsys.factor.engine import FactorEngine
    registry = FactorRegistry()
    registry.discover()
    engine = FactorEngine(registry)
    self.strategy.factor_data = engine.compute_batch(
        self.strategy.required_factors, data
    )
```

### 生成策略示例

```python
class AlphaComboStrategy(BaseStrategy):
    name = "AlphaComboStrategy"
    required_factors = ["WQ002", "WQ017", "WQ041"]
    params = {"buy_threshold": 0.7, "sell_threshold": 0.3, "position_pct": 0.95}

    def on_bar(self, bar: BarEvent) -> dict:
        alpha002 = self._get_factor(bar, "WQ002")
        alpha017 = self._get_factor(bar, "WQ017")
        alpha041 = self._get_factor(bar, "WQ041")

        if any(v is None for v in [alpha002, alpha017, alpha041]):
            return {"action": "HOLD"}

        composite = (alpha002 + alpha017 + alpha041) / 3

        if composite > self.params["buy_threshold"] and self.position <= 0:
            return {"action": "BUY", "weight": self.params["position_pct"]}
        elif composite < self.params["sell_threshold"] and self.position > 0:
            return {"action": "SELL", "weight": 1.0}

        return {"action": "HOLD"}
```

---

## 8. Agent 集成

### 8.1 新 Skill：/factor

```yaml
# skills/factor_analysis/SKILL.md
---
name: "因子分析"
description: "浏览、检索和使用量化因子库，支持因子计算和因子策略生成"
commands:
  - /factor
---
```

支持子命令：
- `/factor list` — 展示因子分类列表
- `/factor search <关键词>` — 按类别/标签/描述语义搜索
- `/factor show <ID>` — 展示完整因子定义
- `/factor compute <ID> --symbol <SYMBOL>` — 计算因子值
- `/factor strategy <ID1> <ID2> ...` — 生成因子组合策略

### 8.2 渐进式上下文注入

| 层级 | 触发时机 | 注入字段 | Token 量 |
|------|---------|---------|---------|
| Level 1 | 始终 | Skill frontmatter（name + description） | ~50 |
| Level 2 | `/factor` 或提到因子 | 全部因子的 id, name, category, description, tags | ~600 |
| Level 3 | Agent 选定因子后 | 选中因子的 formula, compute_fn, data_requirements, lookback_window, notes | ~150/因子 |

### 8.3 增强 StrategyGenerator

当检测到因子相关请求时，在 LLM prompt 中注入因子 Level 3 上下文：

```python
def _generate_with_llm(self, description, class_name, strategy_type, factor_ids=None):
    prompt_parts = [base_prompt]

    if factor_ids:
        registry = FactorRegistry()
        factor_context = registry.get_detail(factor_ids)
        prompt_parts.append(f"""
This strategy uses pre-computed factors from the QuantSys factor library.
Use self._get_factor(bar, factor_id) to access values in on_bar().
Declare required_factors = {factor_ids} in the class.

Factor definitions:
{factor_context}
""")
```

---

## 9. Agent System Prompt 升级

当前 prompt 过于简陋，缺乏领域知识。升级为量化专家身份：

### 新 System Prompt

```
You are QuantSys Agent — a senior quantitative analyst and trading system expert
specializing in A-share (China) markets.

## Identity & Expertise

You have deep knowledge in:
- Factor investing: WorldQuant 101 alphas, Fama-French factors, Barra risk model
- Technical analysis: price-volume patterns, momentum, mean-reversion, volatility
- A-share specifics: T+1 settlement, 10% daily price limit, lot size 100 shares,
  stamp duty on sells, transfer fees, commission structure (万3 minimum 5 yuan)
- Backtest methodology: lookahead bias prevention, survivorship bias, overfitting
  risks, walk-forward validation, out-of-sample testing
- Portfolio construction: position sizing, risk budgeting, diversification

## Behavior Guidelines

- Be precise with numbers: report returns as percentages, Sharpe to 2 decimals
- Always warn about overfitting risk when optimization results look too good
- Suggest benchmark comparison (e.g. CSI 300) when presenting backtest results
- When generating strategies, prefer simple and robust logic over complex models
- Proactively suggest data quality checks before backtesting
- Communicate in the same language as the user (Chinese or English)

## Available Commands
{commands}

## Workflow

1. Understand the user's intent (research, backtest, generate, analyze)
2. Select the appropriate skill/command
3. Gather required parameters (ask if missing)
4. Execute and present results with actionable interpretation
5. Suggest logical next steps (optimize parameters? try different factors? compare?)
```

### 变动点

| 增强项 | 作用 |
|--------|------|
| 量化专家身份 | LLM 角色设定，提升回答专业度 |
| A 股特定知识 | T+1、涨跌停、手续费等，避免生成违规策略 |
| 回测方法论 | 主动提示过拟合、前视偏差等常见陷阱 |
| 因子投资知识 | 支持因子库功能的专业对话 |
| 行为准则 | 数据精度、风险提示、下一步建议 |

---

## 10. 变动范围总结

### 全新文件

| 文件 | 用途 |
|------|------|
| `quantsys/factor/__init__.py` | 模块入口 |
| `quantsys/factor/operators.py` | ~30 个基础算子 |
| `quantsys/factor/registry.py` | 因子注册表 |
| `quantsys/factor/engine.py` | 计算引擎 |
| `quantsys/factor/definitions/*.yaml` | 4 个 YAML 分类文件 |
| `quantsys/factor/library/__init__.py` | 库入口 |
| `quantsys/factor/library/wq101.py` | 20 个因子实现 |
| `quantsys/factor/library/classic.py` | 预留 |
| `quantsys/skills/factor_analysis/SKILL.md` | /factor 技能 |
| `tests/unit/test_operators.py` | 算子单元测试 |
| `tests/unit/test_factor_engine.py` | 引擎集成测试 |

### 修改文件

| 文件 | 变动 | 范围 |
|------|------|------|
| `quantsys/strategy/base.py` | 新增 `required_factors`, `factor_data`, `_get_factor()` | ~15 行 |
| `quantsys/backtest/engine.py` | `run()` 中新增因子预计算注入 | ~5 行 |
| `quantsys/skills/code_generate/generator.py` | LLM prompt 注入因子上下文 | ~30 行 |
| `quantsys/skills/code_generate/SKILL.md` | 更新说明 | 小 |
| `quantsys/agent/core.py` | System prompt 重写 | ~30 行 |

---

## 11. 后续扩展（不在本期范围）

- **广发经典因子**：实现 Amihud 非流动性因子等学术因子到 `classic.py`
- **因子评价体系**：IC/IR/RankIC 计算，因子有效性检验
- **因子预计算存储**：大量股票时将因子值写入 SQLite `factor_values` 表
- **ML 因子挖掘**：基于 OHLCV 的深度学习因子（Qlib/AlphaForge 路线）
- **多因子模型**：Barra 风格风险模型，因子正交化

---

*文档创建日期: 2026-02-23*
*版本: v1.0*
