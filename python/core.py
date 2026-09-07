import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
import atexit
import os
from threading import Lock

from .hardware import Sensor, Fan, find_sensors, find_fans

logger = logging.getLogger(__name__)


class FanController:
    """Main fan controller class that manages hardware monitoring and fan speed control."""
    
    def __init__(self, config_path: Path, status_path: Path):
        self.config_path = config_path
        self.status_path = status_path
        self.config: Dict = {}
        self.sensors: Dict[str, Sensor] = {}
        self.fans: Dict[str, Fan] = {}
        self.last_speeds: Dict[str, float] = {}
        self._status_lock = Lock()
        self.status = {
            "pid": os.getpid(),
            "status": "starting",
            "sensors": {},
            "fans": {},
        }
        atexit.register(self._cleanup_status)

    def _cleanup_status(self):
        if self.status_path.exists():
            self.status_path.unlink()

    def load_config(self) -> bool:
        if not self.config_path.exists():
            logger.error(f"Config file not found at {self.config_path}")
            self.status["status"] = "error"
            self.status["error_message"] = "config.json not found"
            self._write_status()
            return False
        
        with open(self.config_path, "r") as f:
            self.config = json.load(f)

        # Convert old single sensor format to new multi-sensor format if necessary
        for curve_name, curve_data in self.config.get("curves", {}).items():
            if isinstance(curve_data.get("sensor"), str):
                curve_data["sensor"] = {
                    "function": "single", # Use "single" as a pseudo-function for single sensor curves
                    "paths": [curve_data["sensor"]]
                }
            elif not isinstance(curve_data.get("sensor"), dict) or "function" not in curve_data["sensor"] or "paths" not in curve_data["sensor"]:
                logger.error(f"Invalid sensor configuration for curve '{curve_name}'. Skipping.")
                curve_data["sensor"] = {"function": "single", "paths": []} # Default to empty
        
        # Save the converted config back to file
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

        return True

    def _write_status(self):
        """Write status to file with thread safety."""
        with self._status_lock:
            try:
                with open(self.status_path, "w") as f:
                    json.dump(self.status, f, indent=2)
            except OSError as e:
                logger.error(f"Failed to write status file: {e}")

    def discover_hardware(self):
        self.sensors = find_sensors()
        self.fans = find_fans()
        logger.info(f"Found {len(self.sensors)} sensors and {len(self.fans)} fans")

    def calculate_fan_speed(self, temp: float, points: List[Tuple[float, float]]) -> float:
        """Calculate fan speed based on temperature using linear interpolation.
        
        Args:
            temp: Current temperature in Celsius
            points: List of (temperature, speed) tuples defining the curve
            
        Returns:
            Fan speed percentage (0-100)
        """
        if not points:
            return 0.0
        
        points = sorted(points)
        
        # Handle edge cases
        if temp <= points[0][0]:
            return points[0][1]
        if temp >= points[-1][0]:
            return points[-1][1]
        
        temps = [p[0] for p in points]
        speeds = [p[1] for p in points]
        return float(np.interp(temp, temps, speeds))

    def smooth_speed(self, target_speed: float, fan_path: str, step: float = 10.0) -> float:
        """Smooth fan speed changes to prevent sudden jumps.
        
        Args:
            target_speed: Desired fan speed percentage
            fan_path: Path identifier for the fan
            step: Maximum speed change per iteration (default: 10%)
            
        Returns:
            Smoothed fan speed percentage
        """
        last_speed = self.last_speeds.get(fan_path, target_speed)
        
        # Clamp target speed to valid range
        target_speed = max(0.0, min(100.0, target_speed))
        
        if target_speed > last_speed + step:
            return last_speed + step
        elif target_speed < last_speed - step:
            return last_speed - step
        return target_speed

    def run_single_loop(self):
        """Executes a single iteration of the fan control loop.
        
        Reads sensor temperatures, calculates fan speeds based on configured curves,
        applies smoothing, and updates fan speeds.
        """
        # Read all sensor temperatures
        for sensor_path, sensor in self.sensors.items():
            try:
                temp = sensor.read_temp()
                self.status["sensors"][sensor_path] = temp
            except Exception as e:
                logger.error(f"Error reading sensor {sensor_path}: {e}")
                self.status["sensors"][sensor_path] = None

        # Apply fan curves
        curves = self.config.get("curves", {})
        fan_assignments = self.config.get("fans", {})

        for fan_path, fan in self.fans.items():
            curve_name = fan_assignments.get(fan_path)
            
            if not curve_name:
                continue
            
            if curve_name not in curves:
                logger.warning(f"Curve '{curve_name}' not found for fan '{fan_path}'")
                continue

            curve = curves[curve_name]
            sensor_config = curve.get("sensor", {})
            points = curve.get("points", [])

            if not points:
                logger.warning(f"No points defined for curve '{curve_name}'. Skipping fan control.")
                continue

            aggregation_function = sensor_config.get("function")
            sensor_paths_for_curve = sensor_config.get("paths", [])

            if not aggregation_function or not sensor_paths_for_curve:
                # Only log error once per curve, not every loop iteration
                if curve_name not in getattr(self, '_invalid_curves_logged', set()):
                    logger.error(f"Invalid sensor configuration for curve '{curve_name}'. Skipping fan control.")
                    if not hasattr(self, '_invalid_curves_logged'):
                        self._invalid_curves_logged = set()
                    self._invalid_curves_logged.add(curve_name)
                continue

            current_temps = []
            for s_path in sensor_paths_for_curve:
                temp = self.status["sensors"].get(s_path)
                if temp is not None:
                    current_temps.append(temp)
                else:
                    logger.debug(f"Sensor '{s_path}' for curve '{curve_name}' not providing data or not found.")

            if not current_temps:
                logger.warning(f"No valid sensor data for curve '{curve_name}'. Skipping fan control.")
                continue

            effective_temp: Optional[float] = None
            if aggregation_function == "max":
                effective_temp = max(current_temps)
            elif aggregation_function == "min":
                effective_temp = min(current_temps)
            elif aggregation_function == "average":
                effective_temp = sum(current_temps) / len(current_temps)
            elif aggregation_function == "single":
                effective_temp = current_temps[0] if current_temps else None
            else:
                logger.error(f"Unknown aggregation function '{aggregation_function}' for curve '{curve_name}'. Skipping.")
                continue

            if effective_temp is None:
                logger.warning(f"Effective temperature could not be determined for curve '{curve_name}'. Skipping.")
                continue

            target_speed = self.calculate_fan_speed(effective_temp, points)
            smooth_speed = self.smooth_speed(target_speed, fan_path)
            self.last_speeds[fan_path] = smooth_speed

            try:
                fan.set_speed(smooth_speed)
            except Exception as e:
                logger.error(f"Failed to set speed for fan {fan_path}: {e}")
            
            # Update status with detailed info for the GUI
            self.status["fans"][fan_path] = {
                "speed": smooth_speed,
                "curve": curve_name,
                "effective_temp": effective_temp,
            }
            logger.debug(f"Fan {fan_path}: Temp {effective_temp:.1f}°C -> Speed {smooth_speed:.1f}%")

        self._write_status()

    def run(self):
        if not self.load_config():
            return

        self.discover_hardware()
        
        # Apply min speed for NVIDIA fan if configured
        nvidia_min_speed = self.config.get("hardware", {}).get("nvidia_min_fan_speed", 26)
        if "nvidia-settings" in self.fans:
            from .hardware import NvidiaFan
            if isinstance(self.fans["nvidia-settings"], NvidiaFan):
                self.fans["nvidia-settings"].min_speed = nvidia_min_speed

        self.status["status"] = "running"
        self._write_status()

        try:
            while True:
                self.run_single_loop()
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Fan controller stopped by user")
        except Exception as e:
            logger.error(f"Unhandled exception: {e}", exc_info=True)
            self.status["status"] = "error"
            self.status["error_message"] = str(e)
            self._write_status()
        finally:
            logger.info("Stopping fan controller.")
            self._cleanup_status()
