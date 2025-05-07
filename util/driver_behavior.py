import os
import json


def query_driver_behavior_data(vehicle_id:str) -> str:
    """
    Retrieves driver behavior data from a JSON file for a given vehicle ID.
    
    Args:
        vehicle_id (str): The unique identifier for the vehicle
        
    Returns:
        str: JSON data containing the driver's behavior information
        
    Note:
        Currently returns hardcoded 'vehicle_00001.json' data regardless of vehicle_id.
        This may need to be updated to use the actual vehicle_id parameter.
    """
    return load_json_file("vehicle_00001.json")

def load_json_file(file_name: str ="") -> str:
    try:
        # Get base directory for file
        current_file = os.path.abspath(__file__)
        base_dir = os.path.join(os.path.dirname(current_file), '..', 'data')
        
        # Load base folder
        file = os.path.join(base_dir, file_name)
        if not os.path.exists(file):
            raise FileNotFoundError(f"File is not found at {file_name}")

        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
        
    except json.JSONDecodeError as e:
        raise Exception(f"Error parsing JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to load file: {str(e)}")
    

def main():
    try:
        # Load the vehicle data
        vehicle_data = load_json_file("vehicle_00001.json")
        print("Successfully loaded vehicle data:")
        print(json.dumps(vehicle_data, indent=2))
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
    

