#pip install requests pandas
import requests
import pandas as pd

def get_popularity_index(api_key, days=7, time_unit='day'):
    """
    获取人气指数数据
    :param api_key: 您的API密钥
    :param days: 查询天数
    :param time_unit: 时间单位 (day/hour)
    :return: 人气指数数据
    """
    url = "https://www.uqtool.com/wp-json/swtool/v1/visitors-data/"
    
    params = {
        'days': days,
        'time_unit': time_unit,
        'api_key': api_key
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == 'success':
            # 转换为DataFrame便于分析
            df = pd.DataFrame(data['data'])
            print("人气指数数据获取成功！")
            print(f"数据条目: {len(df)}")
            print(df.head())
            return df
        else:
            print(f"请求失败: {data.get('message', '未知错误')}")
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
    popularity_data = get_popularity_index(API_KEY, days=7)
