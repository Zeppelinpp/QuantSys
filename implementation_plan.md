# QuantSys 量化交易系统 - 实施计划

> 基于设计文档: `docs/plans/2026-02-21-quant-trading-system-design.md`
> 创建日期: 2026-02-21

---

## 阶段概览

| 阶段 | 名称 | 预计工期 | 核心交付物 |
|------|------|----------|-----------|
| Phase 1 | 基础设施搭建 | 2-3 天 | 项目结构、数据库、配置管理 |
| Phase 2 | 数据采集层 | 3-4 天 | akshare采集器、数据校验、复权处理 |
| Phase 3 | 回测引擎核心 | 5-7 天 | 事件驱动引擎、撮合系统、绩效分析 |
| Phase 4 | Agent Skill 框架 | 4-5 天 | Skill注册表、上下文管理、LLM客户端 |
| Phase 5 | CLI 与交互 | 3-4 天 | 命令行界面、对话系统、Slash Command |
| Phase 6 | 策略系统 | 4-5 天 | 策略基类、代码生成、参数优化 |
| Phase 7 | 模拟盘系统 | 2-3 天 | 虚拟账户、交易记录、监控 |
| Phase 8 | 集成测试 | 3-4 天 | 端到端测试、性能优化、文档完善 |

**总计预估: 26-35 天（MVP版本）**

---

## Phase 1: 基础设施搭建

### 1.1 项目结构初始化
**文件变更:**
- Create `pyproject.toml` - 项目配置和依赖
- Create `README.md` - 项目说明
- Create `.gitignore` - Python项目忽略规则
- Create `config/settings.yaml` - 配置文件模板

**关键决策:**
- 使用 `pydantic-settings` 进行配置管理
- 使用 `loguru` 进行日志记录
- 目录结构采用扁平化设计，避免过度嵌套

### 1.2 数据库基础
**文件变更:**
- Create `data/database.py` - SQLite连接池和封装
- Create `data/schema.sql` - 数据库表结构定义
- Create `data/migrations/` - 数据库迁移脚本

**实现要点:**
```python
# data/database.py 核心接口
class Database:
    def __init__(self, db_path: str)
    def execute(self, sql: str, params: tuple = None) -> sqlite3.Cursor
    def fetchall(self, sql: str, params: tuple = None) -> List[Dict]
    def fetchone(self, sql: str, params: tuple = None) -> Optional[Dict]
    def create_tables(self)  # 执行schema.sql
```

### 1.3 配置管理
**文件变更:**
- Create `config/__init__.py` - 配置模块入口
- Create `config/settings.py` - Pydantic Settings模型
- Create `config/.env.example` - 环境变量示例

**验收标准:**
- [ ] 配置文件支持 YAML 和 环境变量覆盖
- [ ] 数据库路径、akshare配置、LLM API密钥可配置
- [ ] 开发/测试/生产环境配置分离

---

## Phase 2: 数据采集层

### 2.1 akshare 采集器
**文件变更:**
- Create `data/collector.py` - 数据采集主类
- Create `data/symbols.py` - 股票代码管理
- Create `tests/data/test_collector.py` - 单元测试

**核心功能:**
```python
class DataCollector:
    def download_minute_data(self, symbol: str, start: str, end: str) -> pd.DataFrame
    def download_daily_data(self, symbol: str, start: str, end: str) -> pd.DataFrame
    def get_stock_list(self) -> List[str]  # A股全量代码
    def incremental_update(self, symbols: List[str])  # 增量更新
```

### 2.2 数据校验与清洗
**文件变更:**
- Create `data/validator.py` - 数据质量检查
- Create `data/cleaner.py` - 数据清洗逻辑

**校验规则:**
- 价格范围检查 (0 < price < 10000)
- 成交量非负检查
- 时间戳连续性检查
- OHLC逻辑检查 (low <= open, close <= high)

### 2.3 复权处理
**文件变更:**
- Create `data/adjuster.py` - 复权计算

**算法要点:**
- 从akshare获取除权除息数据
- 计算前复权因子
- 存储原始价格和复权因子（不直接存储复权后价格）

### 2.4 数据CLI工具
**文件变更:**
- Create `scripts/init_db.py` - 初始化数据库
- Create `scripts/update_data.py` - 数据更新脚本

**验收标准:**
- [ ] 支持单只股票历史数据下载
- [ ] 支持批量下载（带进度条）
- [ ] 增量更新只拉取缺失数据
- [ ] 数据校验失败时记录并跳过

---

## Phase 3: 回测引擎核心

### 3.1 事件驱动核心
**文件变更:**
- Create `backtest/engine.py` - 回测引擎主类
- Create `backtest/events.py` - 事件定义（BarEvent, SignalEvent, OrderEvent, FillEvent）

**架构设计:**
```python
class BacktestEngine:
    def __init__(self, start_date, end_date, symbols, strategy, initial_cash=1_000_000)
    def run(self) -> BacktestResult
    def _process_bar(self, bar: BarEvent)
    def _process_signal(self, signal: SignalEvent)
    def _process_order(self, order: OrderEvent)
    def _process_fill(self, fill: FillEvent)
```

