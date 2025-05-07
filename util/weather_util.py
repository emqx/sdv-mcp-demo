import requests
from dotenv import load_dotenv
from .driver_behavior import load_json_file
import os

load_dotenv()


apiKey = os.getenv('JUHE_API_KEY') 

def query_province_id(province: str) -> str:
    provinces = load_json_file("province_ids.json")["provinces"]
    for p in provinces:
        if p["province"] == province:
            return p["id"]
    
    raise ValueError(f"Province '{province}' not found")

def query_city_id(province_id: str, city_name: str) -> str:
    requestParams = {
        'key': apiKey,
        'province_id': province_id
    }
    apiUrl = 'http://v.juhe.cn/historyWeather/citys' 
    response = requests.get(apiUrl, params=requestParams)
    if response.status_code == 200:
        data = response.json()
        if data['error_code'] == 0 and 'result' in data:
            for city in data['result']:
                if city['city_name'] == city_name:
                    return city['id']
        else:
            raise Exception(f"API Error: {data.get('reason', 'Unknown error')}")
    
    raise ValueError(f"City '{city_name}' cannot be found in province_id: {province_id}")


def query_weather_by_city_id(city_id: str, date: str) -> str:
    apiUrl = 'http://v.juhe.cn/historyWeather/weather' 
    requestParams = {
        'key': apiKey,
        'city_id': city_id,
        'weather_date': date,
    }
    response = requests.get(apiUrl, params=requestParams)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get the weather info for {city_id} at {date}")

def main():
    try:
        # city_id = "87"
        # date = "2023-01-12"
        # result = query_weather_by_city_id(city_id, date)
        # print(f"Weather data for city {city_id} on {date}:")
        # print(result)
        result = query_province_id("北京")
        # result = query_city_id("3", "延庆")
        print(result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
