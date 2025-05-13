from mcp.server.fastmcp import FastMCP
from util import query_city_id,query_province_id,query_weather_by_city_id

mcp = FastMCP(
    name = "sdv/system_tools/weather",
    log_level="DEBUG",
    mqtt_server_description = "An MCP server that contains tools to query weather data.",
    mqtt_options={
        "host": "broker.emqx.io",
    }
)

@mcp.tool()
async def query_by_province_id(province: str) -> str:
    """
    Query the province ID by province name.

    Args:
        province (str): The name of the province in Chinese (e.g., '安徽', '北京')

    Returns:
        str: The ID of the province as a string

    Raises:
        ValueError: If the province name is not found in the data
    """
    return query_province_id(province)

@mcp.tool()
def query_by_city_id(province_id: str, city_name: str) -> str:
    """
    Query the city ID by province ID and city name from the weather API.

    Args:
        province_id (str): The ID of the province (obtained from query_province_id)
        city_name (str): The name of the city in Chinese (e.g., '海淀', '北京')

    Returns:
        str: The ID of the city as a string

    Raises:
        ValueError: If the city name is not found in the specified province
        Exception: If the API request fails
    """
    return query_city_id(province_id=province_id, city_name=city_name)

@mcp.tool()
async def query_history_weather_by_city_id_and_date(city_id:str, date_to_query:str) -> str:
    """
    Query historical weather data for a specific city and date from the weather API.

    Args:
        city_id (str): The ID of the city (obtained from query_by_city_id)
        date_to_query (str): The date to query weather for, in format 'YYYY-MM-DD'

    Returns:
        str: JSON response containing weather information for the specified city and date

    Raises:
        Exception: If the API request fails or returns an error status code
    """
    return query_weather_by_city_id(city_id=city_id, date=date_to_query)

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='mqtt')