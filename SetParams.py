import os
import requests
import json
import yaml
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

BASE_URL = f"{os.getenv('BASE_URL')}/robot-params"
YAML_PATH = os.path.join(BASE_DIR, 'JunoParams.yaml')

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
            print(f"CURRENT_PARAMS: {json.dumps(filtered)}")
            return filtered
    except Exception:
        pass
    return None

def set_params(forward_vel, backward_vel, forward_acc, forward_decel, angular_vel, 
               bump_tolerance, smooth_level, auto_hold, bump_speed_limit):
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
        if res.status_code in [200, 201]:
            print("SET_PARAMS_SUCCESS")
            return True
    except Exception:
        pass
    return False

def main():
    config = {}
    if os.path.exists(YAML_PATH):
        try:
            with open(YAML_PATH, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    forward_vel = float(config.get("PARAM_FORWARD_VEL", 1.5))
    backward_vel = float(config.get("PARAM_BACKWARD_VEL", -0.6))
    forward_acc = float(config.get("PARAM_FORWARD_ACC", 0.4))
    forward_decel = float(config.get("PARAM_FORWARD_DECEL", -2.0))
    angular_vel = float(config.get("PARAM_ANGULAR_VEL", 0.78))
    bump_tolerance = float(config.get("PARAM_BUMP_TOLERANCE", 0.5))
    smooth_level = str(config.get("PARAM_SMOOTH_LEVEL", "normal"))
    
    auto_hold = config.get("PARAM_AUTO_HOLD", True)
    bump_speed_limit = config.get("PARAM_BUMP_SPEED_LIMIT", True)

    if not set_params(
        forward_vel=forward_vel,
        backward_vel=backward_vel,
        forward_acc=forward_acc,
        forward_decel=forward_decel,
        angular_vel=angular_vel,
        bump_tolerance=bump_tolerance,
        smooth_level=smooth_level,
        auto_hold=auto_hold,
        bump_speed_limit=bump_speed_limit
    ):
        return

    get_params()

if __name__ == "__main__":
    main()