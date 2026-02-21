# QuantSys - A股量化交易系统

QuantSys 是一个不依赖第三方数据平台、自建行情数据库、支持因子挖掘和分钟级回测的量化交易系统。

## 特性

- **自建数据库**: SQLite存储分钟级行情数据，支持增量更新
- **数据采集**: 基于akshare的A股数据采集，自动复权处理
- **回测引擎**: 事件驱动架构，支持分钟级回测
- **Agent系统**: LLM驱动的策略生成与优化
- **模拟盘**: 虚拟账户跟踪策略表现

## 快速开始

### 安装

```bash
pip install -e ".[dev]"
```

### 初始化数据库

```bash
quant init
```

### 下载数据

```bash
# 下载单只股票
quant data download --symbol 000001.SZ --start 2023-01-01 --end 2024-01-01

# 批量下载
quant data update --batch
```

### 运行回测

```bash
quant backtest strategies/builtin/momentum.py --start 2023-01-01 --end 2024-01-01
```

### 交互模式

```bash
quant chat
```

## 项目结构

```
quantsys/
├── agent/          # Agent核心
├── backtest/       # 回测引擎
├── data/           # 数据层
├── factor/         # 因子库
├── strategy/       # 策略相关
├── skills/         # Agent技能
└── config/         # 配置管理
```

## 配置

复制 `config/.env.example` 到 `.env` 并填写:

```bash
cp config/.env.example .env
```

编辑 `.env`:
```
ANTHROPIC_API_KEY=your_api_key_here
DATABASE_PATH=data/quantsys.db
```

## 开发

```bash
# 运行测试
pytest

# 代码格式化
black quantsys/ tests/
ruff check quantsys/ tests/
```

## 许可证

MIT
