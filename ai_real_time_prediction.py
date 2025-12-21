#pip install requests pandas
import requests
import json

def ai_real_time_prediction(api_key, market, code, price, allow_short=0):
    """
    AI实时预测接口
    :param api_key: 您的API密钥
    :param market: 市场代码 (如: cnstock, gold, forex等)
    :param code: 合约代码 (如: 000001.SZ, XAUUSD.fxcm等)
    :param price: 当前价格
    :param allow_short: 是否允许做空 (0:不允许, 1:允许)
    :return: 预测结果
    """
    url = "https://www.uqtool.com/wp-json/swtool/v1/predict/"
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-KEY': api_key
    }
    
    data = {
        'market': market,
        'code': code,
        'price': str(price),
        'allow_short': allow_short
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('success'):
            print("AI实时预测成功！")
            print(f"合约: {code}")
            print(f"预测仓位: {result.get('position', 'N/A')}%")
            print(f"置信度: {result.get('confidence', 'N/A')}")
            print(f"建议操作: {result.get('suggestion', 'N/A')}")
            return result
        else:
            print(f"预测失败: {result.get('message', '未知错误')}")
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
    
    # 股票预测示例
    prediction = ai_real_time_prediction(
        api_key=API_KEY,
        market="cnstock",
        code="000001.SZ",
        price=12.50,
        allow_short=0
    )
    
    # 黄金预测示例
    prediction2 = ai_real_time_prediction(
        api_key=API_KEY,
        market="gold",
        code="XAUUSD.fxcm",
        price=1950.25,
        allow_short=1
    )
