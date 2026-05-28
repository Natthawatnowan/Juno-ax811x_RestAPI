import time
from RobotFunctions import init_robot, move, jack_up, move_path, jack_down, end_robot

def main():
    print(">> Initializing Robot System...")
    if not init_robot("map.json"):
        print("❌ Initialization failed. Exiting.")
        return

    try:
        print("\n⚡ Mission Started")

        # Step 1: ไปจุด Standby
        print("-> Moving to Point...")
        if not move("Point"): return print("❌ Failed at Step 1")
        time.sleep(1)

        # Step 2: มุดเข้าใต้ Rack (Up)
        print("-> Aligning with Rack (Up)...")
        if not move("Up", move_type="align_with_rack"): return print("❌ Failed at Step 2")

        # Step 3: ยกโหลดขึ้น
        print("-> Jacking Up...")
        if not jack_up(): return print("❌ Failed at Step 3")
        time.sleep(1)

        # Step 4: ลากตาม LineString ไปจุด Down
        print("-> Moving along path to Down...")
        if not move_path("Down"): return print("❌ Failed at Step 4")
        time.sleep(1)

        # Step 5: วาง Rack ลง
        print("-> Jacking Down...")
        if not jack_down(): return print("❌ Failed at Step 5")

        # Step 6: ยกขึ้นเคลียร์สเตตัส
        print("-> Jacking Up...")
        if not jack_up(): return print("❌ Failed at Step 6")

        # Step 7: วิ่งส่งของไป Unload Point
        print("-> Moving to Unload Point...")
        if not move("Up", move_type="to_unload_point"): return print("❌ Failed at Step 7")

        # Step 8: วางลงอย่างสมบูรณ์
        print("-> Final Jacking Down...")
        if not jack_down(): return print("❌ Failed at Step 8")

        # Step 9: กลับจุดสแตนด์บายตัวเปล่า
        print("-> Returning to Point...")
        if not move("Point"): return print("❌ Failed at Step 9")

        print("\n🎉 🎉 🎉 [MISSION FULLY COMPLETED!] 🎉 🎉 🎉")

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by User")
    finally:
        end_robot()

if __name__ == "__main__":
    main()