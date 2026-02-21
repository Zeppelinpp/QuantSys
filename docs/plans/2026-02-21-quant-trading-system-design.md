# QuantSys 量化交易系统设计文档

> **目标**: 构建一个不依赖第三方数据平台、自建行情数据库、支持因子挖掘和分钟级回测的量化交易系统，最终可用于 A 股实盘交易。

---

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI / API Layer                        │
│         (策略对话、回测触发、结果查询、模拟盘监控)              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Agent Core Service                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Skill Registry│  │ Context      │  │ LLM Client       │  │
│  │ (渐进披露)    │  │ Manager      │  │ (Claude API)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Backtest Engine                           │
│         (分钟级回测、虚拟账户、成交模拟、绩效分析)              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Market Data  │  │ Factor Store │  │ Strategy DB      │  │
│  │ (SQLite)     │  │ (预计算因子)  │  │ (代码路径+参数)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Data Collector                             │
│        (akshare采集、数据校验、增量更新、复权处理)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心设计原则

1. **模块化解耦** - 所有模块通过清晰接口交互，方便后续替换（如 SQLite → TimescaleDB）
2. **渐进式扩展** - MVP 聚焦核心闭环，预留 Mode C（全自动策略研究员）扩展空间
3. **Skill 驱动** - Agent 能力通过 Skill 目录动态发现，支持用户自定义扩展
4. **人机协作** - CLI 交互支持自然语言对话 + Slash Command + 文件引用

---

## 3. 项目结构

```
QuantSys/
├── quant_cli.py              # CLI 入口
├── agent/                    # Agent 核心
│   ├── core.py               # 主循环、Skill 发现与调度
│   ├── skill_registry.py     # 扫描 skills/ 目录，加载元数据
│   └── context_manager.py    # 对话上下文、渐进披露控制
│
├── skills/                   # Skill 目录（可扩展）
│   ├── backtest/SKILL.md     # 回测 Skill
│   ├── optimize/SKILL.md     # 参数优化 Skill
│   ├── data_query/SKILL.md   # 数据查询 Skill
│   ├── factor_analysis/      # 因子分析 Skill
│   └── code_generate/        # 代码生成 Skill
│
├── user_skills/              # 用户自定义 skill（gitignore）
│
├── backtest/                 # 回测引擎
│   ├── engine.py             # 事件驱动核心
│   ├── execution.py          # 撮合/滑点/手续费
│   ├── portfolio.py          # 虚拟账户管理
│   ├── metrics.py            # 绩效指标计算
│   └── recorder.py           # 结果记录
│
├── strategy/                 # 策略相关
│   ├── base.py               # 策略基类
│   ├── loader.py             # 策略加载器
│   ├── generated/            # Agent 生成策略存放
│   └── builtin/              # 内置示例策略
│
├── factor/                   # 因子库
│   ├── calculator.py         # 因子计算
│   ├── store.py              # 因子存储/查询
│   └── definitions/          # 预定义因子
│
├── data/                     # 数据层
│   ├── collector.py          # akshare 采集
│   ├── database.py           # SQLite 封装
│   ├── adjuster.py           # 复权处理
│   └── symbols.py            # 股票代码管理
│
├── adapter/                  # 实盘接口（预留）
│   ├── base.py
│   └── ptrade/               # Ptrade 适配器
│
├── config/                   # 配置管理
├── tests/                    # 测试
└── docs/                     # 文档
    └── plans/                # 设计文档存放
```

---

## 4. 数据层设计

### 4.1 SQLite 表结构

