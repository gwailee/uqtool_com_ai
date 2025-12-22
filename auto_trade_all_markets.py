"""
UQTool 多市场策略 - 支持股票、期货、外汇、期权
仓位范围：-1~1（负数为空头，正数为多头）
"""
import requests
import json
import time
import schedule
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('multi_market_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MarketType(Enum):
    """市场类型枚举"""
    STOCK = "cnstock"       # A股股票（不能做空）
    FUTURES = "futures"     # 期货（可以做空）
    FOREX = "forex"         # 外汇（可以做空）
    OPTION = "cnoption"     # 期权（可以做空）
    GOLD = "gold"           # 贵金属（可以做空）
    INDEX = "cnindex"       # 指数（不能做空）
    BOND = "cbond"          # 可转债（不能做空）
    FUND = "fund"           # 基金（不能做空）


class SymbolInfo:
    """交易品种信息"""
    
    def __init__(self, symbol: str, market_type: MarketType, name: str = "", 
                 allow_short: bool = False, leverage: int = 1,
                 per_symbol_capital: float = None):
        """
        初始化交易品种
        
        Args:
            symbol: 品种代码，如 '000001.SZ', 'ICL1.CFX'
            market_type: 市场类型
            name: 品种名称
            allow_short: 是否允许做空
            leverage: 杠杆倍数（期货、外汇等）
            per_symbol_capital: 分配给该合约的资金（元）
        """
        self.symbol = symbol
        self.market_type = market_type
        self.name = name
        self.allow_short = allow_short
        self.leverage = leverage
        self.per_symbol_capital = per_symbol_capital
        
    def __str__(self):
        return f"{self.symbol} ({self.name}) - {self.market_type.value}"


class MultiMarketTrader:
    """多市场交易策略"""
    
    def __init__(self, api_key: str, symbols: List[SymbolInfo], 
                 per_symbol_capital: float = 100000.0,
                 host: str = "www.uqtool.com"):
        """
        初始化多市场交易策略
        
        Args:
            api_key: UQTool API密钥
            symbols: 交易品种列表
            per_symbol_capital: 每个合约分配的初始资金（元）
        """
        self.api_key = api_key
        self.host = host
        self.symbols = symbols
        self.per_symbol_capital = per_symbol_capital
        # 添加积分和API使用信息存储
        self.current_balance = 0
        self.current_remaining_calls = 0
        self.current_payment_type = 'free'
        self.api_usage_today = 0
        self.api_daily_limit = 0
        # 计算总资产：每个合约资金 × 合约数量
        self.total_account_value = sum([symbol.per_symbol_capital for symbol in symbols])
        
        # 为每个SymbolInfo设置资金（如果未设置）
        for symbol in self.symbols:
            if symbol.per_symbol_capital is None:
                symbol.per_symbol_capital = per_symbol_capital
        
        self.base_url =f"https://{self.host}/wp-json/swtool/v1"
        
        # 记录当前持仓 {symbol: {'target_position': -1~1, 'current_units': int, 
        # 'position_type': 'long'/'short', 'allocated_capital': float}}
        self.positions: Dict[str, Dict] = {}
        
        # 市场配置
        self.market_config = self.init_market_config()
        
        logger.info("=" * 70)
        logger.info("UQTool 多市场交易策略启动")
        logger.info(f"总资产: {self.total_account_value:.2f}元")      
        logger.info(f"交易品种 ({len(symbols)}个):")
        for symbol in symbols:
            leverage_info = f" 杠杆{symbol.leverage}X" if symbol.leverage > 1 else ""
            short_info = "可多空" if symbol.allow_short else "仅做多"
            capital_info = f" 资金:{symbol.per_symbol_capital:.0f}元"
            logger.info(f"  {symbol.symbol}: {symbol.name} - {symbol.market_type.value} "
                       f"({short_info}{leverage_info}{capital_info})")
        logger.info("=" * 70)
        
        # 第一步：测试所有API接口
        if not self.test_all_apis():
            logger.error("API测试失败，程序退出")
            return
        
        # 第二步：初始化最近交易日
        self.latest_trading_date = self.get_latest_trading_date()
        logger.info(f"最近交易日: {self.latest_trading_date}")
        
        # 第三步：启动时同步仓位
        self.startup_sync()
    
    def init_market_config(self) -> Dict[str, Dict]:
        """初始化市场配置"""
        return {
            MarketType.STOCK.value: {
                'allow_short': False,
                'leverage': 1,
                'min_lots': 100,  # 最小交易单位（股）
                'price_precision': 2,  # 价格精度
                'volume_precision': 0,  # 数量精度
            },
            MarketType.FUTURES.value: {
                'allow_short': True,
                'leverage': 10,  # 期货通常有杠杆
                'min_lots': 1,  # 最小交易单位（手）
                'price_precision': 2,
                'volume_precision': 0,
            },
            MarketType.FOREX.value: {
                'allow_short': True,
                'leverage': 10,  # 外汇杠杆
                'min_lots': 1000,  # 外汇最小单位
                'price_precision': 4,
                'volume_precision': 0,
            },
            MarketType.OPTION.value: {
                'allow_short': True,
                'leverage': 10,
                'min_lots': 1,  # 期权最小单位（张）
                'price_precision': 4,
                'volume_precision': 0,
            },
            MarketType.GOLD.value: {
                'allow_short': True,
                'leverage': 1,
                'min_lots': 1,
                'price_precision': 2,
                'volume_precision': 0,
            },
            MarketType.INDEX.value: {
                'allow_short': False,
                'leverage': 1,
                'min_lots': 1,
                'price_precision': 2,
                'volume_precision': 0,
            },
            MarketType.BOND.value: {
                'allow_short': False,
                'leverage': 1,
                'min_lots': 1,
                'price_precision': 2,
                'volume_precision': 0,
            },
            MarketType.FUND.value: {
                'allow_short': False,
                'leverage': 1,
                'min_lots': 1,
                'price_precision': 2,
                'volume_precision': 0,
            },
        }
    
    def test_all_apis(self) -> bool:
        """
        测试所有API接口
        
        Returns:
            bool: 所有接口测试通过返回True，否则返回False
        """
        logger.info("开始测试API接口...")
        
        test_results = []
        
        # 按市场类型分组测试
        markets_to_test = {}
        for symbol in self.symbols:
            market = symbol.market_type.value
            if market not in markets_to_test:
                markets_to_test[market] = symbol
        
        # 测试每个市场的API
        for market, test_symbol in markets_to_test.items():
            logger.info(f"测试 {market} 市场接口...")
            
            # 测试实时预测接口
            realtime_result = self.test_realtime_api(test_symbol)
            test_results.append((f"{market}实时接口", realtime_result))
            
            # 测试历史数据接口
            history_result = self.test_history_api(test_symbol)
            test_results.append((f"{market}历史接口", history_result))
            
           # time.sleep(0.1)  # 避免请求过快
        
        # 输出测试结果
        logger.info("\n" + "=" * 70)
        logger.info("API接口测试结果:")
        logger.info("=" * 70)
        
        all_passed = True
        for api_name, result in test_results:
            status = "✓ 通过" if result[0] else "✗ 失败"
            message = result[1]
            logger.info(f"{api_name}: {status}")
            if not result[0]:
                logger.error(f"  错误信息: {message}")
                all_passed = False
            else:
                logger.info(f"  详细信息: {message}")
        
        if all_passed:
            logger.info("所有API接口测试通过！")
        else:
            logger.error("部分API接口测试失败，请检查网络连接和API密钥")
        
        logger.info("=" * 70)
        
        return all_passed
    

    # 修改 test_history_api 函数中的积分信息获取
    def test_history_api(self, symbol_info: SymbolInfo) -> Tuple[bool, str]:
        """测试历史数据接口"""
        try:
            test_date = self.get_latest_trading_date()
            
            url = f"{self.base_url}/history/"
            params = {
                'api_key': self.api_key,
                'market': symbol_info.market_type.value,
                'ts_code': symbol_info.symbol,
                'start_date': test_date,
                'end_date': test_date,
                'table_type': 'basic',
                'max_items': 10000
            }
            
            headers = {'X-API-KEY': self.api_key}
            
            start_time = time.time()
            response = requests.get(url, params=params, headers=headers, timeout=10)
            elapsed_time = time.time() - start_time
            
            response.raise_for_status()
            result = response.json()
            
            # 新的响应格式：返回的是字典，包含 data 和 meta
            if isinstance(result, dict) and result.get('success'):
                data = result.get('data', [])
                meta = result.get('meta', {})
                api_info = meta.get('api_info', {})
                
                # 提取API使用信息
                remaining = api_info.get('remaining', 0)
                used_today = api_info.get('used_today', 0)
                daily_limit = api_info.get('daily_limit', 0)
                payment_type = api_info.get('payment_type', 'free')
                balance = api_info.get('balance', 0)  # 获取积分信息
                user_points = api_info.get('user_points', 0)  # 备用字段
                
                # 使用 balance 字段，如果为0则尝试 user_points
                actual_balance = balance if balance > 0 else user_points
                
                if isinstance(data, list):
                    if len(data) > 0:
                        first_record = data[0]
                        trade_date = first_record.get('trade_date', '未知')
                        position = first_record.get('position', '未知')
                        
                        # 判断仓位方向
                        if position != '未知':
                            position_float = float(position)
                            direction = "多头" if position_float > 0 else ("空头" if position_float < 0 else "空仓")
                            position_str = f"{position_float:.3f} ({direction})"
                        else:
                            position_str = "未知"
                        
                        message = (f"获取到 {len(data)} 条数据，日期: {trade_date}, "
                                f"仓位: {position_str}, "
                                f"API使用: {used_today}/{daily_limit} 剩余: {remaining}, "
                                f"支付方式: {payment_type}, "
                                f"剩余积分: {actual_balance}, "
                                f"响应时间: {elapsed_time:.2f}秒")
                        return True, message
                    else:
                        message = (f"获取到0条数据（可能当天无交易），"
                                f"API使用: {used_today}/{daily_limit} 剩余: {remaining}, "
                                f"支付方式: {payment_type}, "
                                f"剩余积分: {actual_balance}, "
                                f"响应时间: {elapsed_time:.2f}秒")
                        return True, message
                else:
                    return False, f"返回的data字段不是列表格式: {type(data)}"
            else:
                # 如果是旧格式（直接返回列表）
                if isinstance(result, list):
                    if len(result) > 0:
                        first_record = result[0]
                        trade_date = first_record.get('trade_date', '未知')
                        position = first_record.get('position', '未知')
                        
                        if position != '未知':
                            position_float = float(position)
                            direction = "多头" if position_float > 0 else ("空头" if position_float < 0 else "空仓")
                            position_str = f"{position_float:.3f} ({direction})"
                        else:
                            position_str = "未知"
                        
                        message = (f"获取到 {len(result)} 条数据（旧格式），日期: {trade_date}, "
                                f"仓位: {position_str}, 响应时间: {elapsed_time:.2f}秒")
                        return True, message
                    else:
                        return True, f"获取到0条数据（可能当天无交易），响应时间: {elapsed_time:.2f}秒"
                else:
                    return False, f"返回数据格式错误: {type(result)}, 内容: {str(result)[:100]}"
                    
        except requests.exceptions.Timeout:
            return False, "请求超时（10秒）"
        except Exception as e:
            return False, f"未知错误: {str(e)}"

    def get_latest_trading_date(self) -> str:
        """获取最近交易日（处理周末情况）"""
        today = datetime.now()
        
        # 如果是周末（周六=5, 周日=6），向前找到最近的周五
        if today.weekday() == 5:  # 周六
            trading_date = today - timedelta(days=1)
        elif today.weekday() == 6:  # 周日
            trading_date = today - timedelta(days=2)
        else:
            trading_date = today
        
        return trading_date.strftime('%Y-%m-%d')
    
    def get_price_sequence(self, symbol_info: SymbolInfo) -> str:
        """
        获取价格序列字符串
        格式: "open|high|low|close|volume|amount"
        
        简化版：使用示例数据，实际应该从行情API获取
        """
        # 示例价格数据（实际应该动态获取）
        price_examples = {
            # 股票
            '000001.SZ': "11.62|11.63|11.65|11.58|649886|755106",
            # 期货
            'ICL1.CFX': "7142.6|7096.2|7173.6|7083.2|37364|5331950",
            # 外汇
            'EURUSD.fxcm': "1.1050|1.1060|1.1040|1.1055|1000000|1105500",
            # 贵金属
            'Ag(T+D)': "15.463|15.425|15.641|15.21|900984|13933600000",
            # 指数
            '000001.SH': "3890.45|3878.23|3902.67|3871.78|513512000|738066000",
            # 可转债
            '123118.SZ': "1396.25|1288|1414|1269.75|220403|302360",
            # 基金
            '510300.SH': "34.50|34.60|34.40|34.55|100000|34550000",
            # 期权
            'MO2512-C-5800.CFX': "1535|1502.8|1544.6|1502.8|44|671.886",
        }
        
        return price_examples.get(symbol_info.symbol, "0|0|0|0|0|0")
    
    # 修改 test_realtime_api 函数
    def test_realtime_api(self, symbol_info: SymbolInfo) -> Tuple[bool, str]:
        """测试实时预测接口"""
        try:
            # 获取测试价格数据
            price_sequence = self.get_price_sequence(symbol_info)
            
            url = f"{self.base_url}/predict/"
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key
            }
            
            data = {
                'market': symbol_info.market_type.value,
                'code': symbol_info.symbol,
                'price': price_sequence,
                'allow_short': 1 if symbol_info.allow_short else 0
            }
            
            start_time = time.time()
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            elapsed_time = time.time() - start_time
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('success'):
                data = result.get('data', {})
                position = data.get('position')
                remaining = data.get('remaining', '未知')
                balance = data.get('balance', '未知')
                payment_type = data.get('payment_type', '未知')
                
                # 获取API信息
                api_info = data.get('api_info', {})
                used_today = api_info.get('used_today', 0)
                daily_limit = api_info.get('daily_limit', 0)
                
                # 判断仓位方向
                if position is not None:
                    position_float = float(position)
                    direction = "多头" if position_float > 0 else ("空头" if position_float < 0 else "空仓")
                    position_str = f"{position_float:.3f} ({direction})"
                else:
                    position_str = "未知"
                
                message = (f"返回仓位: {position_str}, "
                        f"剩余次数: {remaining}, "
                        f"剩余积分: {balance}, "
                        f"支付方式: {payment_type}, "
                        f"API使用: {used_today}/{daily_limit}, "
                        f"响应时间: {elapsed_time:.2f}秒")
                return True, message
            else:
                return False, f"API返回失败: {result.get('message', '未知错误')}"
                
        except requests.exceptions.Timeout:
            return False, "请求超时（10秒）"
        except requests.exceptions.ConnectionError:
            return False, "网络连接失败"
        except requests.exceptions.HTTPError as e:
            return False, f"HTTP错误: {e.response.status_code if e.response else '无响应'}"
        except Exception as e:
            return False, f"未知错误: {str(e)}"

    # 修改 get_realtime_position 函数中的积分信息获取
    def get_realtime_position(self, symbol_info: SymbolInfo) -> Optional[float]:
        """
        获取实时预测仓位（-1~1）
        
        Returns:
            仓位比例（-1~1），失败返回None
        """
        try:
            # 获取价格序列
            price_sequence = self.get_price_sequence(symbol_info)
            
            url = f"{self.base_url}/predict/"
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key
            }
            
            data = {
                'market': symbol_info.market_type.value,
                'code': symbol_info.symbol,
                'price': price_sequence,
                'allow_short': 1 if symbol_info.allow_short else 0
            }
            
            logger.debug(f"请求实时预测: {symbol_info.symbol}, 市场: {symbol_info.market_type.value}")
            
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                data = result.get('data', {})
                position = float(data.get('position', 0))
                
                # 提取积分和使用信息
                balance = data.get('balance', 0)
                remaining = data.get('remaining', 0)
                payment_type = data.get('payment_type', 'free')
                api_info = data.get('api_info', {})
                
                # 注意：API返回的是-1~1的仓位比例
                # 例如：0.8 表示多头80%仓位，-0.8 表示空头80%仓位
                
                direction = "多头" if position > 0 else ("空头" if position < 0 else "空仓")
                
                # 记录积分信息
                logger.info(f"实时预测 {symbol_info.symbol}: "
                            f"仓位={position:.3f} ({direction}{abs(position)*100:.1f}%), "
                            f"剩余积分={balance}, "
                            f"剩余次数={remaining}, "
                            f"支付方式={payment_type}")
                
                # 存储当前积分和剩余次数到实例变量
                self.current_balance = balance
                self.current_remaining_calls = remaining
                
                return position
            else:
                logger.error(f"实时预测失败 {symbol_info.symbol}: {result.get('message', '未知错误')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"实时预测网络错误 {symbol_info.symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"实时预测未知错误 {symbol_info.symbol}: {e}")
            return None

    def get_history_position(self, symbol_info: SymbolInfo) -> Optional[float]:
        """
        获取历史仓位（-1~1）
        
        Returns:
            仓位比例（-1~1），失败返回None
        """
        try:
            url = f"{self.base_url}/history/"
            
            params = {
                'api_key': self.api_key,
                'market': symbol_info.market_type.value,
                'ts_code': symbol_info.symbol,
                'start_date': self.latest_trading_date,
                'end_date': self.latest_trading_date,
                'table_type': 'basic',
                'max_items': 10000
            }
            
            headers = {'X-API-KEY': self.api_key}
            
            logger.debug(f"查询历史仓位: {symbol_info.symbol}, 市场: {symbol_info.market_type.value}")
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            # 新的响应格式：包含 meta 信息
            if result.get('success'):
                data = result.get('data', [])
                meta = result.get('meta', {})
                api_info = meta.get('api_info', {})
                
                # 提取剩余次数信息
                remaining = api_info.get('remaining', 0)
                used_today = api_info.get('used_today', 0)
                daily_limit = api_info.get('daily_limit', 0)
                payment_type = api_info.get('payment_type', 'free')
                
                logger.info(f"API使用信息: 今日已用 {used_today}/{daily_limit}, 剩余 {remaining}, 支付方式: {payment_type}")
                
                if isinstance(data, list) and len(data) > 0:
                    # 获取最新一条数据
                    latest = data[0] if len(data) == 1 else sorted(data, 
                        key=lambda x: x.get('trade_date', ''), reverse=True)[0]
                    
                    # 注意：历史数据中的position字段可能是字符串
                    position_str = latest.get('position')
                    if position_str is not None:
                        position = float(position_str)
                        trade_date = latest.get('trade_date', '未知')
                        
                        direction = "多头" if position > 0 else ("空头" if position < 0 else "空仓")
                        logger.info(f"历史仓位 {symbol_info.symbol}: 日期={trade_date}, 仓位={position:.3f} ({direction})")
                        return position
                    else:
                        logger.warning(f"历史数据中未找到position字段 {symbol_info.symbol}")
                        return None
                else:
                    logger.warning(f"无历史数据 {symbol_info.symbol}, 日期: {self.latest_trading_date}")
                    return None
            else:
                logger.error(f"API返回失败: {result.get('message', '未知错误')}")
                return None
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"历史数据网络错误 {symbol_info.symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"历史数据处理错误 {symbol_info.symbol}: {e}")
            return None

    def get_current_price(self, symbol_info: SymbolInfo) -> Optional[float]:
        """
        获取当前价格（简化版）
        实际应该从行情API获取
        """
        try:
            # 尝试从历史数据获取最新收盘价；注意历史价格在实盘的时候，会延迟一天
            history_data = self.get_history_position_data(symbol_info)
            if history_data and 'close' in history_data:
                return float(history_data['close'])
            #也可以从tushare.org获取部分的实时行情数据，参考下面的实现
            '''    
            cnstock: df = pro.rt_k(ts_code='600000.SH,000001.SZ')
            fund: df = pro.rt_etf_k(ts_code='5*.SH', topic='HQ_FND_TICK')
            cnindex: df = pro.rt_idx_k(ts_code='000001.SH,399107.SZ')
            futures:            
            pro = ts.pro_api()
            #单个期货合约实时分钟线
            df = pro.df = pro.rt_fut_min(ts_code='CU2501.SHF', freq='1MIN')
            '''
            # 备选方案：使用示例价格
            default_prices = {
                # 股票
                '000001.SZ': 11.62,            
                # 期货
                'ICL1.CFX': 7083.2,
                # 指数
                '000001.SH': 3455.0,
                # 外汇
                'EURUSD.fxcm': 1.1055,
                # 贵金属
                'AG(T+D)': 15.463,
                # 可转债
                '123118.SZ': 1288.0,
                # 基金
                '510300.SH': 34.55,
                # 期权
                'MO2512-C-5800.CFX': 1535.0,
            }
            
            return default_prices.get(symbol_info.symbol, 10.0)
            
        except Exception as e:
            logger.error(f"获取价格失败 {symbol_info.symbol}: {e}")
            return None
    
    def get_history_position_data(self, symbol_info: SymbolInfo) -> Optional[Dict]:
        """获取历史仓位数据（包含价格信息）"""
        try:
            url = f"{self.base_url}/history/"
            
            params = {
                'api_key': self.api_key,
                'market': symbol_info.market_type.value,
                'ts_code': symbol_info.symbol,
                'start_date': self.latest_trading_date,
                'end_date': self.latest_trading_date,
                'table_type': 'basic',
                'max_items': 10000
            }
            
            headers = {'X-API-KEY': self.api_key}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                return data[0]
                
        except:
            pass
        return None
    
    def calculate_target_units(self, symbol_info: SymbolInfo, target_position: float) -> int:
        """
        计算目标交易单位数量
        
        Args:
            symbol_info: 交易品种信息
            target_position: 目标仓位比例（-1~1）
            
        Returns:
            目标交易单位数量
        """
        current_price = self.get_current_price(symbol_info)
        if current_price is None or current_price <= 0:
            logger.error(f"无法获取有效价格 {symbol_info.symbol}")
            return 0
        
        # 获取市场配置
        market_cfg = self.market_config.get(symbol_info.market_type.value, {})
        min_lots = market_cfg.get('min_lots', 1)
        
        # 使用分配给该合约的资金（不是总资产）
        allocated_capital = symbol_info.per_symbol_capital
        
        # 考虑杠杆
        effective_capital = allocated_capital * symbol_info.leverage
        
        # 计算目标市值（注意：空头仓位用负值计算）
        target_value = effective_capital * target_position
        
        # 计算目标单位数量
        if target_position >= 0:  # 多头
            target_units = int(abs(target_value) / current_price / min_lots) * min_lots
        else:  # 空头
            target_units = -int(abs(target_value) / current_price / min_lots) * min_lots
        
        logger.debug(f"计算目标单位 {symbol_info.symbol}: "
                    f"分配资金={allocated_capital:.2f}, "
                    f"价格={current_price:.4f}, "
                    f"目标仓位={target_position:.3f}, "
                    f"目标市值={target_value:.2f}, "
                    f"目标单位={target_units}")
        
        return target_units
    
    def get_position_action(self, old_position: float, new_position: float, allow_short: bool) -> str:
        """
        判断仓位调整动作
        
        Returns:
            动作描述: '建多仓', '建空仓', '平多仓', '平空仓', '多转空', '空转多', '增仓', '减仓', '保持不变'
        """
        if old_position == 0:
            if new_position > 0:
                return "建多仓"
            elif new_position < 0:
                return "建空仓"
            else:
                return "保持不变"
        
        elif old_position > 0:  # 原有多头仓位
            if new_position == 0:
                return "平多仓"
            elif new_position < 0:  # 多转空
                return "多转空"
            elif new_position > old_position:
                return "增多仓"
            elif new_position < old_position:
                return "减多仓"
            else:
                return "保持不变"
        
        else:  # old_position < 0, 原有空头仓位
            if new_position == 0:
                return "平空仓"
            elif new_position > 0:  # 空转多
                return "空转多"
            elif abs(new_position) > abs(old_position):  # 增加空头仓位
                return "增空仓"
            elif abs(new_position) < abs(old_position):  # 减少空头仓位
                return "减空仓"
            else:
                return "保持不变"
    
    def execute_position_adjustment(self, symbol_info: SymbolInfo, target_position: float, reason: str):
        """
        执行仓位调整
        
        Args:
            symbol_info: 交易品种信息
            target_position: 目标仓位比例（-1~1）
            reason: 调整原因
        """
        # 获取当前持仓
        symbol_key = symbol_info.symbol
        current_pos = self.positions.get(symbol_key, {
            'target_position': 0.0,
            'current_units': 0,
            'position_type': 'flat',
            'allocated_capital': symbol_info.per_symbol_capital
        })
        
        old_position = current_pos['target_position']
        old_units = current_pos['current_units']
        allocated_capital = current_pos['allocated_capital']
        
        # 判断调整动作
        action = self.get_position_action(old_position, target_position, symbol_info.allow_short)
        
        if action == "保持不变":
            logger.info(f"{symbol_info.symbol}: 仓位保持不变 ({target_position:.3f})")
            return
        
        # 计算目标单位数量
        target_units = self.calculate_target_units(symbol_info, target_position)
        
        # 计算需要交易的数量
        units_to_trade = target_units - old_units
        
        if units_to_trade == 0:
            logger.info(f"{symbol_info.symbol}: 仓位比例变化但数量不变 ({old_position:.3f}->{target_position:.3f})")
        else:
            # 获取当前价格
            current_price = self.get_current_price(symbol_info) or 0
            
            # 确定交易方向
            if units_to_trade > 0:
                trade_direction = "买入开多" if target_position > 0 else "卖出开空"
            else:
                trade_direction = "卖出平多" if old_units > 0 else "买入平空"
            
            # 计算交易金额（考虑杠杆）
            trade_value = abs(units_to_trade) * current_price / symbol_info.leverage
            
            logger.info(f"{symbol_info.symbol}: {action} {trade_direction}{abs(units_to_trade)}单位 "
                      f"@ {current_price:.4f}, 占用资金={trade_value:.2f}元")
        
        # 更新持仓记录
        position_type = 'long' if target_position > 0 else ('short' if target_position < 0 else 'flat')
        
        self.positions[symbol_key] = {
            'target_position': target_position,
            'current_units': target_units,
            'position_type': position_type,
            'allocated_capital': allocated_capital,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reason': reason,
            'market_type': symbol_info.market_type.value,
            'symbol_name': symbol_info.name,
            'leverage': symbol_info.leverage
        }
        
        direction_old = "多头" if old_position > 0 else ("空头" if old_position < 0 else "空仓")
        direction_new = "多头" if target_position > 0 else ("空头" if target_position < 0 else "空仓")
        
        logger.info(f"{symbol_info.symbol}: {action}完成 "
                   f"({direction_old}{abs(old_position)*100:.1f}%->{direction_new}{abs(target_position)*100:.1f}%), "
                   f"单位: {old_units}->{target_units}, "
                   f"分配资金: {allocated_capital:.2f}元")
    
    def startup_sync(self):
        """启动时同步仓位"""
        logger.info("\n执行启动仓位同步...")
        
        now = datetime.now()
        current_hour = now.hour
        
        # 判断当前时段：尾盘（14:00-15:00）用实时预测，其他时间用历史数据
        if 14 <= current_hour < 15:
            logger.info("当前为尾盘时段，使用实时预测同步")
            data_source = "realtime"
            reason_prefix = "启动同步(实时)"
        else:
            logger.info("当前为非尾盘时段，使用历史数据同步")
            data_source = "history"
            reason_prefix = "启动同步(历史)"
        
        self.sync_all_positions(data_source, reason_prefix)
    
    def sync_all_positions(self, data_source: str, reason_prefix: str):
        """同步所有交易品种的仓位"""
        logger.info(f"开始同步所有品种 ({data_source})...")
        
        for symbol_info in self.symbols:
            try:
                if data_source == "realtime":
                    target_position = self.get_realtime_position(symbol_info)
                    reason = f"{reason_prefix} - 实时预测"
                else:
                    target_position = self.get_history_position(symbol_info)
                    reason = f"{reason_prefix} - 历史数据"
                
                if target_position is not None:
                    # 确保仓位在-1~1范围内
                    target_position = max(-1.0, min(1.0, target_position))
                    
                    # 如果不允许做空但仓位为负，调整为0
                    if not symbol_info.allow_short and target_position < 0:
                        logger.warning(f"{symbol_info.symbol} 不允许做空，空头仓位{target_position:.3f}调整为0")
                        target_position = 0.0
                    
                    self.execute_position_adjustment(symbol_info, target_position, reason)
                else:
                    logger.warning(f"无法获取 {symbol_info.symbol} 的仓位数据")
                
               # time.sleep(0.1)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"同步 {symbol_info.symbol} 仓位时出错: {e}")
        
        logger.info("同步完成")
        self.print_position_summary()
    
    def print_position_summary(self):
        """打印仓位汇总"""
        logger.info("\n" + "-" * 80)
        logger.info("当前仓位汇总:")
        logger.info("-" * 80)
        
        total_position_value = 0
        long_value = 0
        short_value = 0
        total_allocated_capital = 0
        
        for symbol_key, pos_info in self.positions.items():
            target_position = pos_info['target_position']
            current_units = pos_info['current_units']
            position_type = pos_info.get('position_type', 'flat')
            market_type = pos_info.get('market_type', 'unknown')
            symbol_name = pos_info.get('symbol_name', symbol_key)
            allocated_capital = pos_info.get('allocated_capital', 0)
            leverage = pos_info.get('leverage', 1)
            
            total_allocated_capital += allocated_capital
            
            # 找到对应的symbol_info
            symbol_info = next((s for s in self.symbols if s.symbol == symbol_key), None)
            
            if symbol_info:
                # 计算当前市值
                current_price = self.get_current_price(symbol_info) or 0
                
                if position_type == 'long':
                    position_value = abs(current_units) * current_price / leverage
                    long_value += position_value
                elif position_type == 'short':
                    position_value = -abs(current_units) * current_price / leverage
                    short_value += position_value
                else:
                    position_value = 0
                
                total_position_value += position_value
                
                # 计算实际仓位比例（相对于该合约分配的资金）
                position_ratio = position_value / allocated_capital if allocated_capital > 0 else 0
                
                direction = "多头" if target_position > 0 else ("空头" if target_position < 0 else "空仓")
                
                logger.info(f"{symbol_key} ({symbol_name} - {market_type}):")
                logger.info(f"  目标仓位: {target_position:.3f} ({direction}{abs(target_position)*100:.1f}%)")
                logger.info(f"  实际仓位: {position_ratio:.3f} ({position_ratio*100:.1f}%)")
                logger.info(f"  持仓方向: {position_type}")
                logger.info(f"  持仓单位: {current_units}")
                logger.info(f"  当前价格: {current_price:.4f}")
                logger.info(f"  持仓市值: {position_value:.2f}元")
                logger.info(f"  分配资金: {allocated_capital:.2f}元")
                if leverage > 1:
                    logger.info(f"  杠杆倍数: {leverage}X")
                logger.info("")
        
        logger.info(f"多头总市值: {long_value:.2f}元")
        logger.info(f"空头总市值: {short_value:.2f}元")
        logger.info(f"净持仓市值: {total_position_value:.2f}元")
        logger.info(f"分配总资金: {total_allocated_capital:.2f}元")
        logger.info(f"账户总资产: {self.total_account_value:.2f}元")
        
        # 计算相对于总资产的仓位比例
        if self.total_account_value > 0:
            total_position_ratio = total_position_value / self.total_account_value
            logger.info(f"总仓位比例: {total_position_ratio:.3f} ({total_position_ratio*100:.1f}%)")
        
        # 计算风险指标（相对于总资产）
        gross_exposure = (long_value + abs(short_value)) / self.total_account_value
        net_exposure = total_position_value / self.total_account_value
        logger.info(f"总风险敞口: {gross_exposure:.3f} ({gross_exposure*100:.1f}%)")
        logger.info(f"净风险敞口: {net_exposure:.3f} ({net_exposure*100:.1f}%)")
        
        # 计算资金利用率
        if total_allocated_capital > 0:
            capital_utilization = (long_value + abs(short_value)) / total_allocated_capital
            logger.info(f"资金利用率: {capital_utilization:.3f} ({capital_utilization*100:.1f}%)")
        
        logger.info("-" * 80)
    
    def check_and_sync_morning(self):
        """早盘检查并同步"""
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"\n{'='*70}")
        logger.info(f"早盘检查 {current_time}")
        logger.info('='*70)
        
        for symbol_info in self.symbols:
            try:
                # 早盘使用历史数据
                target_position = self.get_history_position(symbol_info)
                
                if target_position is not None:
                    # 确保仓位在-1~1范围内
                    target_position = max(-1.0, min(1.0, target_position))
                    
                    # 如果不允许做空但仓位为负，调整为0
                    if not symbol_info.allow_short and target_position < 0:
                        target_position = 0.0
                    
                    # 获取当前持仓
                    current_pos = self.positions.get(symbol_info.symbol, {'target_position': 0.0})
                    old_position = current_pos['target_position']
                    
                    # 判断是否需要调整
                    if abs(target_position - old_position) > 0.001:  # 容忍0.1%的差异
                        self.execute_position_adjustment(symbol_info, target_position, "早盘同步")
                    else:
                        direction = "多头" if target_position > 0 else ("空头" if target_position < 0 else "空仓")
                        logger.info(f"{symbol_info.symbol}: 仓位一致，无需调整 ({direction}{abs(target_position)*100:.1f}%)")
                else:
                    logger.warning(f"无法获取 {symbol_info.symbol} 的历史仓位")
                
               # time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"处理 {symbol_info.symbol} 早盘检查时出错: {e}")
    
    def check_and_sync_late(self):
        """尾盘检查并同步"""
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"\n{'='*70}")
        logger.info(f"尾盘检查 {current_time}")
        logger.info('='*70)
        
        for symbol_info in self.symbols:
            try:
                # 尾盘使用实时预测
                target_position = self.get_realtime_position(symbol_info)
                
                if target_position is not None:
                    # 确保仓位在-1~1范围内
                    target_position = max(-1.0, min(1.0, target_position))
                    
                    # 如果不允许做空但仓位为负，调整为0
                    if not symbol_info.allow_short and target_position < 0:
                        target_position = 0.0
                    
                    # 获取当前持仓
                    current_pos = self.positions.get(symbol_info.symbol, {'target_position': 0.0})
                    old_position = current_pos['target_position']
                    
                    # 判断是否需要调整
                    if abs(target_position - old_position) > 0.001:  # 容忍0.1%的差异
                        self.execute_position_adjustment(symbol_info, target_position, "尾盘同步")
                    else:
                        direction = "多头" if target_position > 0 else ("空头" if target_position < 0 else "空仓")
                        logger.info(f"{symbol_info.symbol}: 仓位一致，无需调整 ({direction}{abs(target_position)*100:.1f}%)")
                else:
                    logger.warning(f"无法获取 {symbol_info.symbol} 的实时预测")
                
               # time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"处理 {symbol_info.symbol} 尾盘检查时出错: {e}")
    
    def run(self):
        """运行策略主循环"""
        logger.info("\n进入主循环...")
        
        # 设置定时任务
        # 早盘：9:35和9:45
        schedule.every().day.at("09:35").do(self.check_and_sync_morning)
        schedule.every().day.at("09:45").do(self.check_and_sync_morning)
        
        # 尾盘：14:30和14:45
        schedule.every().day.at("14:30").do(self.check_and_sync_late)
        schedule.every().day.at("14:45").do(self.check_and_sync_late)
        
        # 收盘后打印汇总
        schedule.every().day.at("15:05").do(self.print_position_summary)
        
        logger.info("定时任务已设置:")
        logger.info("早盘: 09:35, 09:45")
        logger.info("尾盘: 14:30, 14:45")
        logger.info("汇总: 15:05")
        
        # 主循环
        while True:
            try:
                schedule.run_pending()
               # time.sleep(0.1)
                
            except KeyboardInterrupt:
                logger.info("\n收到中断信号，停止运行")
                break
            except Exception as e:
                logger.error(f"主循环错误: {e}")
                time.sleep(60)


