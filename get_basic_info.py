import requests
import pandas as pd

def get_basic_info(api_key, market, ts_code):
    """
    获取合约基础信息
    :param api_key: 您的API密钥
    :param market: 市场代码
    :param ts_code: 合约代码
    :return: 合约基础信息
    """
    url = "https://www.uqtool.com/wp-json/swtool/v1/query/"
    
    params = {
        'api_key': api_key,
        'market': market,
        'ts_code': ts_code,
        'table_type': 'basic'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'success':
            basic_info = data.get('data', {})
            
            print(f"合约基础信息 - {ts_code}")
            print("="*50)
            
            # 格式化输出信息
            for key, value in basic_info.items():
                if isinstance(value, dict):
                    print(f"{key}:")
                    for sub_key, sub_value in value.items():
                        print(f"  {sub_key}: {sub_value}")
                else:
                    print(f"{key}: {value}")
            
            # 转换为DataFrame便于进一步处理
            df = pd.DataFrame([basic_info])
            return df
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
    
    # 获取黄金基础信息
    gold_info = get_basic_info(
        api_key=API_KEY,
        market="gold",
        ts_code="XAUUSD.fxcm"
    )
    
    # 获取股票基础信息
    stock_info = get_basic_info(
        api_key=API_KEY,
        market="cnstock",
        ts_code="000001.SZ"
    )