### 3.2 撮合与执行
**文件变更:**
- Create `backtest/execution.py` - 执行处理器

**撮合规则实现:**
- 下一bar开盘价成交
- 滑点模型：小单(1-2bps), 中单(5bps), 大单(10+bps)
- 涨跌停限制：涨停不买，跌停不卖
- T+1限制：当日买入次日才能卖出

### 3.3 虚拟账户与持仓
**文件变更:**
- Create `backtest/portfolio.py` - 投资组合管理

**核心功能:**
```python
class Portfolio:
    def update_market(self, timestamp, prices: Dict[str, float])
    def submit_order(self, order: OrderEvent) -> bool
    def process_fill(self, fill: FillEvent)
    def get_equity(self) -> float  # 总权益
    def get_positions(self) -> Dict[str, Position]
```

### 3.4 绩效指标计算
**文件变更:**
- Create `backtest/metrics.py` - 绩效分析

**指标列表:**
- 总收益率、年化收益率
- 夏普比率 (无风险利率可配置)
- 最大回撤及回撤持续时间
- 胜率、盈亏比
- Alpha, Beta (相对基准)
- 索提诺比率
- 卡尔玛比率

### 3.5 结果记录
**文件变更:**
- Create `backtest/recorder.py` - 回测结果持久化

**验收标准:**
- [ ] 分钟级回测10万条数据在30秒内完成
- [ ] 支持多标的组合回测
- [ ] 成交记录精确到分钟
- [ ] 权益曲线可导出CSV/JSON

---

## Phase 4: Agent Skill 框架

### 4.1 Skill 注册表
**文件变更:**
- Create `agent/skill_registry.py` - Skill发现与加载
- Create `skills/backtest/SKILL.md` - 回测Skill定义
- Create `skills/optimize/SKILL.md` - 优化Skill定义
- Create `skills/data_query/SKILL.md` - 数据查询Skill定义
- Create `skills/code_generate/SKILL.md` - 代码生成Skill定义

**Skill发现机制:**
```python
class SkillRegistry:
    def scan_skills(self, paths: List[str]) -> List[SkillMeta]
    def get_skill(self, name: str) -> Optional[Skill]
    def list_commands(self) -> Dict[str, str]  # command -> skill_name
```

### 4.2 渐进披露实现
**文件变更:**
- Create `agent/skill_loader.py` - Skill分级加载

**三级披露:**
- Level 1: YAML frontmatter (常驻内存)
- Level 2: 使用说明 (调用时加载)
- Level 3+: 高级文档 (按需加载)

### 4.3 上下文管理
**文件变更:**
- Create `agent/context_manager.py` - 对话上下文管理

**功能:**
- 多轮对话历史维护
- Token使用追踪与截断
- 用户偏好记忆

### 4.4 LLM客户端
**文件变更:**
- Create `agent/llm_client.py` - Claude API封装

**特性:**
- 支持流式响应
- 重试机制（指数退避）
- Token使用量追踪

### 4.5 Agent核心循环
**文件变更:**
- Create `agent/core.py` - Agent主循环

**验收标准:**
- [ ] Skill动态发现无需重启
- [ ] 支持用户自定义skill目录
- [ ] 上下文窗口自动管理
- [ ] LLM调用失败优雅降级

---

## Phase 5: CLI 与交互

### 5.1 CLI框架
**文件变更:**
- Create `quant_cli.py` - 主入口
- Create `cli/commands.py` - 命令定义

**命令结构:**
```bash
quant init              # 初始化项目
quant chat              # 进入对话模式
quant backtest <file>   # 直接回测
quant data update       # 更新数据
quant data status       # 查看数据状态
```

### 5.2 对话模式
**文件变更:**
- Create `cli/chat_mode.py` - 交互式对话

**交互特性:**
- 自然语言理解
- Slash command支持 (/backtest, /optimize等)
- 文件引用 (@strategy.py)
- 历史记录保存

### 5.3 输出格式化
**文件变更:**
- Create `cli/formatters.py` - 结果展示

**支持格式:**
- 表格（使用rich库）
- 图表（ASCII或matplotlib）
- JSON（用于脚本调用）

### 5.4 配置命令
**文件变更:**
- Create `cli/config_cmd.py` - 配置管理

**验收标准:**
- [ ] 所有命令有--help说明
- [ ] 错误信息友好且可操作
- [ ] 支持管道和重定向
- [ ] Tab补全支持

---

## Phase 6: 策略系统

### 6.1 策略基类
**文件变更:**
- Create `strategy/base.py` - 抽象基类
- Create `strategy/builtin/momentum.py` - 动量策略示例
- Create `strategy/builtin/rsi_bounce.py` - RSI反弹策略示例

**基类接口:**
```python
class BaseStrategy(ABC):
    params: Dict[str, Any] = {}

    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """返回: {'action': 'BUY'|'SELL'|'HOLD', 'weight': float}"""
        pass
```

### 6.2 策略加载器
**文件变更:**
- Create `strategy/loader.py` - 动态加载策略

**功能:**
- 从文件路径加载策略类
- 验证策略接口合规性
- 热重载支持（开发模式）

