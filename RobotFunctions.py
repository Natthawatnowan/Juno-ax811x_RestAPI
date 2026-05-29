import time
import json
import threading
import requests
import websocket
import os

class RobotController:
    def __init__(self, robot_ip="192.168.12.1", port="8090", json_path="map.json"):
        self.robot_ip = robot_ip
        self.port = port
        self.base_url = f"http://{self.robot_ip}:{self.port}"
        self.ws_url = f"ws://{self.robot_ip}:{self.port}/ws/v2/topics"
        self.json_path = json_path

        self.waypoints = {}
        self.map_routes = {}
        self.ws_app = None
        self.running = True
        self.virtual_jack_is_up = False 

        self.current_pos = [0.0, 0.0]
        self.current_ori = 0.0
        self.current_linear_vel = 0.0
        self.current_angular_vel = 0.0
        self.jack_state = "unknown"

    def load_waypoints_from_json(self):
        if not os.path.exists(self.json_path):
            print(f"Error: Not found file {self.json_path}")
            return False
        
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            overlays_data = data.get("overlays", {})
            
            if isinstance(overlays_data, str):
                try: 
                    overlays_data = json.loads(overlays_data)
                except Exception: 
                    overlays_data = {}

            features = overlays_data.get("features", []) if isinstance(overlays_data, dict) else []

            for item in features:
                geometry = item.get("geometry", {})
                geom_type = geometry.get("type")
                properties = item.get("properties", {})
                
                if geom_type == "Point":
                    name = properties.get("name")
                    coord = geometry.get("coordinates", [0.0, 0.0])
                    rack_id = properties.get("relatedShelvesAreaId", properties.get("areaId", ""))
                    
                    if name:
                        self.waypoints[name] = {
                            "name": f"Point {name}",
                            "x": coord[0],
                            "y": coord[1],
                            "area_id": rack_id
                        }
                
                elif geom_type == "LineString":
                    coords_list = geometry.get("coordinates", [])
                    if coords_list:
                        feature_id = item.get("id", "map_main_line")
                        self.map_routes[feature_id] = coords_list
                        self.map_routes["map_main_line"] = coords_list

            print(f"JSON Loaded: Loaded {len(self.waypoints)} waypoints and {max(0, len(self.map_routes) - 1)} route lines.")
            return True
        except Exception as e:
            print(f"Error reading JSON file: {e}")
            return False

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            topic = data.get("topic")
            if topic == "/tracked_pose":
                self.current_pos = data.get("pos", [0.0, 0.0])
                self.current_ori = data.get("ori", 0.0)
            elif topic == "/twist_feedback":
                self.current_linear_vel = data.get("linear_velocity", 0.0)
                self.current_angular_vel = data.get("angular_velocity", 0.0)
            elif topic == "/jack_state":
                self.jack_state = data.get("state", "unknown")
        except Exception: 
            pass

    def _on_open(self, ws):
        print("WebSocket Connected")
        ws.send(json.dumps({"enable_topic": "/tracked_pose"}))
        ws.send(json.dumps({"enable_topic": "/twist_feedback"}))
        ws.send(json.dumps({"enable_topic": "/jack_state"}))

    def _on_error(self, ws, error):
        if self.running: 
            print(f"WebSocket Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        if self.running: 
            print("WebSocket Closed")

    def _start_websocket_thread(self):
        self.ws_app = websocket.WebSocketApp(
            self.ws_url, 
            on_open=self._on_open, 
            on_message=self._on_message, 
            on_error=self._on_error, 
            on_close=self._on_close
        )
        self.ws_app.run_forever()

    def init_robot(self):
        url = f"{self.base_url}/chassis/moves"  
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print("Error: Cannot connect to robot")
                return False
        except Exception:
            print("Error: Cannot connect to robot")
            return False

        if not self.load_waypoints_from_json(): 
            return False
            
        ws_thread = threading.Thread(target=self._start_websocket_thread, daemon=True)
        ws_thread.start()
        time.sleep(2) 
        return True

    def send_move_command(self, x, y, move_type="standard", rack_area_id="", route_coordinates="", detour_tolerance=0.0):
        url = f"{self.base_url}/chassis/moves"
        payload = {"creator": "python_script", "type": move_type, "target_x": x, "target_y": y, "target_z": 0.0}
        if move_type in ["align_with_rack", "to_unload_point"] and rack_area_id:
            payload["rack_area_id"] = rack_area_id
        if move_type == "along_given_route" and route_coordinates:
            payload["route_coordinates"] = route_coordinates
            payload["detour_tolerance"] = detour_tolerance
        try:
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
            if response.status_code in [200, 201]: 
                return response.json().get("id")
        except Exception as e: 
            print(f"Error sending move: {e}")
        return None

    def check_move_status(self, move_id):
        try:
            response = requests.get(f"{self.base_url}/chassis/moves/{move_id}", timeout=5)
            if response.status_code == 200:
                return response.json().get("state"), response.json().get("fail_reason_str")
        except Exception: 
            pass
        return "error", "Connection error"

    def wait_for_move_completion(self, move_id, point_name):
        while self.running:
            state, fail_reason = self.check_move_status(move_id)
            if state in ["finished", "succeeded"]:
                print(f"Success: Arrived at {point_name}")
                time.sleep(1)
                return True
            elif state in ["failed", "canceled"]:
                print(f"Failed: Cannot move! Status: {state} | Reason: {fail_reason}")
                return False
            time.sleep(1)
        return False

    def move(self, target, move_type="standard"):
        if target not in self.waypoints:
            print(f"Error: Waypoint name '{target}' not found in JSON")
            return False
        point = self.waypoints[target]
        print(f"Command: Move robot ({move_type}) to {point['name']} (X: {point['x']}, Y: {point['y']})")
        move_id = self.send_move_command(point["x"], point["y"], move_type, rack_area_id=point.get("area_id", ""))
        return self.wait_for_move_completion(move_id, point['name']) if move_id else False

    def move_path(self, target, detour_tolerance=0.0, reverse=False): # 1. เพิ่มตัวแปร reverse
        if target not in self.waypoints:
            print(f"Error: Waypoint name '{target}' not found in JSON")
            return False
        point = self.waypoints[target]
        
        route_coords = self.map_routes.get("map_main_line", [])
        if not route_coords:
            print("Error: No LineString route data found in map file!")
            return False
        
        # 2. เช็กว่าถ้าสั่ง reverse=True ให้กลับลำดับพิกัด
        if reverse:
            route_coords = route_coords[::-1]
            print("Mode: Reverse path execution (6 -> 1)")
            
        route_str = ", ".join([f"{pt[0]}, {pt[1]}" for pt in route_coords])
        
        print(f"Command: Move robot (along_given_route) to {point['name']} (X: {point['x']}, Y: {point['y']})")
        move_id = self.send_move_command(x=point["x"], y=point["y"], move_type="along_given_route", route_coordinates=route_str, detour_tolerance=detour_tolerance)
        return self.wait_for_move_completion(move_id, point['name']) if move_id else False

    def jack_up(self):
        url = f"{self.base_url}/services/jack_up"
        try:
            response = requests.post(url, timeout=5)
            if response.status_code not in [200, 201]:
                print("\n❌ ไม่สามารถส่งคำสั่ง jack_up ได้")
                return False
            print("\n🔼 กำลังยก Jack ขึ้น...")
            time.sleep(1) 
            start_time = time.time()
            while self.running:
                if self.jack_state == "hold" and self.current_linear_vel == 0.0:
                    print("\n⏳ สถานะเป็น hold (ยกสุด) แล้ว.. กำลังหน่วงเวลารอ 3 วินาที เพื่อความปลอดภัย...")
                    time.sleep(3)
                    if self.jack_state == "hold" and self.current_linear_vel == 0.0:
                        print("\n✅ [Jack Up Complete] -> ระบบล็อกแน่นหนา พร้อมเคลื่อนที่ไปจุดถัดไป!")
                        self.virtual_jack_is_up = True 
                        return True
                if time.time() - start_time > 20:
                    print("\n⚠️ [Jack Up Timeout] -> ใช้เวลาในการยกนานเกินไป")
                    return False
                time.sleep(0.5)
        except Exception as e: 
            print(f"\n💥 Error jack_up: {e}")
        return False

    def jack_down(self):
        url = f"{self.base_url}/services/jack_down"
        try:
            response = requests.post(url, timeout=5)
            if response.status_code not in [200, 201]:
                print("\n❌ ไม่สามารถส่งคำสั่ง jack_down ได้")
                return False
            print("\n🔽 กำลังวาง Jack ลง...")
            time.sleep(1) 
            start_time = time.time()
            has_started_down = False
            while self.running:
                if self.jack_state == "jacking_down": 
                    has_started_down = True
                if has_started_down and self.jack_state in ["hold", "unknown"] and self.current_linear_vel == 0.0:
                    print(f"\n⏳ ตรวจพบกลไกหดกลับสนิท (State: {self.jack_state}) -> กำลังหน่วงเวลารอ 3 วินาที...")
                    time.sleep(3)
                    if self.jack_state in ["hold", "unknown"] and self.current_linear_vel == 0.0:
                        print("\n✅ [Jack Down Complete] -> วางชั้นวางเรียบร้อยแล้ว หุ่นยนต์พร้อมเคลื่อนที่ตัวเปล่า!")
                        self.virtual_jack_is_up = False 
                        return True
                if not has_started_down and (time.time() - start_time > 8) and self.jack_state in ["hold", "unknown"]:
                    print("\n⚠️ [Fallback] ไม่พบสเตตัสขยับ แต่เวลาผ่านไปพอสมควรและรถนิ่งสนิท ดำเนินการขั้นตอนถัดไป...")
                    self.virtual_jack_is_up = False
                    return True
                if time.time() - start_time > 20:
                    print("\n⚠️ [Jack Down Timeout] -> ใช้เวลาในการวางนานเกินไป")
                    return False
                time.sleep(0.5)
        except Exception as e: 
            print(f"\n💥 Error jack_down: {e}")
        return False

    def set_remote_mode(self, enable=True):
            url = f"{self.base_url}/services/wheel_control/set_control_mode"
            mode_str = "remote" if enable else "auto"
            payload = {"control_mode": mode_str}
            try:
                response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
                if response.status_code in [200, 201]:
                    return True
            except Exception:
                pass
            return False
    
    def remote_control(self, linear, angular, duration_sec):
        if not (self.ws_app and self.ws_app.sock and self.ws_app.sock.connected):
            return False
            
        payload = {
            "topic": "/twist",
            "linear_velocity": float(linear),
            "angular_velocity": float(angular)
        }
        stop_payload = {
            "topic": "/twist",
            "linear_velocity": 0.0,
            "angular_velocity": 0.0
        }
        
        start_time = time.time()
        interval = 0.1 
        
        try:
            while time.time() - start_time < duration_sec:
                loop_start = time.time()
                self.ws_app.send(json.dumps(payload))
                
                elapsed = time.time() - loop_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            self.ws_app.send(json.dumps(stop_payload))
            return True
        except Exception:
            try:
                self.ws_app.send(json.dumps(stop_payload))
            except Exception:
                pass
        return False

    def end_robot(self):
        print("\nSystem: Terminating process...")
        self.running = False
        if self.ws_app:
            try: 
                self.ws_app.close()
            except Exception: 
                pass
        print("System: Connections closed and resources cleared successfully.")