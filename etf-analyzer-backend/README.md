# ETF双框架智能分析系统

基于**缠论技术分析**与**丁昶投资框架**的A股ETF智能分析工具，提供完整的量化分析能力。

---

## 项目概述

本系统整合了两种互补的投资分析框架，为ETF投资者提供全面的决策支持：

### 缠论技术分析框架
基于缠中说禅的技术分析理论，实现：
- **分型识别**: 顶分型与底分型的自动检测
- **笔划分**: 按缠论规则连接分型形成笔
- **线段划分**: 基于笔构建高级走势结构
- **中枢识别**: 连续笔重叠区域的中枢检测
- **背驰检测**: MACD面积法背驰信号识别
- **买卖点识别**: 一买/二买/三买及对应卖点
- **多周期共振**: 日线/30分钟/5分钟三周期共振分析

### 丁昶五维评分框架
基于丁昶投资体系的五维度评估：
- **股息质量 (30%)**: 分红回报或资本效率评估
- **估值安全 (25%)**: PE/PB历史百分位与估值安全边际
- **盈利质地 (20%)**: ROE、收益稳定性与增长趋势
- **资金驱动 (15%)**: AUM趋势、成交量与资金流向
- **宏观适配 (10%)**: 周期定位、利率环境与政策支持

---

## 项目架构

```
etf-analyzer-backend/
├── app/                          # 主应用目录
│   ├── __init__.py
│   ├── main.py                   # FastAPI 入口
│   ├── config.py                 # 应用配置
│   ├── data/
│   │   ├── __init__.py
│   │   └── fetcher.py            # akshare 数据获取
│   ├── chanlun/                  # 缠论分析引擎
│   │   ├── __init__.py
│   │   ├── engine.py             # 核心引擎
│   │   ├── fractal.py            # 分型识别
│   │   ├── bi.py                 # 笔划分
│   │   ├── segment.py            # 线段划分
│   │   ├── center.py             # 中枢识别
│   │   ├── divergence.py         # 背驰检测
│   │   ├── buypoint.py           # 买卖点识别
│   │   └── resonance.py          # 多周期共振
│   ├── dingchang/                # 丁昶评分引擎
│   │   ├── __init__.py
│   │   ├── engine.py             # 五维评分引擎
│   │   ├── dividend.py           # 股息质量
│   │   ├── valuation.py          # 估值安全
│   │   ├── profitability.py      # 盈利质地
│   │   ├── capital_flow.py       # 资金驱动
│   │   └── macro.py              # 宏观适配
│   ├── models/                   # Pydantic 模型
│   │   ├── __init__.py
│   │   ├── chanlun.py
│   │   └── dingchang.py
│   └── api/
│       ├── __init__.py
│       └── router.py             # API 路由
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── README.md
└── .env.example
```

---

## 安装说明

### 环境要求
- Python 3.10+
- pip 21+
- Docker & Docker Compose (可选，用于容器化部署)

### 本地安装

```bash
# 1. 克隆项目
git clone <repository-url>
cd etf-analyzer-backend

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量（可选）
cp .env.example .env

# 5. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker 部署

```bash
# 1. 构建并启动
cd docker
docker-compose up --build -d

# 2. 查看日志
docker-compose logs -f

# 3. 停止服务
docker-compose down
```

---

## API 文档

启动服务后，可通过以下地址访问 API 文档：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/analyze` | 双框架综合分析 |
| GET | `/api/v1/etf/list` | 获取ETF列表 |
| GET | `/api/v1/etf/{code}/basic` | ETF基本信息 |
| GET | `/api/v1/etf/{code}/chanlun` | 缠论单独分析 |
| GET | `/api/v1/etf/{code}/dingchang` | 丁昶单独分析 |
| GET | `/api/v1/etf/{code}/multi-timeframe` | 多周期数据 |
| GET | `/health` | 健康检查 |

### 示例请求

#### 双框架分析
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"etf_code": "510300", "include_minute": true}'
```

#### ETF列表
```bash
curl http://localhost:8000/api/v1/etf/list?limit=20
```

#### ETF基本信息
```bash
curl http://localhost:8000/api/v1/etf/510300/basic
```

#### 缠论分析
```bash
curl http://localhost:8000/api/v1/etf/510300/chanlun
```

#### 丁昶分析
```bash
curl http://localhost:8000/api/v1/etf/510300/dingchang
```

---

## 配置说明

通过环境变量或 `.env` 文件进行配置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `ENV` | `development` | 运行环境 |
| `DEBUG` | `false` | 调试模式 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `PORT` | `8000` | 服务端口 |
| `CHANLUN_MIN_KLINES` | `5` | 笔最小K线间隔 |
| `CHANLUN_RESONANCE_THRESHOLD` | `70.0` | 共振信号阈值 |
| `DINGCHANG_COMPOSITE_THRESHOLD_BUY` | `80.0` | 买入阈值 |
| `DINGCHANG_COMPOSITE_THRESHOLD_HOLD` | `60.0` | 持有阈值 |

---

## 评分体系说明

### 缠论信号解读

| 信号 | 说明 | 操作建议 |
|------|------|----------|
| 一买 | 趋势背驰后转折 | 积极关注买入 |
| 二买 | 回调不创新低 | 回调买入 |
| 三买 | 突破中枢回调不入 | 追涨买入 |
| 一卖 | 趋势背驰后转折 | 考虑减仓 |
| 二卖 | 反弹不创新高 | 反弹减仓 |
| 三卖 | 跌破中枢反弹不入 | 止损离场 |

### 丁昶评级标准

| 评级 | 分数范围 | 含义 |
|------|----------|------|
| 买入 | >= 80分 | 多维度优秀，积极配置 |
| 持有 | 60-79分 | 整体尚可，继续持有 |
| 观察 | 40-59分 | 存在不确定，观望 |
| 回避 | < 40分 | 多项指标偏弱，回避 |

### 共振等级

| 等级 | 分数范围 | 含义 |
|------|----------|------|
| Strong | 90-100 | 三周期完全一致 |
| Medium-Strong | 70-89 | 两周期一致 |
| Medium | 50-69 | 结构清晰但有分歧 |
| Weak | < 50 | 单周期信号，不确定性高 |

---

## 数据源

本系统使用 [akshare](https://www.akshare.xyz/) 作为免费数据源，
获取A股ETF的实时行情和历史数据。akshare 数据来源于东方财富等公开渠道，
无需注册即可使用。

---

## 免责声明

本系统仅作为技术学习和研究参考，不构成任何投资建议。
投资者据此操作，风险自担。过往表现不代表未来收益。

---

## License

MIT License
