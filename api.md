1. API 概述
API 地址: https://www.uqtool.com/wp-json/swtool/v1/query/
请求方式: GET
认证方式: 通过 api_key 进行认证
数据格式: JSON
支持18种以上语言API：提供语言包括但不限于MT4、MT5、麦语言、Python、C、C++、PHP、Java、shell等等。
支持多维度特色数据：人气指数、AI实时预测、策略数据等
2. API 密钥生成
点击这里生成：https://www.uqtool.com/test_tool

生成后，用户可以在个人页面查看和管理API密钥。
3. 可调用的市场配置
以下是支持的市场及其配置：

python

markets = [
    {'prefix': 'gold', 'allow_short': True, 'leverage': 1},  # 黄金市场
    {'prefix': 'forex', 'allow_short': True, 'leverage': 10},  # 外汇市场
    {'prefix': 'cnindex', 'allow_short': False},  # 指数市场
    {'prefix': 'cnstock', 'allow_short': False},  # A 股市场
    {'prefix': 'cbond', 'allow_short': False},  # 可转债市场
    {'prefix': 'futures', 'allow_short': True, 'leverage': 5},  # 期货市场
    {'prefix': 'fund', 'allow_short': False},  # 基金市场
    {'prefix': 'cnoption', 'allow_short': True, 'leverage': 10},  # 期权市场
]

4. API 参数说明
参数名	必填	说明
api_key	是	用户的API密钥，用于认证和权限控制。
market	是	市场名称（如 gold, forex, cnindex 等）。
ts_code	是	合约代码（如 XAUUSD.fxcm, EURUSD.fxcm, 000001.SH 等）。
start_date	否	查询的开始日期（格式：YYYY-MM-DD），仅对 market 表查询有效。
end_date	否	查询的结束日期（格式：YYYY-MM-DD），仅对 market 表查询有效。
table_type	是	查询的表类型，可选值为 market 或 basic。

6. HTTP 请求示例
查询人气指数数据
GET 'https://www.uqtool.com/wp-json/swtool/v1/visitors-data/?days=7&time_unit=day&api_key=YOUR_API_KEY'
AI实时预测数据
POST 'https://www.uqtool.com/wp-json/swtool/v1/predict/' \
-H 'Content-Type: application/json' \
-H 'X-API-KEY: YOUR_API_KEY' \
-d '{"market":"cnstock","code":"000001.SZ","price":"10.50","allow_short":0}'

查询market表数据
GET https://www.uqtool.com/wp-json/swtool/v1/query/?api_key=YOUR_API_KEY&market=gold&ts_code=XAUUSD.fxcm&start_date=2023-01-01&end_date=2023-12-31&table_type=market

查询basic表数据
GET https://www.uqtool.com/wp-json/swtool/v1/query/?api_key=YOUR_API_KEY&market=gold&ts_code=XAUUSD.fxcm&table_type=basic

测试工具
https://www.uqtool.com/test_tool
