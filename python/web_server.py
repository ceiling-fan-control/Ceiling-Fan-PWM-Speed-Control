import os
import logging
from flask import Flask, jsonify, request, render_template

logger = logging.getLogger("air-controller.web")

def create_app(config_manager, controller):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    app = Flask(__name__,
                static_folder=os.path.join(base_dir, "static"),
                template_folder=os.path.join(base_dir, "templates"))

    # Turn off default request logs to prevent console noise (optional but clean)
    # logging.getLogger('werkzeug').setLevel(logging.WARNING)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status", methods=["GET"])
    def get_status():
        status = controller.get_status()
        return jsonify(status)

    @app.route("/api/config", methods=["GET"])
    def get_config():
        cfg = config_manager.get_config()
        return jsonify(cfg)

    @app.route("/api/config", methods=["POST"])
    def update_config():
        try:
            new_cfg = request.get_json()
            if not new_cfg:
                return jsonify({"success": False, "error": "Invalid JSON"}), 400
            
            success = config_manager.save(new_cfg)
            if success:
                controller.scan_devices() # Re-scan devices in case config mappings changed
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to save configuration file"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/select-profile", methods=["POST"])
    def select_profile():
        try:
            data = request.get_json() or {}
            profile_name = data.get("profile")
            if not profile_name:
                return jsonify({"success": False, "error": "Missing 'profile' field"}), 400

            cfg = config_manager.get_config()
            if profile_name not in cfg.get("profiles", {}):
                return jsonify({"success": False, "error": f"Profile '{profile_name}' does not exist"}), 404

            cfg["active_profile"] = profile_name
            success = config_manager.save(cfg)
            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to update profile in config file"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/save-fan-curve", methods=["POST"])
    def save_fan_curve():
        try:
            data = request.get_json() or {}
            fan_id = data.get("fan_id")
            mode = data.get("mode") # "manual" or "curve"
            
            if not fan_id:
                return jsonify({"success": False, "error": "Missing 'fan_id' field"}), 400
            if mode not in ["manual", "curve"]:
                return jsonify({"success": False, "error": "Invalid or missing 'mode' field"}), 400

            cfg = config_manager.get_config()
            active_profile = cfg.get("active_profile", "Standard")
            
            if active_profile not in cfg.get("profiles", {}):
                return jsonify({"success": False, "error": f"Active profile '{active_profile}' is corrupt"}), 500

            fan_profile = cfg["profiles"][active_profile].setdefault(fan_id, {})
            fan_profile["mode"] = mode

            if mode == "manual":
                val = data.get("manual_value")
                if val is None:
                    return jsonify({"success": False, "error": "Missing 'manual_value' for manual mode"}), 400
                fan_profile["manual_value"] = int(val)
            else:
                # Curve mode
                temp_dev = data.get("temp_device_name")
                temp_chan = data.get("temp_channel")
                curve = data.get("curve") # Expected: [[temp, pwm], ...]

                if not temp_dev or not temp_chan or curve is None:
                    return jsonify({"success": False, "error": "Missing temperature source parameters or curve data"}), 400
                
                fan_profile["temp_device_name"] = temp_dev
                fan_profile["temp_channel"] = int(temp_chan)
                fan_profile["curve"] = curve

            success = config_manager.save(cfg)
            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to update fan config"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/detect", methods=["GET"])
    def detect_hardware():
        try:
            detected = controller.detect_all_hardware()
            return jsonify(detected)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/setup-hardware", methods=["POST"])
    def setup_hardware():
        try:
            data = request.get_json() or {}
            fans = data.get("fans")
            if fans is None:
                return jsonify({"success": False, "error": "Missing 'fans' dictionary"}), 400

            cfg = config_manager.get_config()
            cfg["fans"] = fans

            # Find a default temperature source to auto-configure new fans
            default_temp_dev = "k10temp"
            default_temp_chan = 1
            
            detected = controller.detect_all_hardware()
            if "k10temp" not in detected:
                for name in detected.keys():
                    if "coretemp" in name or "cpu" in name or "k10" in name:
                        default_temp_dev = name
                        break
                else:
                    for name, dev in detected.items():
                        if dev.get("temps"):
                            default_temp_dev = name
                            break

            # Ensure all profiles have config blocks for the mapped fans
            default_curve = [[30, 20], [50, 35], [65, 55], [75, 75], [85, 100]]
            
            # Initialize default profiles if they are missing
            if not cfg.get("profiles"):
                cfg["profiles"] = {
                    "Standard": {},
                    "Silent": {},
                    "Performance": {}
                }

            for profile_name, profile_cfg in cfg["profiles"].items():
                # Clean up deleted fans
                for key in list(profile_cfg.keys()):
                    if key not in fans:
                        profile_cfg.pop(key, None)
                
                # Add default curve for new fans
                for fan_id in fans.keys():
                    if fan_id not in profile_cfg:
                        profile_cfg[fan_id] = {
                            "mode": "curve",
                            "manual_value": 50,
                            "temp_device_name": default_temp_dev,
                            "temp_channel": default_temp_chan,
                            "curve": default_curve
                        }

            success = config_manager.save(cfg)
            if success:
                controller.scan_devices()
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to save configuration"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/toggle-identify", methods=["POST"])
    def toggle_identify():
        try:
            data = request.get_json() or {}
            fan_id = data.get("fan_id")
            enable = data.get("identify")
            if not fan_id or enable is None:
                return jsonify({"success": False, "error": "Missing fan_id or identify flag"}), 400
                
            controller.toggle_identify(fan_id, bool(enable))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/load-driver", methods=["POST"])
    def load_driver():
        """Helper endpoint to load nct6775 kernel module if not active."""
        # Check if already loaded
        import subprocess
        try:
            lsmod_out = subprocess.check_output("lsmod", shell=True).decode()
            if "nct6775" in lsmod_out:
                return jsonify({"success": True, "message": "nct6775 driver is already loaded."})
            
            # Attempt to run modprobe. Since we might be running as a user with writable files,
            # running modprobe itself might require sudo. We try it.
            res = subprocess.run(["sudo", "modprobe", "nct6775"], capture_output=True, text=True)
            if res.returncode == 0:
                controller.scan_devices() # Re-scan devices to pick up motherboard sensors
                return jsonify({"success": True, "message": "Successfully loaded nct6775 driver."})
            else:
                return jsonify({
                    "success": False, 
                    "error": f"Failed to load module. Exit code: {res.returncode}. Stderr: {res.stderr}"
                }), 500
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    return app
