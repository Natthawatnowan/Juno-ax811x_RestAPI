import os
import json
import requests
from dotenv import load_dotenv

# โหลด .env
load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), '.env'))
BASE_URL = os.getenv('BASE_URL')
MAP_NAME = os.getenv('Map_name') or os.getenv('MAP_NAME')

def fetch_map_data(map_name=MAP_NAME, output_file="map.json"):
    # ตรวจสอบค่าตัวแปรจาก .env
    if not BASE_URL:
        print("❌ Error: 'BASE_URL' ไม่ถูกตั้งค่าใน .env หรือหาไฟล์ .env ไม่เจอ")
        return None
    if not map_name:
        print("❌ Error: 'MAP_NAME' ไม่ถูกตั้งค่าใน .env หรือไม่ได้ส่งเข้ามาในฟังก์ชัน")
        return None

    # ตัดเครื่องหมาย / ที่อาจจะเกินมาท้าย URL เพื่อป้องกัน URL เพี้ยน
    base_url_clean = BASE_URL.rstrip('/')

    with requests.Session() as session:
        session.headers.update({"Accept": "application/json"})
        try:
            # 1. ดึงรายชื่อเพื่อหา Map ID
            url = f"{base_url_clean}/maps"
            res = session.get(url, timeout=5)
            
            if res.status_code != 200:
                print(f"❌ Error: เรียกดูรายการ Map ไม่สำเร็จ (Status Code: {res.status_code}) จาก URL: {url}")
                return None
            
            # ค้นหา id ที่ตรงกับ map_name แบบไม่สนใจพิมพ์เล็ก-พิมพ์ใหญ่ (Case-insensitive) เพื่อความยืดหยุ่น
            maps_list = res.json()
            map_id = next((m.get("id") for m in maps_list if str(m.get("map_name")).strip().lower() == str(map_name).strip().lower()), None)
            
            if not map_id:
                print(f"❌ Error: ไม่พบ Map ที่ชื่อ '{map_name}' ในระบบ (มีแค่ชื่อ: {[m.get('map_name') for m in maps_list]})")
                return None

            # 2. ดึงข้อมูลรายละเอียดของ Map
            detail_url = f"{base_url_clean}/maps/{map_id}"
            res_detail = session.get(detail_url, timeout=5)
            if res_detail.status_code != 200:
                print(f"❌ Error: ไม่สามารถดึงรายละเอียด Map ID {map_id} ได้ (Status Code: {res_detail.status_code})")
                return None

            map_data = res_detail.json()

            # 3. แปลง overlays string ให้เป็น JSON object
            overlays = map_data.get("overlays")
            if isinstance(overlays, str):
                try: 
                    map_data["overlays"] = json.loads(overlays)
                except json.JSONDecodeError: 
                    print("⚠️ Warning: ไม่สามารถแปลงโครงสร้าง 'overlays' จาก String เป็น JSON ได้")

            # 4. บันทึกไฟล์ (สร้างโฟลเดอร์ให้อัตโนมัติถ้าไม่มี เพื่อกันพัง)
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(map_data, f, indent=2, ensure_ascii=False)

            return map_data

        except requests.Timeout:
            print("❌ Error: การเชื่อมต่อไปยัง API หมดเวลา (Timeout)")
            return None
        except requests.ConnectionError:
            print(f"❌ Error: ไม่สามารถเชื่อมต่อกับ Server ได้ (โปรดเช็คว่าเปิด Server หรือใส่ BASE_URL ถูกไหม: {base_url_clean})")
            return None
        except requests.RequestException as e:
            print(f"❌ Error: เกิดข้อผิดพลาดของ Requests: {e}")
            return None

if __name__ == "__main__":
    print("🔄 กำลังเริ่มทำงาน...")
    result = fetch_map_data()
    if result:
        print(f"\n✨ Success: บันทึกข้อมูลแผนที่ '{result.get('map_name')}' ลงในไฟล์ 'map.json' เรียบร้อยแล้ว!")