# 使用示例
if __name__ == "__main__":
    # 配置参数
    API_KEY = "YOU-API-KEY"  # 替换为你的API密钥
    host="www.uqtool.com"
    # 定义交易品种（多市场示例）
    SYMBOLS = [
        # A股股票（不能做空）- 每个分配20万
        SymbolInfo('000001.SZ', MarketType.STOCK, '平安银行', allow_short=False, 
                  per_symbol_capital=200000.0),
        
        # 期货（可以做空）- 每个分配10万
        SymbolInfo('ICL1.CFX', MarketType.FUTURES, '中证500主力', allow_short=True, 
                  leverage=1, per_symbol_capital=100000.0),
        
        # 可转债（不可以做空）- 每个分配10万
        SymbolInfo('123118.SZ', MarketType.BOND, '123118', allow_short=False, 
                  per_symbol_capital=100000.0),
        
        # 基金（不可以做空）- 每个分配20万
        SymbolInfo('510300.SH', MarketType.FUND, '510300', allow_short=False, 
                  per_symbol_capital=200000.0),
        
        # 期权（可以做空）- 每个分配10万
        SymbolInfo('MO2512-C-5800.CFX', MarketType.OPTION, '202512C5800', 
                  allow_short=True, leverage=1, per_symbol_capital=100000.0),
        #指数（不可以做空）- 每个分配10万
        SymbolInfo('000001.SH', MarketType.INDEX, '上证指数', allow_short=False, 
                  per_symbol_capital=100000.0),
        
        #外汇（可以做空）- 每个分配10万
        #SymbolInfo('GBPJPY.FXCM', MarketType.FOREX, '英镑日元', allow_short=True, 
        #          per_symbol_capital=100000.0),

        #黄金（可以做空）- 每个分配10万
        #SymbolInfo('Ag(T+D)', MarketType.GOLD, '白银', allow_short=True, 
        #          per_symbol_capital=100000.0),
        
    ]
    
    # 计算默认每个合约资金（如果不指定）
    DEFAULT_PER_SYMBOL_CAPITAL = 100000.0  # 10万元/合约
    
    try:
        # 创建并运行交易策略
        trader = MultiMarketTrader(
            api_key=API_KEY,
            symbols=SYMBOLS,
            per_symbol_capital=DEFAULT_PER_SYMBOL_CAPITAL,
            host=host
        )
        
        # 如果API测试通过，才运行主循环
        if hasattr(trader, 'positions'):
            trader.run()
        else:
            logger.error("策略初始化失败，程序退出")
            
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
