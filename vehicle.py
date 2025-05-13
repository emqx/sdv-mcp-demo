from mcp.server.fastmcp import FastMCP
from util import query_driver_behavior_data

mcp = FastMCP(
    name = "sdv/devices/vehicle",
    log_level="DEBUG",
    mqtt_server_description = "An MCP server that contains tools to query vehicle driving behavior data.",
    mqtt_options={
        "host": "broker.emqx.io",
    }
)

@mcp.tool()
async def query_vehicle_driving_behaviour_data(vehicle_id: str) -> str:
    """
    Asynchronously queries and retrieves driving behavior data for a specific vehicle.

    Args:
        vehicle_id (str): The unique identifier of the vehicle to query.

    Returns:
        str: The driving behavior data for the specified vehicle. The data is similar as following.
        - `time` field means when the event happen.
        - `type` field means the event type, currently it support to report 3 kinds of events: 
            - sudden_acceleration: sudden acceleration.
            - max_speed: max speed during the driving.
            - sudden_deceleration: sudden deceleration.
        - `location` field is the location info when the event is recorded, the value is longitude & latitude respectively
        - `speed` field only applicable when the type is `max_speed`, means the max speed value (unit is km/hour).
    {
        "data": [
            {"time":"2023-01-01 11:12:01", "type": "sudden_acceleration", "location": "116.456963,39.962918"},
            {"time":"2023-01-01 11:12:01", "type": "max_speed", "location": "116.456963,39.962918", "speed": "70km/h"},
            {"time":"2023-01-12 08:11:30", "type": "sudden_deceleration", "location": "116.629816,40.316679"},
            {"time":"2023-01-12 08:12:01", "type": "sudden_deceleration", "location": "116.629818,40.316679"},
            {"time":"2023-01-12 08:12:12", "type": "max_speed", "location": "116.629819,40.316679", "speed": "56km/h"},
            {"time":"2023-01-13 11:12:01", "type": "sudden_deceleration", "location": "116.417510,40.021192"},
            {"time":"2023-01-13 11:12:00", "type": "max_speed", "location": "116.417510,40.021192", "speed": "98km/h"}
        ]
    }

    This function uses the query_driver_behavior_data utility to fetch
    behavioral data associated with the given vehicle ID.
    """
    return query_driver_behavior_data(vehicle_id)

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='mqtt')