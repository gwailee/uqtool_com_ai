import requests
import pandas as pd
import json
from typing import Optional, Dict, Any
import time

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
            if method.upper() == 'GET':
                response = self.session.get(url, **kwargs)
            elif method.upper() == 'POST':
                response = self.session.post(url, **kwargs)
            else:
                raise ValueError(f"不支持的请求方法: {method}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return None
    
    def get_popularity(self, days: int = 7) -> Optional[pd.DataFrame]:
        """获取人气指数"""
        params = {
            'days': days,
            'time_unit': 'day',
            'api_key': self.api_key
        }
        data = self._make_request("visitors-data/", params=params)
        
        if data and data.get('status') == 'success':
            return pd.DataFrame(data['data'])
        return None
    
    def predict(self, market: str, code: str, price: float, 
                allow_short: int = 0) -> Optional[Dict]:
        """AI实时预测"""
        headers = {'Content-Type': 'application/json', 'X-API-KEY': self.api_key}
        payload = {
            'market': market,
            'code': code,
            'price': str(price),
            'allow_short': allow_short
        }
        
        return self._make_request("predict/", method='POST', 
                                  headers=headers, data=json.dumps(payload))
    
    def get_history(self, market: str, ts_code: str, 
                    start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        """获取历史数据"""
        params = {
            'api_key': self.api_key,
            'market': market,
            'ts_code': ts_code,
            'table_type': 'market'
        }
        
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
            
        data = self._make_request("query/", params=params)
        
        if data and data.get('status') == 'success':
            return pd.DataFrame(data['data'])
        return None
    
    def get_basic_info(self, market: str, ts_code: str) -> Optional[Dict]:
        """获取基础信息"""
        params = {
            'api_key': self.api_key,
            'market': market,
            'ts_code': ts_code,
            'table_type': 'basic'
        }
        
        data = self._make_request("query/", params=params)
        
        if data and data.get('status') == 'success':
            return data['data']
        return None

# 综合使用示例
if __name__ == "__main__":
    # 初始化客户端
    client = UQToolAPI(api_key="您的API密钥")
    
    # 1. 获取人气指数
    print("=== 获取人气指数 ===")
    popularity = client.get_popularity(days=5)
    if popularity is not None:
        print(f"获取到 {len(popularity)} 天人气数据")
    
    # 2. AI实时预测
    print("\n=== AI实时预测 ===")
    prediction = client.predict(
        market="cnstock",
        code="000001.SZ",
        price=12.50,
        allow_short=0
    )
    if prediction:
        print(f"预测结果: {prediction}")
    
    # 3. 获取历史数据
    print("\n=== 获取历史数据 ===")
    history = client.get_history(
        market="gold",
        ts_code="XAUUSD.fxcm",
        start_date="2024-01-01",
        end_date="2024-01-31"
    )
    if history is not None:
        print(f"获取到 {len(history)} 条历史记录")
    
    # 4. 获取基础信息
    print("\n=== 获取基础信息 ===")
    basic_info = client.get_basic_info(
        market="cnstock",
        ts_code="000001.SZ"
    )
    if basic_info:
        print(f"合约名称: {basic_info.get('name', 'N/A')}")