```sql
-- 原始行情数据（分钟级）
CREATE TABLE market_data (
    symbol TEXT NOT NULL,              -- 股票代码 000001.SZ
    timestamp DATETIME NOT NULL,       -- 时间戳
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL,       -- 成交量额
    adj_factor REAL,                   -- 复权因子
    PRIMARY KEY (symbol, timestamp)
);

-- 日线数据（用于快速筛选）
CREATE TABLE daily_data (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL,
    PRIMARY KEY (symbol, date)
);

-- 预计算因子库
CREATE TABLE factors (
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    ma_5 REAL, ma_10 REAL, ma_20 REAL, ma_60 REAL,
    rsi_14 REAL,
    macd_dif REAL, macd_dea REAL, macd_hist REAL,
    atr_14 REAL,
    PRIMARY KEY (symbol, timestamp)
);

-- 策略定义
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    code_path TEXT NOT NULL,           -- 策略代码文件路径
    params JSON,                       -- 参数空间配置
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 回测结果
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    start_date DATE,
    end_date DATE,
    symbols TEXT,                      -- 回测标的列表
    metrics JSON,                      -- 收益率、夏普、最大回撤等
    trades JSON,                       -- 成交记录
    equity_curve JSON,                 -- 权益曲线
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

-- 模拟盘账户
CREATE TABLE paper_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    initial_cash REAL DEFAULT 1000000,
    current_cash REAL,
    positions JSON,                    -- 当前持仓
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模拟盘交易记录
CREATE TABLE paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    symbol TEXT,
    side TEXT,                         -- BUY/SELL
    quantity INTEGER,
    price REAL,
    timestamp DATETIME,
    FOREIGN KEY (account_id) REFERENCES paper_accounts(id)
);
```

### 4.2 数据采集流程

1. **首次全量下载** - 使用 akshare 下载历史分钟数据
2. **每日增量更新** - 收盘后自动拉取当日数据
3. **复权处理** - 自动计算前复权因子，存储原始价格和复权因子

---

## 5. 回测引擎设计

### 5.1 事件驱动架构

```
时间序列遍历（分钟级）
        │
        ▼
   ┌─────────┐
   │ 新 Bar 到达 │
   └────┬────┘
        │
        ▼
   ┌─────────┐     ┌─────────┐
   │ 更新行情数据 │──▶│ 计算指标/因子 │
   └────┬────┘     └────┬────┘
        │               │
        ▼               ▼
   ┌─────────────────────────┐
   │    Strategy.on_bar()    │
   │  (用户自定义策略逻辑)     │
   └───────────┬─────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   ┌─────────┐     ┌─────────┐
   │ 生成信号  │     │ 更新持仓市值│
   │(买/卖/持有)│    │ (浮动盈亏) │
   └────┬────┘     └─────────┘
        │
        ▼
   ┌─────────┐
   │ 模拟成交  │◀── 考虑滑点、手续费、涨跌停限制
   │(虚拟账户) │
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ 记录交易  │
   └─────────┘
```

### 5.2 撮合规则（Best Practice）

| 机制 | 实现方式 |
|------|---------|
| **成交价格** | 下一 bar 开盘价成交（避免 lookahead bias） |
| **滑点** | 分级滑点：小单 1-2 bps，中单 5 bps，大单 10+ bps |
| **手续费** | 佣金万3（最低5元）+ 印花税千0.5（卖出）+ 过户费万0.01 |
| **涨跌停** | 涨停不买，跌停不卖 |
| **T+1** | 当日买入次日才能卖出 |

---

## 6. Agent Skill 系统设计

### 6.1 渐进披露三层机制

```
skills/
├── backtest/
│   ├── SKILL.md              ← Level 1: YAML frontmatter (常驻上下文)
│   │   ---
│   │   name: "回测策略"
│   │   description: "运行策略回测并生成绩效报告"
│   │   commands:
│   │     - /backtest
│   │   ---
│   │   ## 使用说明           ← Level 2: 判断相关时加载
│   │   当用户要求回测策略时，收集以下参数：...
│   │
│   │   @see ./advanced.md    ← Level 3+: 执行时按需加载
│   │   @see ./examples/
│   │
│   ├── advanced.md           ← 高级功能（部分成交、多标的权重）
│   ├── optimization.md       ← 参数优化指南
│   └── examples/
│       └── momentum_backtest.py
│
├── optimize/
│   └── SKILL.md
├── data_query/
│   └── SKILL.md
└── code_generate/
    └── SKILL.md
```

### 6.2 Skill 发现机制

Agent 启动时扫描 `skills/` 和 `user_skills/` 目录：

1. 读取每个 `SKILL.md` 的 YAML frontmatter（Level 1）
2. 构建可用技能索引：`{name, description, commands, path}`
3. 用户输入时，LLM 根据描述选择调用哪个 skill
4. 执行时再加载完整指令和引用的文件

