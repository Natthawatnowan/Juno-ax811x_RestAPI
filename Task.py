import os
import time
from dotenv import load_dotenv
from RobotFunctions import RobotController

def setup_robot():
    load_dotenv()
    
    base_url_env = os.getenv("BASE_URL", "http://192.168.12.1:8090")
    map_name = os.getenv("MAP_NAME", "map.json")
    
    if "://" in base_url_env:
        url_part = base_url_env.split("://")[1]
    else:
        url_part = base_url_env
        
    if ":" in url_part:
        robot_ip, port = url_part.split(":")
    else:
        robot_ip = url_part
        port = "8090"

    map_file = "map.json" if not map_name.endswith(".json") else map_name

    robot = RobotController(robot_ip=robot_ip, port=port, json_path=map_file)
    
    if not robot.init_robot():
        return None
        
    return robot

def run_task(robot):
    try:
        if not robot.move("Point"): 
            return

        if not robot.move("Up", move_type="align_with_rack"): 
            return

        if not robot.jack_up(): 
            return
    
        if not robot.move_path("Down"): 
            return
        time.sleep(1)

        if not robot.jack_down(): 
            return

        if not robot.set_remote_mode(enable=True):
            return
        
        if not robot.remote_control(-1.0, 0.0, duration_sec=12.0): 
            print("Failed to execute remote control movement")
            return

        if not robot.set_remote_mode(enable=False):
            return

        if not robot.move_path("Up", reverse=True): 
            return

        if not robot.move("Point"): 
            return

        print("SUCCESS")

    except KeyboardInterrupt:
        pass
    finally:
        robot.set_remote_mode(enable=False)  
        robot.end_robot()

def main():
    robot = setup_robot()
    if robot is None:
        return
        
    run_task(robot)

if __name__ == "__main__":
    main()