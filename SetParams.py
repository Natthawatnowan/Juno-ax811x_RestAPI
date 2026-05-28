import os
import requests
import json
from dotenv import load_dotenv

# หาตำแหน่งโฟลเดอร์ของไฟล์นี้อัตโนมัติ (รองรับสแลชทุกรูปแบบบน Windows)
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ดึงค่าจาก .env ไปใช้งาน
BASE_URL = f"{os.getenv('BASE_URL')}/robot-params"

TARGET_PARAMS = [
    "/wheel_control/max_forward_velocity",
    "/wheel_control/max_backward_velocity",
    "/wheel_control/max_forward_acc",
    "/wheel_control/max_forward_decel",
    "/wheel_control/max_angular_velocity",
    "/wheel_control/acc_smoother/smooth_level",
    "/planning/auto_hold",
    "/control/bump_tolerance",
    "/control/bump_based_speed_limit/enable"
]

def get_params():
    try:
        res = requests.get(BASE_URL, timeout=5)
        if res.status_code == 200:
            filtered = {k: v for k, v in res.json().items() if k in TARGET_PARAMS}
            print(f"\n--- Params ---\n{json.dumps(filtered, indent=2)}")
            return filtered
    except Exception as e: print(f"Get Error: {e}")
    return None

def set_params(forward_vel, backward_vel, forward_acc, forward_decel, angular_vel, 
               bump_tolerance, smooth_level="normal", auto_hold=True, bump_speed_limit=True):
    payload = {
        "/wheel_control/max_forward_velocity": forward_vel,
        "/wheel_control/max_backward_velocity": backward_vel,
        "/wheel_control/max_forward_acc": forward_acc,
        "/wheel_control/max_forward_decel": forward_decel,
        "/wheel_control/max_angular_velocity": angular_vel,
        "/wheel_control/acc_smoother/smooth_level": smooth_level,
        "/planning/auto_hold": auto_hold,
        "/control/bump_tolerance": bump_tolerance,
        "/control/bump_based_speed_limit/enable": bump_speed_limit
    }
    try:
        res = requests.post(BASE_URL, json=payload, timeout=5)
        print("Set Params: Success" if res.status_code in [200, 201] else f"Set Failed: {res.status_code}")
    except Exception as e: print(f"Set Error: {e}")

if __name__ == "__main__":
    set_params(
        forward_vel=1.5, 
        backward_vel=-0.6, 
        forward_acc=0.4, 
        forward_decel=-2.0, 
        angular_vel=0.78, 
        bump_tolerance=0.5
    )
    
    get_params()