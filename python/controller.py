import os
import glob
import time
import logging
import fnmatch
from threading import Lock

logger = logging.getLogger("air-controller.controller")

class FanController:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.lock = Lock()
        self.device_map = {}  # Matches device_name pattern -> absolute hwmon path
        self.status = {}      # Shared state containing real-time measurements
        self.last_temps = {}  # Cache of last read temperatures for safety fallbacks
        self.identifying_fans = {}  # Maps fan_id -> expiration_timestamp
        
        self.scan_devices()

    def scan_devices(self):
        """Scans /sys/class/hwmon/hwmon* and maps device names to paths."""
        new_map = {}
        paths = glob.glob("/sys/class/hwmon/hwmon*")
        for path in paths:
            name_file = os.path.join(path, "name")
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r") as f:
                        name = f.read().strip()
                        new_map[name] = path
                        logger.info(f"Detected hwmon device '{name}' at {path}")
                except Exception as e:
                    logger.error(f"Error reading name from {name_file}: {e}")
        
        with self.lock:
            self.device_map = new_map
            logger.info(f"Scanning completed. Active mapping: {self.device_map}")

    def detect_all_hardware(self):
        """Scans the system for all hwmon devices and lists their temperature sensors,
        RPM sensors, and writeable PWM channels."""
        self.scan_devices()  # Refresh mapping
        
        detected = {}
        with self.lock:
            active_devices = list(self.device_map.items())

        for name, path in active_devices:
            device_info = {
                "path": path,
                "temps": [],
                "fans": []
            }
            
            # Find temperature sensors (temp*_input)
            temp_files = glob.glob(os.path.join(path, "temp*_input"))
            for temp_file in temp_files:
                filename = os.path.basename(temp_file)
                try:
                    chan_str = filename.replace("temp", "").replace("_input", "")
                    chan = int(chan_str)
                except ValueError:
                    continue
                
                label = ""
                label_file = os.path.join(path, f"temp{chan}_label")
                if os.path.exists(label_file):
                    try:
                        with open(label_file, "r") as lf:
                            label = lf.read().strip()
                    except Exception:
                        pass
                
                value = None
                try:
                    with open(temp_file, "r") as tf:
                        value = float(tf.read().strip()) / 1000.0
                except Exception:
                    pass
                
                device_info["temps"].append({
                    "channel": chan,
                    "label": label,
                    "current_value": value
                })
            
            # Find fans (fan*_input)
            fan_files = glob.glob(os.path.join(path, "fan*_input"))
            for fan_file in fan_files:
                filename = os.path.basename(fan_file)
                try:
                    chan_str = filename.replace("fan", "").replace("_input", "")
                    chan = int(chan_str)
                except ValueError:
                    continue
                
                label = ""
                label_file = os.path.join(path, f"fan{chan}_label")
                if os.path.exists(label_file):
                    try:
                        with open(label_file, "r") as lf:
                            label = lf.read().strip()
                    except Exception:
                        pass
                
                rpm = 0
                try:
                    with open(fan_file, "r") as ff:
                        rpm = int(ff.read().strip())
                except Exception:
                    pass
                
                has_pwm = os.path.exists(os.path.join(path, f"pwm{chan}"))
                
                device_info["fans"].append({
                    "channel": chan,
                    "label": label,
                    "current_rpm": rpm,
                    "has_pwm": has_pwm
                })
                
            device_info["temps"].sort(key=lambda x: x["channel"])
            device_info["fans"].sort(key=lambda x: x["channel"])
            
            detected[name] = device_info
            
        return detected

    def resolve_device_path(self, pattern):
        """Finds the absolute path of a device matching a pattern (e.g. 'nct*' or 'k10temp')."""
        with self.lock:
            # First try exact match
            if pattern in self.device_map:
                return self.device_map[pattern]
            
            # Next, try pattern matching (fnmatch)
            for name, path in self.device_map.items():
                if fnmatch.fnmatch(name, pattern):
                    return path
        return None

    def toggle_identify(self, fan_id, enable):
        """Starts or stops the fan finder (identify) mode for a fan channel."""
        with self.lock:
            if enable:
                # Override to 100% for 20 seconds
                self.identifying_fans[fan_id] = time.time() + 20.0
                logger.info(f"Started identify mode for fan '{fan_id}' (expires in 20s)")
            else:
                self.identifying_fans.pop(fan_id, None)
                logger.info(f"Stopped identify mode for fan '{fan_id}'")

    def read_temperature(self, device_pattern, channel):
        """Reads temperature from sysfs in Celsius. Caches last reading as safety fallback."""
        path = self.resolve_device_path(device_pattern)
        if not path:
            logger.warning(f"Temperature device not found matching pattern '{device_pattern}'")
            return self.last_temps.get((device_pattern, channel), None)

        temp_file = os.path.join(path, f"temp{channel}_input")
        if not os.path.exists(temp_file):
            logger.warning(f"Temperature file {temp_file} does not exist")
            return self.last_temps.get((device_pattern, channel), None)

        try:
            with open(temp_file, "r") as f:
                val = float(f.read().strip())
                temp_c = val / 1000.0
                self.last_temps[(device_pattern, channel)] = temp_c
                return temp_c
        except Exception as e:
            logger.error(f"Error reading temperature from {temp_file}: {e}")
            return self.last_temps.get((device_pattern, channel), None)

    def read_fan_rpm(self, device_pattern, channel):
        """Reads fan speed in RPM."""
        path = self.resolve_device_path(device_pattern)
        if not path:
            return 0

        fan_file = os.path.join(path, f"fan{channel}_input")
        if not os.path.exists(fan_file):
            return 0

        try:
            with open(fan_file, "r") as f:
                return int(f.read().strip())
        except Exception as e:
            logger.debug(f"Error reading fan RPM from {fan_file}: {e}")
            return 0

    def enable_manual_control(self, device_path, channel):
        """Ensures that the PWM control mode is set to manual (1)."""
        enable_file = os.path.join(device_path, f"pwm{channel}_enable")
        if not os.path.exists(enable_file):
            return True # Not all drivers expose pwmX_enable; assume manual works

        try:
            # Avoid writing if it is already 1
            with open(enable_file, "r") as f:
                current_mode = f.read().strip()
                if current_mode == "1":
                    return True
            
            with open(enable_file, "w") as f:
                f.write("1")
                logger.info(f"Set manual control mode (1) for {enable_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable manual control for channel {channel} at {device_path}: {e}")
            return False

    def write_pwm(self, device_pattern, channel, percentage):
        """Sets the PWM output (0-100%) to sysfs."""
        path = self.resolve_device_path(device_pattern)
        if not path:
            return False, f"Device matching '{device_pattern}' not found"

        # Make sure control is in manual mode
        if not self.enable_manual_control(path, channel):
            return False, f"Could not set manual control enable for pwm{channel}"

        pwm_file = os.path.join(path, f"pwm{channel}")
        if not os.path.exists(pwm_file):
            return False, f"PWM control file {pwm_file} does not exist"

        # Convert percentage (0-100) to raw value (0-255)
        raw_val = int(round(max(0, min(100, percentage)) * 2.55))

        try:
            with open(pwm_file, "w") as f:
                f.write(str(raw_val))
            return True, None
        except Exception as e:
            err_msg = f"Failed to write raw PWM value {raw_val} to {pwm_file}: {e}"
            logger.error(err_msg)
            return False, err_msg

    @staticmethod
    def interpolate_curve(temp, curve):
        """Linearly interpolates PWM percent from temperature curve coordinates."""
        if not curve:
            return 100.0 # Safety default
            
        # Ensure the curve points are sorted by temperature
        sorted_curve = sorted(curve, key=lambda x: x[0])
        
        # Guard underflow
        if temp <= sorted_curve[0][0]:
            return float(sorted_curve[0][1])
            
        # Guard overflow
        if temp >= sorted_curve[-1][0]:
            return float(sorted_curve[-1][1])
            
        # Interpolate between intermediate points
        for i in range(len(sorted_curve) - 1):
            t1, p1 = sorted_curve[i]
            t2, p2 = sorted_curve[i + 1]
            if t1 <= temp <= t2:
                # Linear interpolation formula
                p_val = p1 + (p2 - p1) * (temp - t1) / (t2 - t1)
                return float(p_val)
                
        return 100.0 # Fallback

    def update_loop(self):
        """Main background thread loop evaluating configurations and adjusting speeds."""
        logger.info("Fan control loop background thread started.")
        scan_counter = 0

        while True:
            try:
                # 0. Prune expired identifying fans
                now_time = time.time()
                with self.lock:
                    expired = [fid for fid, expire in self.identifying_fans.items() if now_time > expire]
                    for fid in expired:
                        self.identifying_fans.pop(fid, None)
                        logger.info(f"Identify mode for fan '{fid}' expired. Returning to normal curves.")

                # 1. Periodically rescan paths (every 30 seconds) to adapt to hotplugs
                scan_counter += 1
                if scan_counter >= 30:
                    self.scan_devices()
                    scan_counter = 0

                # 2. Fetch configurations
                config = self.config_manager.get_config()
                active_profile_name = config.get("active_profile", "Standard")
                profile = config.get("profiles", {}).get(active_profile_name, {})
                fan_definitions = config.get("fans", {})
                interval = config.get("refresh_interval_seconds", 1.0)

                # Collect all active temperatures to expose to UI
                system_temps = {}
                # Extract temperature sources from config
                temp_sources = set()
                for fan_prof in profile.values():
                    if fan_prof.get("mode") == "curve":
                        temp_sources.add((fan_prof.get("temp_device_name"), fan_prof.get("temp_channel")))

                # Always read CPU and GPU temps by default as dashboard info
                temp_sources.add(("k10temp", 1)) # CPU Tctl
                temp_sources.add(("kraken2023", 1)) # Coolant
                temp_sources.add(("amdgpu", 1)) # GPU Edge
                temp_sources.add(("amdgpu", 2)) # GPU Junction

                for device, chan in temp_sources:
                    t = self.read_temperature(device, chan)
                    if t is not None:
                        system_temps[f"{device}_temp{chan}"] = t

                current_fan_status = {}

                # 3. For each configured fan, determine speed and write PWM
                for fan_id, fan_def in fan_definitions.items():
                    label = fan_def.get("label", fan_id)
                    dev_name = fan_def.get("device_name")
                    pwm_chan = fan_def.get("pwm_channel")
                    fan_chan = fan_def.get("fan_channel")

                    # Read current speed RPM
                    rpm = self.read_fan_rpm(dev_name, fan_chan)

                    # Determine control settings from current profile
                    fan_profile = profile.get(fan_id, {})
                    mode = fan_profile.get("mode", "curve")
                    manual_val = fan_profile.get("manual_value", 50)
                    
                    target_pwm = 50.0
                    error_msg = None

                    if mode == "manual":
                        target_pwm = float(manual_val)
                    else:
                        # Auto / Curve mode
                        temp_dev = fan_profile.get("temp_device_name")
                        temp_chan = fan_profile.get("temp_channel")
                        curve = fan_profile.get("curve")

                        current_temp = system_temps.get(f"{temp_dev}_temp{temp_chan}")
                        if current_temp is None:
                            # Safety default if temperature reading fails
                            target_pwm = 100.0
                            error_msg = f"Temperature sensor {temp_dev}_temp{temp_chan} unavailable. Fan set to 100% safety default."
                            logger.error(error_msg)
                        else:
                            target_pwm = self.interpolate_curve(current_temp, curve)

                    # Check if fan finder is active for this fan
                    is_identifying = False
                    with self.lock:
                        if fan_id in self.identifying_fans:
                            is_identifying = True
                            target_pwm = 100.0  # Force max speed!

                    # Enforce bounds
                    target_pwm = max(0.0, min(100.0, target_pwm))

                    # Apply control action
                    success, write_err = self.write_pwm(dev_name, pwm_chan, target_pwm)
                    if not success:
                        error_msg = write_err

                    current_fan_status[fan_id] = {
                        "label": label,
                        "device_name": dev_name,
                        "resolved_path": self.resolve_device_path(dev_name),
                        "pwm_channel": pwm_chan,
                        "fan_channel": fan_chan,
                        "mode": mode,
                        "rpm": rpm,
                        "target_pwm": round(target_pwm, 1),
                        "is_identifying": is_identifying,
                        "error": error_msg
                    }

                # Update the shared status state atomically
                with self.lock:
                    self.status = {
                        "timestamp": time.time(),
                        "temperatures": system_temps,
                        "fans": current_fan_status,
                        "active_profile": active_profile_name
                    }

                # Sleep until next control tick
                time.sleep(interval)

            except Exception as e:
                logger.critical(f"Critical error in fan control loop thread: {e}", exc_info=True)
                time.sleep(2)  # Prevent tight error loops

    def get_status(self):
        """Returns the latest atomically stored status."""
        with self.lock:
            return self.status.copy()
