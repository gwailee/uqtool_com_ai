import requests
import pandas as pd
import json
from typing import Optional, Dict, Any
import time
from datetime import datetime, timedelta

class UQToolAPI:
    """UQTool API 客户端"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.uqtool.com/wp-json/swtool/v1"
        self.session = requests.Session()
        
    def _make_request(self, endpoint: str, method='GET', **kwargs):
        """发送请求的通用方法"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # 添加调试信息
            print(f"请求URL: {url}")
            print(f"请求方法: {method}")
            
            if method.upper() == 'GET':
                response = self.session.get(url, **kwargs)
            elif method.upper() == 'POST':
                response = self.session.post(url, **kwargs)
            else:
                raise ValueError(f"不支持的请求方法: {method}")
            
            # 打印响应状态码
            print(f"响应状态码: {response.status_code}")
            
            response.raise_for_status()
            
            # 尝试解析JSON
            try:
                result = response.json()
                print(f"JSON响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return result
            except json.JSONDecodeError:
                print(f"响应内容（非JSON）: {response.text[:200]}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"错误响应: {e.response.text[:500]}")
            return None
    
    def get_popularity(self, days: int = 7) -> Optional[pd.DataFrame]:
        """获取人气指数"""
        params = {
            'days': days,
            'time_unit': 'day',
            'api_key': self.api_key
        }
        print(f"人气指数请求参数: {params}")
        
        data = self._make_request("visitors-data/", params=params)
        
        if data and data.get('success') == True:  # 注意：使用success字段
            return pd.DataFrame(data['data'])
        elif data:
            print(f"人气指数API返回错误: {data.get('message', '未知错误')}")
        return None
    
    def predict(self, market: str, code: str, price: float, 
                allow_short: int = 0) -> Optional[Dict]:
        """AI实时预测"""
        headers = {
            'Content-Type': 'application/json', 
            'X-API-KEY': self.api_key
        }
        payload = {
            'market': market,
            'code': code,
            'price': str(price),
            'allow_short': allow_short
        }
        
        print(f"预测请求参数: {payload}")
        print(f"请求头: {headers}")
        
        data = self._make_request("predict/", method='POST', 
                                  headers=headers, data=json.dumps(payload))
        
        if data and data.get('success') == True:
            return data['data']
        elif data:
            print(f"预测API返回错误: {data.get('message', '未知错误')}")
        return None
    
    def get_history(self, market: str, ts_code: str, 
                    start_date: str = None, end_date: str = None,
                    max_items: int = 10000) -> Optional[pd.DataFrame]:
        """获取历史数据 - 使用正确的端点 /history/"""
        params = {
            'api_key': self.api_key,
            'market': market,
            'ts_code': ts_code,
            'table_type': 'market',
            'max_items': max_items  # 添加max_items参数
        }
        
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
            
        # 同时通过header传递API密钥（双重认证）
        headers = {'X-API-KEY': self.api_key}
        
        print(f"历史数据请求参数: {params}")
        print(f"请求头: {headers}")
        
        data = self._make_request("history/", params=params, headers=headers)
        
        if data and data.get('success') == True:
            return pd.DataFrame(data['data'])
        elif data:
            print(f"历史数据API返回错误: {data.get('message', '未知错误')}")
        return None
    
    def get_basic_info(self, market: str, ts_code: str) -> Optional[Dict]:
        """获取基础信息 - 应该使用 /history/ 端点，但table_type='basic'"""
        params = {
            'api_key': self.api_key,
            'market': market,
            'ts_code': ts_code,
            'table_type': 'basic'
        }
        
        headers = {'X-API-KEY': self.api_key}
        
        print(f"基础信息请求参数: {params}")
        
        data = self._make_request("history/", params=params, headers=headers)
        
        if data and data.get('success') == True:
            # 基础信息可能直接返回数据，而不是数组
            if isinstance(data['data'], list) and len(data['data']) > 0:
                return data['data'][0]  # 返回第一条记录
            return data['data']
        elif data:
            print(f"基础信息API返回错误: {data.get('message', '未知错误')}")
        return None


# 综合使用示例
if __name__ == "__main__":
    try:
        # 初始化客户端
        api_key = "YOU-API-KEY"
        print(f"使用API密钥: {api_key[:10]}...")
        
        client = UQToolAPI(api_key=api_key)
        
        # 1. 获取人气指数
        print("\n=== 获取人气指数 ===")
        popularity = client.get_popularity(days=5)
        if popularity is not None:
            print(f"获取到 {len(popularity)} 天人气数据")
            if not popularity.empty:
                print(popularity.head())
        else:
            print("获取人气指数失败")
        
        # 2. AI实时预测
        print("\n=== AI实时预测 ===")
        # 使用完整的价格序列（如你提供的CURL示例）
        price_sequence = "11.52|11.61|11.61|11.51|742369|857197"
        prediction = client.predict(
            market="cnstock",
            code="000001.SZ",
            price=price_sequence,  # 使用完整的价格序列
            allow_short=0
        )
        if prediction:
            print(f"预测结果: {json.dumps(prediction, ensure_ascii=False, indent=2)}")
        else:
            print("预测失败")
        
        # 3. 获取历史数据 - 使用股票数据测试
        print("\n=== 获取历史数据（股票） ===")
        history = client.get_history(
            market="cnstock",  
            ts_code="000001.SZ",
            start_date=(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),  # 使用最近的日期
            end_date=(datetime.now()).strftime('%Y-%m-%d'),
            max_items=1000
        )
        if history is not None:
            print(f"获取到 {len(history)} 条历史记录")
            if not history.empty:
                print(history.head())
        else:
            print("获取历史数据失败")
        
        # 4. 获取基础信息
        print("\n=== 获取基础信息 ===")
        basic_info = client.get_basic_info(
            market="cnstock",
            ts_code="000001.SZ"
        )
        if basic_info:
            print(f"基础信息: {json.dumps(basic_info, ensure_ascii=False, indent=2)}")
        else:
            print("获取基础信息失败")
        
        
            
    except Exception as e:
        print(f"程序执行错误: {e}")
        import traceback
        traceback.print_exc()
