import time
import json
import threading
import requests
import websocket
import math
import os

ROBOT_IP = "192.168.12.1"
PORT = "8090"
BASE_URL = f"http://{ROBOT_IP}:{PORT}"
WS_URL = f"ws://{ROBOT_IP}:{PORT}/ws/v2/topics"

WAYPOINTS = {}
MAP_ROUTES = {}
ws_app = None
running = True
virtual_jack_is_up = False 

current_pos = [0.0, 0.0]
current_ori = 0.0
current_linear_vel = 0.0
current_angular_vel = 0.0
jack_state = "unknown"

def load_waypoints_from_json(json_file_path="map.json"):
    global WAYPOINTS, MAP_ROUTES
    if not os.path.exists(json_file_path):
        print(f"Error: Not found file {json_file_path}")
        return False
    
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        overlays_data = data.get("overlays", {})
        
        # ปรับปรุง: รองรับทั้ง overlays แบบ String (แบบเก่า) และแบบ Dict/Object (แบบใหม่จาก Gen_map)
        if isinstance(overlays_data, str):
            try: overlays_data = json.loads(overlays_data)
            except Exception: overlays_data = {}

        features = overlays_data.get("features", []) if isinstance(overlays_data, dict) else []

        # วนลูปสแกนหาจุดเหมือนเดิม
        for item in features:
            geometry = item.get("geometry", {})
            geom_type = geometry.get("type")
            properties = item.get("properties", {})
            
            if geom_type == "Point":
                name = properties.get("name")
                coord = geometry.get("coordinates", [0.0, 0.0])
                rack_id = properties.get("relatedShelvesAreaId", properties.get("areaId", ""))
                
                if name:
                    WAYPOINTS[name] = {
                        "name": f"Point {name}",
                        "x": coord[0],
                        "y": coord[1],
                        "area_id": rack_id
                    }
            
            elif geom_type == "LineString":
                coords_list = geometry.get("coordinates", [])
                if coords_list:
                    feature_id = item.get("id", "map_main_line")
                    MAP_ROUTES[feature_id] = coords_list
                    MAP_ROUTES["map_main_line"] = coords_list

        print(f"JSON Loaded: Loaded {len(WAYPOINTS)} waypoints and {max(0, len(MAP_ROUTES) - 1)} route lines.")
        return True
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return False

def on_message(ws, message):
    global current_pos, current_ori, current_linear_vel, current_angular_vel, jack_state
    try:
        data = json.loads(message)
        topic = data.get("topic")
        if topic == "/tracked_pose":
            current_pos = data.get("pos", [0.0, 0.0])
            current_ori = data.get("ori", 0.0)
        elif topic == "/twist_feedback":
            current_linear_vel = data.get("linear_velocity", 0.0)
            current_angular_vel = data.get("angular_velocity", 0.0)
        elif topic == "/jack_state":
            jack_state = data.get("state", "unknown")
    except Exception: pass

def on_open(ws):
    print("WebSocket Connected")
    ws.send(json.dumps({"enable_topic": "/tracked_pose"}))
    ws.send(json.dumps({"enable_topic": "/twist_feedback"}))
    ws.send(json.dumps({"enable_topic": "/jack_state"}))

def on_error(ws, error):
    if running: print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    if running: print("WebSocket Closed")

def start_websocket_thread():
    global ws_app
    ws_app = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
    ws_app.run_forever()

def init_robot(json_path="map.json"):
    url = f"{BASE_URL}/chassis/moves"  
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            print("Error: Cannot connect to robot")
            return False
    except Exception:
        print("Error: Cannot connect to robot")
        return False

    if not load_waypoints_from_json(json_path): return False
    ws_thread = threading.Thread(target=start_websocket_thread, daemon=True)
    ws_thread.start()
    time.sleep(2) 
    return True

def send_move_command(x, y, move_type="standard", rack_area_id="", route_coordinates="", detour_tolerance=0.0):
    url = f"{BASE_URL}/chassis/moves"
    payload = {"creator": "python_script", "type": move_type, "target_x": x, "target_y": y, "target_z": 0.0}
    if move_type in ["align_with_rack", "to_unload_point"] and rack_area_id:
        payload["rack_area_id"] = rack_area_id
    if move_type == "along_given_route" and route_coordinates:
        payload["route_coordinates"] = route_coordinates
        payload["detour_tolerance"] = detour_tolerance
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        if response.status_code in [200, 201]: return response.json().get("id")
    except Exception as e: print(f"Error sending move: {e}")
    return None

def check_move_status(move_id):
    try:
        response = requests.get(f"{BASE_URL}/chassis/moves/{move_id}", timeout=5)
        if response.status_code == 200:
            return response.json().get("state"), response.json().get("fail_reason_str")
    except Exception: pass
    return "error", "Connection error"

