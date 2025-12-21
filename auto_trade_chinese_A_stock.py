"""
UQTool A股策略 - 仓位同步版（带API测试功能）
"""
import requests
import json
import time
import schedule
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('position_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PositionSyncTrader:
    """仓位同步交易策略"""
    
    def __init__(self, api_key: str, symbols: List[str], account_value: float = 1000000.0):
        """
        初始化交易策略
        
        Args:
            api_key: UQTool API密钥
            symbols: 股票代码列表，如 ['000001.SZ', '000002.SZ']
            account_value: 账户总资产（元）
        """
        self.api_key = api_key
        self.symbols = symbols
        self.account_value = account_value
        self.base_url = "https://www.uqtool.com/wp-json/swtool/v1"
        
        # 记录当前持仓 {symbol: {'target_position': 0~1, 'current_shares': int}}
        self.positions: Dict[str, Dict] = {}
        
        logger.info("=" * 60)
        logger.info("UQTool A股仓位同步策略启动")
        logger.info(f"账户总资产: {account_value:.2f}元")
        logger.info(f"监控股票: {', '.join(symbols)}")
        logger.info("=" * 60)
        
        # 第一步：测试所有API接口
        if not self.test_all_apis():
            logger.error("API测试失败，程序退出")
            return
        
        # 第二步：初始化最近交易日
        self.latest_trading_date = self.get_latest_trading_date()
        logger.info(f"最近交易日: {self.latest_trading_date}")
        
        # 第三步：启动时同步仓位
        self.startup_sync()
    
    def test_all_apis(self) -> bool:
        """
        测试所有API接口
        
        Returns:
            bool: 所有接口测试通过返回True，否则返回False
        """
        logger.info("开始测试API接口...")
        
        test_results = []
        
        # 测试1：实时预测接口
        logger.info("1. 测试实时预测接口...")
        realtime_test_result = self.test_realtime_api()
        test_results.append(("实时预测接口", realtime_test_result))
        
        # 测试2：历史数据接口
        logger.info("2. 测试历史数据接口...")
        history_test_result = self.test_history_api()
        test_results.append(("历史数据接口", history_test_result))
        
        # 测试3：所有股票的基本数据获取
        logger.info("3. 测试所有股票数据获取...")
        symbols_test_result = self.test_symbols_api()
        test_results.append(("股票数据接口", symbols_test_result))
        
        # 输出测试结果
        logger.info("\n" + "=" * 60)
        logger.info("API接口测试结果:")
        logger.info("=" * 60)
        
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
        
        logger.info("=" * 60)
        
        return all_passed
    
    def test_realtime_api(self) -> Tuple[bool, str]:
        """测试实时预测接口"""
        try:
            # 使用第一个股票进行测试
            if not self.symbols:
                return False, "无监控股票"
            
            test_symbol = self.symbols[0]
            
            # 获取测试价格数据
            price_sequence = self.get_price_sequence(test_symbol)
            
            url = f"{self.base_url}/predict/"
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key
            }
            
            data = {
                'market': 'cnstock',
                'code': test_symbol,
                'price': price_sequence,
                'allow_short': 0
            }
            
            start_time = time.time()
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            elapsed_time = time.time() - start_time
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('success'):
                position = result['data'].get('position')
                remaining = result['data'].get('remaining', '未知')
                cached = result.get('cached', False)
                
                message = (f"返回仓位: {position}, 剩余次数: {remaining}, "
                          f"缓存: {cached}, 响应时间: {elapsed_time:.2f}秒")
                return True, message
            else:
                return False, f"API返回失败: {result.get('message', '未知错误')}"
                
        except requests.exceptions.Timeout:
            return False, "请求超时（10秒）"
        except requests.exceptions.ConnectionError:
            return False, "网络连接失败"
        except requests.exceptions.HTTPError as e:
            return False, f"HTTP错误: {e.response.status_code if e.response else '无响应'}"
        except KeyError as e:
            return False, f"数据解析错误: 缺少字段 {e}"
        except Exception as e:
            return False, f"未知错误: {str(e)}"
    
    def test_history_api(self) -> Tuple[bool, str]:
        """测试历史数据接口"""
        try:
            # 使用第一个股票进行测试
            if not self.symbols:
                return False, "无监控股票"
            
            test_symbol = self.symbols[0]
            test_date = self.get_latest_trading_date()  # 获取最近交易日
            
            url = f"{self.base_url}/history/"
            params = {
                'api_key': self.api_key,
                'market': 'cnstock',
                'ts_code': test_symbol,
                'start_date': test_date,
                'end_date': test_date,
                'table_type': 'market',
                'max_items': 10000
            }
            
            headers = {'X-API-KEY': self.api_key}
            
            start_time = time.time()
            response = requests.get(url, params=params, headers=headers, timeout=10)
            elapsed_time = time.time() - start_time
            
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                if len(data) > 0:
                    first_record = data[0]
                    trade_date = first_record.get('trade_date', '未知')
                    position = first_record.get('position', '未知')
                    close_price = first_record.get('close', '未知')
                    
                    message = (f"获取到 {len(data)} 条数据，日期: {trade_date}, "
                              f"仓位: {position}, 收盘价: {close_price}, "
                              f"响应时间: {elapsed_time:.2f}秒")
                    return True, message
                else:
                    return True, f"获取到0条数据（可能当天无交易），响应时间: {elapsed_time:.2f}秒"
            else:
                return False, f"返回数据格式错误: {type(data)}"
                
        except requests.exceptions.Timeout:
            return False, "请求超时（10秒）"
        except requests.exceptions.ConnectionError:
            return False, "网络连接失败"
        except requests.exceptions.HTTPError as e:
            return False, f"HTTP错误: {e.response.status_code if e.response else '无响应'}"
        except Exception as e:
            return False, f"未知错误: {str(e)}"
    
    def test_symbols_api(self) -> Tuple[bool, str]:
        """测试所有股票数据获取"""
        if not self.symbols:
            return False, "无监控股票"
        
        success_count = 0
        failed_symbols = []
        total_time = 0
        
        for symbol in self.symbols[:3]:  # 测试前3个股票
            try:
                # 测试历史数据获取
                test_date = self.get_latest_trading_date()
                url = f"{self.base_url}/history/"
                params = {
                    'api_key': self.api_key,
                    'market': 'cnstock',
                    'ts_code': symbol,
                    'start_date': test_date,
                    'end_date': test_date,
                    'table_type': 'market',
                    'max_items': 1
                }
                headers = {'X-API-KEY': self.api_key}
                
                start_time = time.time()
                response = requests.get(url, params=params, headers=headers, timeout=5)
                elapsed_time = time.time() - start_time
                total_time += elapsed_time
                
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, list):
                    success_count += 1
                else:
                    failed_symbols.append(f"{symbol}(格式错误)")
                    
            except Exception as e:
                failed_symbols.append(f"{symbol}({str(e)[:30]})")
            
            time.sleep(0.5)  # 避免请求过快
        
        if success_count == len(self.symbols[:3]):
            message = f"所有{len(self.symbols[:3])}个股票测试通过，平均响应时间: {total_time/len(self.symbols[:3]):.2f}秒"
            return True, message
        else:
            message = f"{success_count}个成功，{len(failed_symbols)}个失败: {', '.join(failed_symbols)}"
            return False, message
    
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
    
    def get_price_sequence(self, symbol: str) -> str:
        """
        获取价格序列字符串
        格式: "open|high|low|close|volume|amount"
        
        简化版：使用示例数据，实际应该从行情API获取
        """
        # 示例价格数据（实际应该动态获取）
        price_examples = {
            '000001.SZ': "11.62|11.63|11.65|11.58|649886|755106",
            '000002.SZ': "8.32|8.35|8.30|8.33|500000|416500",
            '000858.SZ': "150.80|151.50|150.50|151.00|200000|30100000",
            '600519.SH': "1705.00|1710.00|1700.00|1708.00|50000|85400000",
        }
        
        return price_examples.get(symbol, "0|0|0|0|0|0")
    
    def get_realtime_position(self, symbol: str) -> Optional[float]:
        """
        获取实时预测仓位（0~1）
        
        Returns:
            仓位比例（0~1），失败返回None
        """
        try:
            # 获取价格序列
            price_sequence = self.get_price_sequence(symbol)
            
            url = f"{self.base_url}/predict/"
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': self.api_key
            }
            
            data = {
                'market': 'cnstock',
                'code': symbol,
                'price': price_sequence,
                'allow_short': 0
            }
            
            logger.debug(f"请求实时预测: {symbol}, 价格: {price_sequence}")
            
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                position = float(result['data']['position'])
                
                # 注意：API返回的是0~1的仓位比例，不是百分比
                # 例如：0.8 表示80%仓位，不是80%
                
                logger.info(f"实时预测 {symbol}: 仓位={position:.3f} (即{position*100:.1f}%)")
                return position
            else:
                logger.error(f"实时预测失败 {symbol}: {result.get('message', '未知错误')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"实时预测网络错误 {symbol}: {e}")
            return None
        except KeyError as e:
            logger.error(f"实时预测数据解析错误 {symbol}: 缺少字段 {e}")
            return None
        except Exception as e:
            logger.error(f"实时预测未知错误 {symbol}: {e}")
            return None
    
    def get_history_position(self, symbol: str) -> Optional[float]:
        """
        获取历史仓位（0~1）
        
        Returns:
            仓位比例（0~1），失败返回None
        """
        try:
            url = f"{self.base_url}/history/"
            
            params = {
                'api_key': self.api_key,
                'market': 'cnstock',
                'ts_code': symbol,
                'start_date': self.latest_trading_date,
                'end_date': self.latest_trading_date,
                'table_type': 'market',
                'max_items': 10000
            }
            
            headers = {'X-API-KEY': self.api_key}
            
            logger.debug(f"查询历史仓位: {symbol}, 日期: {self.latest_trading_date}")
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                # 获取最新一条数据
                latest = data[0] if len(data) == 1 else sorted(data, 
                    key=lambda x: x.get('trade_date', ''), reverse=True)[0]
                
                # 注意：历史数据中的position字段可能是字符串
                position_str = latest.get('position')
                if position_str is not None:
                    position = float(position_str)
                    trade_date = latest.get('trade_date', '未知')
                    
                    logger.info(f"历史仓位 {symbol}: 日期={trade_date}, 仓位={position:.3f}")
                    return position
                else:
                    logger.warning(f"历史数据中未找到position字段 {symbol}")
                    return None
            else:
                logger.warning(f"无历史数据 {symbol}, 日期: {self.latest_trading_date}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"历史数据网络错误 {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"历史数据处理错误 {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取当前价格（简化版）
        实际应该从行情API获取
        """
        try:
            # 尝试从历史数据获取最新收盘价；注意历史价格在实盘的时候，会延迟一天
            history_data = self.get_history_position_data(symbol)
            if history_data and 'close' in history_data:
                return float(history_data['close'])
            
            # 备选方案：使用示例价格
            default_prices = {
                '000001.SZ': 11.62,
                '000002.SZ': 8.32,
                '000858.SZ': 150.80,
                '600519.SH': 1705.00,
            }
            
            return default_prices.get(symbol, 10.0)
            
        except Exception as e:
            logger.error(f"获取价格失败 {symbol}: {e}")
            return None
    
    def get_history_position_data(self, symbol: str) -> Optional[Dict]:
        """获取历史仓位数据（包含价格信息）"""
        try:
            url = f"{self.base_url}/history/"
            
            params = {
                'api_key': self.api_key,
                'market': 'cnstock',
                'ts_code': symbol,
                'start_date': self.latest_trading_date,
                'end_date': self.latest_trading_date,
                'table_type': 'market',
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
    
    def calculate_target_shares(self, symbol: str, target_position: float) -> int:
        """
        计算目标持股数量
        
        Args:
            symbol: 股票代码
            target_position: 目标仓位比例（0~1）
            
        Returns:
            目标持股数量（整数，以100股为单位）
        """
        current_price = self.get_current_price(symbol)
        if current_price is None or current_price <= 0:
            logger.error(f"无法获取有效价格 {symbol}")
            return 0
        
        # 计算目标市值
        target_value = self.account_value * target_position
        
        # 计算目标股数（A股以100股为单位）
        target_shares = int(target_value / current_price / 100) * 100
        
        logger.debug(f"计算目标股数 {symbol}: "
                    f"价格={current_price:.2f}, "
                    f"目标仓位={target_position:.3f}, "
                    f"目标市值={target_value:.2f}, "
                    f"目标股数={target_shares}")
        
        return target_shares
    
    def get_position_action(self, old_position: float, new_position: float) -> str:
        """
        判断仓位调整动作
        
        Returns:
            动作描述: '建仓', '清仓', '增仓', '减仓', '保持不变'
        """
        if old_position == 0 and new_position > 0:
            return "建仓"
        elif old_position > 0 and new_position == 0:
            return "清仓"
        elif new_position > old_position:
            return "增仓"
        elif new_position < old_position:
            return "减仓"
        else:
            return "保持不变"
    
    def execute_position_adjustment(self, symbol: str, target_position: float, reason: str):
        """
        执行仓位调整
        
        Args:
            symbol: 股票代码
            target_position: 目标仓位比例（0~1）
            reason: 调整原因
        """
        # 获取当前持仓
        current_pos = self.positions.get(symbol, {
            'target_position': 0.0,
            'current_shares': 0
        })
        
        old_position = current_pos['target_position']
        old_shares = current_pos['current_shares']
        
        # 判断调整动作
        action = self.get_position_action(old_position, target_position)
        
        if action == "保持不变":
            logger.info(f"{symbol}: 仓位保持不变 ({target_position:.3f})")
            return
        
        # 计算目标股数
        target_shares = self.calculate_target_shares(symbol, target_position)
        
        # 计算需要交易的数量
        shares_to_trade = target_shares - old_shares
        
        if shares_to_trade == 0:
            logger.info(f"{symbol}: 仓位比例变化但股数不变 ({old_position:.3f}->{target_position:.3f})")
        else:
            # 获取当前价格
            current_price = self.get_current_price(symbol) or 0
            
            if shares_to_trade > 0:
                trade_type = "买入"
                amount = shares_to_trade * current_price
                logger.info(f"{symbol}: {action} {trade_type}{shares_to_trade}股 "
                          f"@ {current_price:.2f}, 金额={amount:.2f}")
            else:
                trade_type = "卖出"
                amount = abs(shares_to_trade) * current_price
                logger.info(f"{symbol}: {action} {trade_type}{abs(shares_to_trade)}股 "
                          f"@ {current_price:.2f}, 金额={amount:.2f}")
        
        # 更新持仓记录
        self.positions[symbol] = {
            'target_position': target_position,
            'current_shares': target_shares,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reason': reason
        }
        
        logger.info(f"{symbol}: {action}完成 "
                   f"({old_position:.3f}->{target_position:.3f}), "
                   f"股数: {old_shares}->{target_shares}")
    
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
        """同步所有股票的仓位"""
        logger.info(f"开始同步所有股票 ({data_source})...")
        
        for symbol in self.symbols:
            try:
                if data_source == "realtime":
                    target_position = self.get_realtime_position(symbol)
                    reason = f"{reason_prefix} - 实时预测"
                else:
                    target_position = self.get_history_position(symbol)
                    reason = f"{reason_prefix} - 历史数据"
                
                if target_position is not None:
                    # 确保仓位在0~1范围内
                    target_position = max(0.0, min(1.0, target_position))
                    
                    self.execute_position_adjustment(symbol, target_position, reason)
                else:
                    logger.warning(f"无法获取 {symbol} 的仓位数据")
                
                time.sleep(1)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"同步 {symbol} 仓位时出错: {e}")
        
        logger.info("同步完成")
        self.print_position_summary()
    
    def print_position_summary(self):
        """打印仓位汇总"""
        logger.info("\n" + "-" * 60)
        logger.info("当前仓位汇总:")
        logger.info("-" * 60)
        
        total_position_value = 0
        
        for symbol, pos_info in self.positions.items():
            target_position = pos_info['target_position']
            current_shares = pos_info['current_shares']
            last_update = pos_info.get('last_update', '未知')
            
            # 计算当前市值
            current_price = self.get_current_price(symbol) or 0
            position_value = current_shares * current_price
            total_position_value += position_value
            
            # 计算实际仓位比例
            actual_position = position_value / self.account_value if self.account_value > 0 else 0
            
            logger.info(f"{symbol}:")
            logger.info(f"  目标仓位: {target_position:.3f} ({target_position*100:.1f}%)")
            logger.info(f"  实际仓位: {actual_position:.3f} ({actual_position*100:.1f}%)")
            logger.info(f"  持有股数: {current_shares}")
            logger.info(f"  当前价格: {current_price:.2f}")
            logger.info(f"  持仓市值: {position_value:.2f}")
            logger.info(f"  最后更新: {last_update}")
            logger.info("")
        
        logger.info(f"总持仓市值: {total_position_value:.2f}")
        logger.info(f"账户总资产: {self.account_value:.2f}")
        logger.info(f"总仓位比例: {total_position_value/self.account_value:.3f} "
                   f"({total_position_value/self.account_value*100:.1f}%)")
        logger.info("-" * 60)
    
    def check_and_sync_morning(self):
        """早盘检查并同步"""
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"\n{'='*60}")
        logger.info(f"早盘检查 {current_time}")
        logger.info('='*60)
        
        for symbol in self.symbols:
            try:
                # 早盘使用历史数据
                target_position = self.get_history_position(symbol)
                
                if target_position is not None:
                    # 确保仓位在0~1范围内
                    target_position = max(0.0, min(1.0, target_position))
                    
                    # 获取当前持仓
                    current_pos = self.positions.get(symbol, {'target_position': 0.0})
                    old_position = current_pos['target_position']
                    
                    # 判断是否需要调整
                    if abs(target_position - old_position) > 0.001:  # 容忍0.1%的差异
                        self.execute_position_adjustment(symbol, target_position, "早盘同步")
                    else:
                        logger.info(f"{symbol}: 仓位一致，无需调整 ({target_position:.3f})")
                else:
                    logger.warning(f"无法获取 {symbol} 的历史仓位")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"处理 {symbol} 早盘检查时出错: {e}")
    
    def check_and_sync_late(self):
        """尾盘检查并同步"""
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"\n{'='*60}")
        logger.info(f"尾盘检查 {current_time}")
        logger.info('='*60)
        
        for symbol in self.symbols:
            try:
                # 尾盘使用实时预测
                target_position = self.get_realtime_position(symbol)
                
                if target_position is not None:
                    # 确保仓位在0~1范围内
                    target_position = max(0.0, min(1.0, target_position))
                    
                    # 获取当前持仓
                    current_pos = self.positions.get(symbol, {'target_position': 0.0})
                    old_position = current_pos['target_position']
                    
                    # 判断是否需要调整
                    if abs(target_position - old_position) > 0.001:  # 容忍0.1%的差异
                        self.execute_position_adjustment(symbol, target_position, "尾盘同步")
                    else:
                        logger.info(f"{symbol}: 仓位一致，无需调整 ({target_position:.3f})")
                else:
                    logger.warning(f"无法获取 {symbol} 的实时预测")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"处理 {symbol} 尾盘检查时出错: {e}")
    
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
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("\n收到中断信号，停止运行")
                break
            except Exception as e:
                logger.error(f"主循环错误: {e}")
                time.sleep(60)


# 使用示例
if __name__ == "__main__":
    # 配置参数
    API_KEY = "YOUR_API_KEY"  # 替换为你的API密钥
    
    # 监控的股票列表
    SYMBOLS = [
        '000001.SZ',  # 平安银行
        '000002.SZ',  # 万科A
        '000858.SZ',  # 五粮液
        '600519.SH',  # 贵州茅台
    ]
    
    # 账户总资产（元）
    ACCOUNT_VALUE = 1000000.0
    
    try:
        # 创建并运行交易策略
        trader = PositionSyncTrader(
            api_key=API_KEY,
            symbols=SYMBOLS,
            account_value=ACCOUNT_VALUE
        )
        
        # 如果API测试通过，才运行主循环
        if hasattr(trader, 'positions'):
            trader.run()
        else:
            logger.error("策略初始化失败，程序退出")
            
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