### 6.3 代码生成Skill
**文件变更:**
- Create `skills/code_generate/generator.py` - 策略生成器
- Create `skills/code_generate/templates/` - 代码模板

**生成流程:**
1. 用户描述策略逻辑
2. LLM生成代码草稿
3. 语法验证
4. 保存到 `strategy/generated/`

### 6.4 参数优化
**文件变更:**
- Create `strategy/optimizer.py` - 贝叶斯优化
- Create `skills/optimize/optimizer_skill.py` - 优化Skill

**优化目标:**
- 夏普比率最大化
- 支持参数边界约束
- 防止过拟合（交叉验证）

### 6.5 策略数据库
**文件变更:**
- Update `data/database.py` - 添加策略表操作

**验收标准:**
- [ ] 策略代码自动生成可运行
- [ ] 参数优化收敛稳定
- [ ] 策略版本可追溯
- [ ] 支持策略回滚

---

## Phase 7: 模拟盘系统

### 7.1 虚拟账户管理
**文件变更:**
- Create `paper/account.py` - 账户管理
- Create `paper/manager.py` - 多账户管理

**功能:**
```python
class PaperAccount:
    def __init__(self, name: str, initial_cash: float)
    def buy(self, symbol: str, quantity: int, price: float) -> bool
    def sell(self, symbol: str, quantity: int, price: float) -> bool
    def get_portfolio_value(self, current_prices: Dict) -> float
```

### 7.2 模拟盘交易记录
**文件变更:**
- Update `data/database.py` - 添加模拟盘表

### 7.3 模拟盘监控
**文件变更:**
- Create `paper/monitor.py` - 实时监控
- Create `cli/paper_commands.py` - 模拟盘CLI

**CLI命令:**
```bash
quant paper create --name test --cash 1000000
quant paper list
quant paper status --name test
quant paper trades --name test
```

### 7.4 定时任务框架
**文件变更:**
- Create `paper/scheduler.py` - 收盘后数据更新

**验收标准:**
- [ ] 支持多虚拟账户
- [ ] 交易记录完整可查
- [ ] 每日自动更新持仓市值
- [ ] 盈亏计算准确

---

## Phase 8: 集成测试与优化

### 8.1 端到端测试
**文件变更:**
- Create `tests/e2e/test_full_workflow.py` - 完整流程测试

**测试场景:**
1. 下载数据 -> 运行回测 -> 查看结果
2. 生成策略 -> 优化参数 -> 对比回测
3. 创建模拟盘 -> 模拟交易 -> 查看盈亏

### 8.2 性能测试
**文件变更:**
- Create `tests/perf/test_backtest_perf.py` - 回测性能

**基准:**
- 单标的1年分钟数据回测 < 10秒
- 100标的组合回测 < 60秒

### 8.3 数据一致性测试
**文件变更:**
- Create `tests/data/test_consistency.py` - 数据质量

### 8.4 文档完善
**文件变更:**
- Update `README.md` - 使用指南
- Create `docs/quickstart.md` - 快速开始
- Create `docs/api.md` - API文档
- Create `docs/strategy_development.md` - 策略开发指南

### 8.5 部署准备
**文件变更:**
- Create `Dockerfile` - 容器化
- Create `docker-compose.yml` - 本地开发环境
- Create `.github/workflows/ci.yml` - CI/CD

**验收标准:**
- [ ] 测试覆盖率 > 80%
- [ ] 核心流程全部通过
- [ ] 文档完整可跟随
- [ ] Docker镜像可运行

---

## 依赖清单

### Python包
```
# 核心
python = "^3.11"
pydantic = "^2.0"
pydantic-settings = "^2.0"
click = "^8.0"  # 或 typer

# 数据
pandas = "^2.0"
numpy = "^1.24"
akshare = "^1.10"
sqlite3  # 内置

# LLM
anthropic = "^0.18"

# 工具
loguru = "^0.7"
rich = "^13.0"  # 终端美化
pyyaml = "^6.0"
python-dotenv = "^1.0"

# 优化
scikit-optimize = "^0.9"

# 测试
pytest = "^8.0"
pytest-cov = "^4.0"
```

### 外部服务
- **Claude API** - 代码生成和自然语言处理
- **akshare** - A股行情数据（免费）

---

## 风险缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| akshare数据不稳定 | 高 | 实现重试机制，支持备用数据源接口 |
| LLM API延迟/故障 | 中 | 本地缓存常用响应，优雅降级到模板 |
| 回测性能不足 | 中 | 预留向量化回测路径，必要时切换 |
| 数据量过大 | 中 | 实现数据分区，支持按年份分库 |
| 过拟合 | 高 | 优化时使用交叉验证，强调样本外测试 |

---

## 后续迭代方向

### Mode B（短期）
- Web可视化界面（Gradio/Streamlit）
- 更多技术指标和因子
- 策略组合与权重优化

### Mode C（长期）
- 全自动策略研究员（AutoML + LLM）
- 实时行情接入
- Ptrade实盘对接
- 机器学习预测模块

---

*计划创建日期: 2026-02-21*
*版本: v1.0*