def wait_for_move_completion(move_id, point_name):
    while running:
        state, fail_reason = check_move_status(move_id)
        if state in ["finished", "succeeded"]:
            print(f"Success: Arrived at {point_name}")
            time.sleep(1)
            return True
        elif state in ["failed", "canceled"]:
            print(f"Failed: Cannot move! Status: {state} | Reason: {fail_reason}")
            return False
        time.sleep(1)
    return False

def move(target, move_type="standard"):
    if target not in WAYPOINTS:
        print(f"Error: Waypoint name '{target}' not found in JSON")
        return False
    point = WAYPOINTS[target]
    print(f"Command: Move robot ({move_type}) to {point['name']} (X: {point['x']}, Y: {point['y']})")
    move_id = send_move_command(point["x"], point["y"], move_type, rack_area_id=point.get("area_id", ""))
    return wait_for_move_completion(move_id, point['name']) if move_id else False

def move_path(target, detour_tolerance=0.0):
    if target not in WAYPOINTS:
        print(f"Error: Waypoint name '{target}' not found in JSON")
        return False
    point = WAYPOINTS[target]
    route_coords = MAP_ROUTES.get("map_main_line", [])
    if not route_coords:
        print("Error: No LineString route data found in map file!")
        return False
    route_str = ", ".join([f"{pt[0]}, {pt[1]}" for pt in route_coords])
    print(f"Command: Move robot (along_given_route) to {point['name']} (X: {point['x']}, Y: {point['y']})")
    move_id = send_move_command(x=point["x"], y=point["y"], move_type="along_given_route", route_coordinates=route_str, detour_tolerance=detour_tolerance)
    return wait_for_move_completion(move_id, point['name']) if move_id else False

# --- ฟังก์ชันควบคุมกลไกทางกายภาพ (ใช้ของเดิมของคุณ 100% ไม่เปลี่ยนแปลงอะไรเลย) ---
def jack_up():
    global virtual_jack_is_up
    url = f"{BASE_URL}/services/jack_up"
    try:
        response = requests.post(url, timeout=5)
        if response.status_code not in [200, 201]:
            print("\n❌ ไม่สามารถส่งคำสั่ง jack_up ได้")
            return False
        print("\n🔼 กำลังยก Jack ขึ้น...")
        time.sleep(1) 
        start_time = time.time()
        while running:
            if jack_state == "hold" and current_linear_vel == 0.0:
                print("\n⏳ สถานะเป็น hold (ยกสุด) แล้ว.. กำลังหน่วงเวลารอ 3 วินาที เพื่อความปลอดภัย...")
                time.sleep(3)
                if jack_state == "hold" and current_linear_vel == 0.0:
                    print("\n✅ [Jack Up Complete] -> ระบบล็อกแน่นหนา พร้อมเคลื่อนที่ไปจุดถัดไป!")
                    virtual_jack_is_up = True 
                    return True
            if time.time() - start_time > 20:
                print("\n⚠️ [Jack Up Timeout] -> ใช้เวลาในการยกนานเกินไป")
                return False
            time.sleep(0.5)
    except Exception as e: print(f"\n💥 Error jack_up: {e}")
    return False

def jack_down():
    global virtual_jack_is_up
    url = f"{BASE_URL}/services/jack_down"
    try:
        response = requests.post(url, timeout=5)
        if response.status_code not in [200, 201]:
            print("\n❌ ไม่สามารถส่งคำสั่ง jack_down ได้")
            return False
        print("\n🔽 กำลังวาง Jack ลง...")
        time.sleep(1) 
        start_time = time.time()
        has_started_down = False
        while running:
            if jack_state == "jacking_down": has_started_down = True
            if has_started_down and jack_state in ["hold", "unknown"] and current_linear_vel == 0.0:
                print(f"\n⏳ ตรวจพบกลไกหดกลับสนิท (State: {jack_state}) -> กำลังหน่วงเวลารอ 3 วินาที...")
                time.sleep(3)
                if jack_state in ["hold", "unknown"] and current_linear_vel == 0.0:
                    print("\n✅ [Jack Down Complete] -> วางชั้นวางเรียบร้อยแล้ว หุ่นยนต์พร้อมเคลื่อนที่ตัวเปล่า!")
                    virtual_jack_is_up = False 
                    return True
            if not has_started_down and (time.time() - start_time > 8) and jack_state in ["hold", "unknown"]:
                print("\n⚠️ [Fallback] ไม่พบสเตตัสขยับ แต่เวลาผ่านไปพอสมควรและรถนิ่งสนิท ดำเนินการขั้นตอนถัดไป...")
                virtual_jack_is_up = False
                return True
            if time.time() - start_time > 20:
                print("\n⚠️ [Jack Down Timeout] -> ใช้เวลาในการวางนานเกินไป")
                return False
            time.sleep(0.5)
    except Exception as e: print(f"\n💥 Error jack_down: {e}")
    return False

def end_robot():
    global running
    print("\nSystem: Terminating process...")
    running = False
    if ws_app:
        try: ws_app.close()
        except Exception: pass
    print("System: Connections closed and resources cleared successfully.")