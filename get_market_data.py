#pip install requests pandas
import requests
import pandas as pd
from datetime import datetime, timedelta

def get_market_data(api_key, market, ts_code, start_date=None, end_date=None):
    """
    获取市场历史数据
    :param api_key: 您的API密钥
    :param market: 市场代码
    :param ts_code: 合约代码
    :param start_date: 开始日期 (YYYY-MM-DD)
    :param end_date: 结束日期 (YYYY-MM-DD)
    :return: 市场历史数据
    """
    url = "https://www.uqtool.com/wp-json/swtool/v1/query/"
    
    # 设置默认日期（最近30天）
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    params = {
        'api_key': api_key,
        'market': market,
        'ts_code': ts_code,
        'start_date': start_date,
        'end_date': end_date,
        'table_type': 'market'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'success':
            records = data.get('data', [])
            if records:
                # 转换为DataFrame
                df = pd.DataFrame(records)
                
                # 转换日期列
                if 'trade_date' in df.columns:
                    df['trade_date'] = pd.to_datetime(df['trade_date'])
                
                print(f"获取到 {len(df)} 条历史数据")
                print(f"时间范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
                print("\n数据预览:")
                print(df.head())
                print("\n数据统计:")
                print(df.describe())
                
                return df
            else:
                print("未查询到数据")
                return None
        else:
            print(f"查询失败: {data.get('message', '未知错误')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except Exception as e:
        print(f"处理数据错误: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    API_KEY = "您的API密钥"
    
    # 获取黄金历史数据
    gold_data = get_market_data(
        api_key=API_KEY,
        market="gold",
        ts_code="XAUUSD.fxcm",
        start_date="2024-01-01",
        end_date="2024-03-01"
    )
    
    # 获取股票历史数据
    stock_data = get_market_data(
        api_key=API_KEY,
        market="cnstock",
        ts_code="000001.SZ"
    )
