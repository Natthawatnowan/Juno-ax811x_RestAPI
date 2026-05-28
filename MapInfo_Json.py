import os
import json
import requests
from dotenv import load_dotenv

# โหลด .env
load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), '.env'))
BASE_URL = os.getenv('BASE_URL')
MAP_NAME = os.getenv('Map_name') or os.getenv('MAP_NAME') # รองรับทั้งสองแบบ

def fetch_map_data(map_name=MAP_NAME, output_file="map.json"):
    if not BASE_URL or not map_name:
        return None

    # ใช้ Session เพื่อความเร็วในการเชื่อมต่อ API (Keep-Alive)
    with requests.Session() as session:
        session.headers.update({"Accept": "application/json"})
        try:
            # 1. ดึงรายชื่อเพื่อหา Map ID
            res = session.get(f"{BASE_URL}/maps", timeout=5)
            if res.status_code != 200: return None
            
            # ค้นหา id ที่ตรงกับ map_name แบบรวดเร็ว
            map_id = next((m.get("id") for m in res.json() if m.get("map_name") == map_name), None)
            if not map_id: return None

            # 2. ดึงข้อมูลรายละเอียดของ Map
            res_detail = session.get(f"{BASE_URL}/maps/{map_id}", timeout=5)
            if res_detail.status_code != 200: return None

            map_data = res_detail.json()

            # 3. แปลง overlays string ให้เป็น JSON object (ถ้ามี)
            overlays = map_data.get("overlays")
            if isinstance(overlays, str):
                try: map_data["overlays"] = json.loads(overlays)
                except json.JSONDecodeError: pass

            # 4. บันทึกไฟล์
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(map_data, f, indent=2, ensure_ascii=False)

            return map_data

        except requests.RequestException:
            return None

if __name__ == "__main__":
    # เรียกใช้งาน (Clean & Minimal Print ด้านนอกเพื่อความสวยงาม)
    result = fetch_map_data()
    if result:
        print(f"Success: Saved '{result.get('map_name')}' to map.json")
    else:
        print("Error: Process failed or Map not found.")