### 6.3 人机协作交互示例

```
> quant chat

You: /backtest @strategies/momentum.py --start 2023-01-01
Agent: [调用 backtest skill] 运行完成：
       - 总收益率: 23.5%
       - 夏普比率: 1.34
       - 最大回撤: 12.8%
       需要我用 /optimize 优化参数吗？

You: 帮我写个RSI超卖反弹策略
Agent: [调用 code_generate skill] 已创建 strategies/generated/rsi_bounce_001.py

       ```python
       class RSIBounceStrategy(BaseStrategy):
           params = {'period': 14, 'oversold': 30}
           ...
       ```

       要现在回测吗？

You: @strategies/generated/rsi_bounce_001.py 把阈值改成25
Agent: [读取并修改文件] 已更新 oversold=25，重新回测？
```

---

## 7. 策略开发规范

### 7.1 策略基类

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseStrategy(ABC):
    """策略基类，所有策略必须继承此类"""

    # 策略参数定义（用于优化）
    params: Dict[str, Any] = {}

    def __init__(self, params: Dict[str, Any] = None):
        if params:
            self.params.update(params)
        self.data = None
        self.position = 0

    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """
        每个 bar 调用一次
        Args:
            bar: {symbol, timestamp, open, high, low, close, volume, ...}
        Returns:
            signal: {'action': 'BUY'|'SELL'|'HOLD', 'weight': float}
        """
        pass

    def on_start(self, context: Dict[str, Any]):
        """回测开始前调用"""
        pass

    def on_stop(self, context: Dict[str, Any]):
        """回测结束后调用"""
        pass
```

### 7.2 策略示例

```python
# strategies/builtin/momentum.py
from strategy.base import BaseStrategy

class MomentumStrategy(BaseStrategy):
    """简单动量策略：价格上穿20日均线买入，下穿卖出"""

    params = {
        'ma_period': 20,
        'position_pct': 0.95  # 仓位比例
    }

    def __init__(self, params=None):
        super().__init__(params)
        self.ma_history = []

    def on_bar(self, bar):
        close = bar['close']
        self.ma_history.append(close)

        if len(self.ma_history) < self.params['ma_period']:
            return {'action': 'HOLD'}

        ma20 = sum(self.ma_history[-self.params['ma_period']:]) / self.params['ma_period']

        if close > ma20 and self.position <= 0:
            return {'action': 'BUY', 'weight': self.params['position_pct']}
        elif close < ma20 and self.position > 0:
            return {'action': 'SELL', 'weight': 1.0}

        return {'action': 'HOLD'}
```

---

## 8. MVP 阶段范围

### 包含功能

- [x] SQLite 行情数据库（分钟级）
- [x] akshare 数据采集器
- [x] 分钟级事件驱动回测引擎
- [x] 基础绩效指标（收益、夏普、回撤）
- [x] Agent Skill 框架（渐进披露）
- [x] CLI 交互（chat + slash command）
- [x] 策略代码生成与优化
- [x] 模拟盘虚拟账户

### 不包含（后续迭代）

- [ ] 实时行情接入
- [ ] Ptrade 实盘对接
- [ ] 多因子模型（Barra 风格）
- [ ] 机器学习预测模块
- [ ] Web 可视化界面
- [ ] 分布式回测

---

## 9. 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 量化生态丰富 |
| 数据库 | SQLite | 零配置、足够支撑 MVP |
| 数据源 | akshare | 免费、A股数据齐全 |
| LLM | Claude API | 代码生成能力强 |
| CLI | Click / Typer | 现代 Python CLI 框架 |
| 数值计算 | NumPy, Pandas | 行业标准 |
| 回测 | 自研事件驱动 | 灵活可控 |
| 优化 | scikit-optimize | 贝叶斯优化 |

---

## 10. 风险与注意事项

1. **数据质量** - akshare 免费数据可能存在延迟或缺失，实盘前需验证
2. **过拟合风险** - 参数优化可能导致过度拟合历史数据
3. **滑点假设** - 分钟级回测无法完全模拟真实盘口冲击
4. **合规性** - 实盘交易需遵守监管规定，建议先充分模拟验证

---

*文档创建日期: 2026-02-21*
*版本: v1.0 MVP Design*
