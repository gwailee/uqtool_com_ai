# UQTOOL.COM AI API 文档

## 概述
- **API地址**：`https://www.uqtool.com/wp-json/swtool/v1/{查询参数}/`
- **请求方式**：GET
- **认证方式**：`api_key` 参数认证
- **数据格式**：JSON
- **多语言支持**：MT4、MT5、麦语言、Python、C、C++、PHP、Java、Shell 等18+种语言
- **数据维度**：人气指数、AI实时预测、策略数据等

## API密钥管理
- **生成地址**：[https://www.uqtool.com/test_tool](https://www.uqtool.com/test_tool)
- **管理**：生成后可在个人页面查看和管理API密钥

## 市场配置
| 市场代码 | 允许做空 | 杠杆倍数 | 说明 |
|----------|----------|----------|------|
| `gold` | ✅ 是 | 1 | 黄金市场 |
| `forex` | ✅ 是 | 10 | 外汇市场 |
| `cnindex` | ❌ 否 | - | 指数市场 |
| `cnstock` | ❌ 否 | - | A股市场 |
| `cbond` | ❌ 否 | - | 可转债市场 |
| `futures` | ✅ 是 | 5 | 期货市场 |
| `fund` | ❌ 否 | - | 基金市场 |
| `cnoption` | ✅ 是 | 10 | 期权市场 |

## 请求参数
| 参数名 | 必填 | 说明 |
|--------|------|------|
| `api_key` | 是 | 用户API密钥，用于认证和权限控制 |
| `market` | 是 | 市场名称（如 `gold`, `forex`, `cnindex` 等） |
| `ts_code` | 是 | 合约代码（如 `XAUUSD.fxcm`, `EURUSD.fxcm`, `000001.SH` 等） |
| `start_date` | 否 | 开始日期（格式：`YYYY-MM-DD`），仅对 `market` 表有效 |
| `end_date` | 否 | 结束日期（格式：`YYYY-MM-DD`），仅对 `market` 表有效 |
| `table_type` | 是 | 查询表类型：`market` 或 `basic` |

## 接口示例
### 1. 查询人气指数数据
```http
GET https://www.uqtool.com/wp-json/swtool/v1/visitors-data/
    ?days=7
    &time_unit=day
    &api_key=YOUR_API_KEY
```

### 2. AI实时预测数据
```http
POST https://www.uqtool.com/wp-json/swtool/v1/predict/
Content-Type: application/json
X-API-KEY: YOUR_API_KEY

{
    "market": "cnstock",
    "code": "000001.SZ",
    "price": "10.50",
    "allow_short": 0
}
```

### 3. 查询market表数据（历史数据）
```http
GET https://www.uqtool.com/wp-json/swtool/v1/history/
    ?api_key=YOUR_API_KEY
    &market=gold
    &ts_code=XAUUSD.fxcm
    &start_date=2023-01-01
    &end_date=2023-12-31
    &table_type=market
```

### 4. 查询basic表数据（基础信息）
```http
GET https://www.uqtool.com/wp-json/swtool/v1/history/
    ?api_key=YOUR_API_KEY
    &market=gold
    &ts_code=XAUUSD.fxcm
    &table_type=basic
```

## 测试工具
- **在线测试**：[https://www.uqtool.com/test_tool](https://www.uqtool.com/test_tool)

---

> 注意：请妥善保管您的API密钥，避免泄露。所有请求需通过HTTPS协议发送。
