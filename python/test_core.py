"""Tests for the core.py module."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json
from typing import Dict, List, Tuple, Optional
import os # Added for os.getpid() in mock

from fan_controller.core import FanController
from fan_controller.hardware import Sensor, Fan # Added Sensor, Fan imports


class MockSensor(Sensor):
    """A mock sensor for testing purposes."""
    def __init__(self, path: str, name: str, temp_value: Optional[float]):
        super().__init__(path, name)
        self._temp_value = temp_value

    def read_temp(self) -> Optional[float]:
        return self._temp_value


class MockFan(Fan):
    """A mock fan for testing purposes."""
    def __init__(self, path: str, name: str):
        super().__init__(path, name)
        self.speed_set = -1.0 # To track if set_speed was called

    def set_speed(self, speed: float):
        self.speed_set = speed

class TestFanController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "config.json"
        self.status_path = Path(self.test_dir) / "status.json"
        
        # Create a basic config (will be overwritten by specific tests)
        self.config = {
            "curves": {
                "test_curve_single": {
                    "sensor": {"function": "single", "paths": ["/sys/test/temp1_input"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "test_fan_single": "test_curve_single"
            },
            "aliases": {},
            "hidden_fans": [],
            "hidden_sensors": []
        }
        
        with open(self.config_path, "w") as f:
            json.dump(self.config, f)

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_load_config_and_single_sensor_conversion(self, mock_find_fans, mock_find_sensors):
        """Test configuration loading, including old single sensor format conversion."""
        # Test old format conversion
        old_config = {
            "curves": {
                "old_curve": {
                    "sensor": "/sys/old/temp_input",
                    "points": [[0,0], [100,100]]
                }
            },
            "fans": {}, "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(old_config)
        self.assertIn("old_curve", controller.config["curves"])
        self.assertEqual(controller.config["curves"]["old_curve"]["sensor"]["function"], "single")
        self.assertEqual(controller.config["curves"]["old_curve"]["sensor"]["paths"], ["/sys/old/temp_input"])

        # Test new format loading
        new_config = {
            "curves": {
                "new_curve": {
                    "sensor": {"function": "max", "paths": ["/sys/new/temp1", "/sys/new/temp2"]},
                    "points": [[0,0], [100,100]]
                }
            },
            "fans": {}, "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(new_config)
        self.assertIn("new_curve", controller.config["curves"])
        self.assertEqual(controller.config["curves"]["new_curve"]["sensor"]["function"], "max")
        self.assertEqual(controller.config["curves"]["new_curve"]["sensor"]["paths"], ["/sys/new/temp1", "/sys/new/temp2"])

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_multi_sensor_aggregation_max(self, mock_find_fans, mock_find_sensors):
        """Test fan speed calculation with max aggregation."""
        test_config = {
            "curves": {
                "max_curve": {
                    "sensor": {"function": "max", "paths": ["/sys/s1", "/sys/s2", "/sys/s3"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "fan1": "max_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {
            "/sys/s1": MockSensor("/sys/s1", "Sensor1", 30.0),
            "/sys/s2": MockSensor("/sys/s2", "Sensor2", 50.0),
            "/sys/s3": MockSensor("/sys/s3", "Sensor3", 40.0),
        }
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        mock_fan = controller.fans["fan1"]
        self.assertAlmostEqual(mock_fan.speed_set, 75.0, delta=0.1) # Max temp is 50, speed should be 75

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_multi_sensor_aggregation_min(self, mock_find_fans, mock_find_sensors):
        """Test fan speed calculation with min aggregation."""
        test_config = {
            "curves": {
                "min_curve": {
                    "sensor": {"function": "min", "paths": ["/sys/s1", "/sys/s2", "/sys/s3"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "fan1": "min_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {
            "/sys/s1": MockSensor("/sys/s1", "Sensor1", 30.0),
            "/sys/s2": MockSensor("/sys/s2", "Sensor2", 50.0),
            "/sys/s3": MockSensor("/sys/s3", "Sensor3", 40.0),
        }
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        mock_fan = controller.fans["fan1"]
        self.assertAlmostEqual(mock_fan.speed_set, 25.0, delta=0.1) # Min temp is 30, speed should be 25

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_multi_sensor_aggregation_average(self, mock_find_fans, mock_find_sensors):
        """Test fan speed calculation with average aggregation."""
        test_config = {
            "curves": {
                "avg_curve": {
                    "sensor": {"function": "average", "paths": ["/sys/s1", "/sys/s2", "/sys/s3"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "fan1": "avg_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {
            "/sys/s1": MockSensor("/sys/s1", "Sensor1", 30.0),
            "/sys/s2": MockSensor("/sys/s2", "Sensor2", 50.0),
            "/sys/s3": MockSensor("/sys/s3", "Sensor3", 40.0),
        }
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        mock_fan = controller.fans["fan1"]
        # Average temp is (30+50+40)/3 = 40, speed should be 50
        self.assertAlmostEqual(mock_fan.speed_set, 50.0, delta=0.1)

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_multi_sensor_aggregation_single(self, mock_find_fans, mock_find_sensors):
        """Test fan speed calculation with single aggregation (original behavior)."""
        test_config = {
            "curves": {
                "single_curve": {
                    "sensor": {"function": "single", "paths": ["/sys/s1"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "fan1": "single_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {
            "/sys/s1": MockSensor("/sys/s1", "Sensor1", 45.0),
        }
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        mock_fan = controller.fans["fan1"]
        # Temp is 45, speed should be 62.5
        self.assertAlmostEqual(controller.calculate_fan_speed(45, test_config["curves"]["single_curve"]["points"]), 62.5, delta=0.1)
        self.assertAlmostEqual(mock_fan.speed_set, 62.5, delta=0.1)

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_multi_sensor_missing_data(self, mock_find_fans, mock_find_sensors):
        """Test handling of missing sensor data for aggregation."""
        test_config = {
            "curves": {
                "max_curve": {
                    "sensor": {"function": "max", "paths": ["/sys/s1", "/sys/s2"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "fan1": "max_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {
            "/sys/s1": MockSensor("/sys/s1", "Sensor1", None), # Missing data
            "/sys/s2": MockSensor("/sys/s2", "Sensor2", 40.0),
        }
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        mock_fan = controller.fans["fan1"]
        self.assertAlmostEqual(mock_fan.speed_set, 50.0, delta=0.1) # Only 40.0 is valid, so max is 40.0, speed 50

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_multi_sensor_no_valid_data(self, mock_find_fans, mock_find_sensors):
        """Test handling when no valid sensor data is available for aggregation."""
        test_config = {
            "curves": {
                "avg_curve": {
                    "sensor": {"function": "average", "paths": ["/sys/s1", "/sys/s2"]},
                    "points": [[20, 0], [40, 50], [60, 100]]
                }
            },
            "fans": {
                "fan1": "avg_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {
            "/sys/s1": MockSensor("/sys/s1", "Sensor1", None),
            "/sys/s2": MockSensor("/sys/s2", "Sensor2", None),
        }
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        mock_fan = controller.fans["fan1"]
        self.assertEqual(mock_fan.speed_set, -1.0) # set_speed should not be called if no valid data

    def test_calculate_fan_speed(self):
        """Test fan speed calculation from curve."""
        controller = FanController(self.config_path, self.status_path)
        points = [[20, 0], [40, 50], [60, 100]]
        
        # Test exact points
        self.assertEqual(controller.calculate_fan_speed(20, points), 0)
        self.assertEqual(controller.calculate_fan_speed(40, points), 50)
        self.assertEqual(controller.calculate_fan_speed(60, points), 100)
        
        # Test interpolation
        self.assertAlmostEqual(controller.calculate_fan_speed(30, points), 25, delta=0.1)
        self.assertAlmostEqual(controller.calculate_fan_speed(50, points), 75, delta=0.1)

    @patch('fan_controller.core.find_sensors')
    @patch('fan_controller.core.find_fans')
    def test_status_file_format(self, mock_find_fans, mock_find_sensors):
        """Test that the status file is written with the correct format."""
        test_config = {
            "curves": {
                "test_curve": {
                    "sensor": {"function": "max", "paths": ["/sys/s1"]},
                    "points": [[20, 0], [60, 100]]
                }
            },
            "fans": {
                "fan1": "test_curve"
            },
            "aliases": {}, "hidden_fans": [], "hidden_sensors": []
        }
        controller = self._create_controller_with_config(test_config)

        mock_find_sensors.return_value = {"/sys/s1": MockSensor("/sys/s1", "Sensor1", 40.0)}
        mock_find_fans.return_value = {"fan1": MockFan("fan1", "Fan1")}

        controller.discover_hardware()
        controller.run_single_loop()

        with open(self.status_path, "r") as f:
            status_data = json.load(f)

        self.assertIn("fans", status_data)
        self.assertIn("fan1", status_data["fans"])
        
        fan_status = status_data["fans"]["fan1"]
        self.assertIn("speed", fan_status)
        self.assertIn("curve", fan_status)
        self.assertIn("effective_temp", fan_status)
        
        self.assertAlmostEqual(fan_status["speed"], 50.0, delta=0.1)
        self.assertEqual(fan_status["curve"], "test_curve")
        self.assertAlmostEqual(fan_status["effective_temp"], 40.0, delta=0.1)

    def test_smooth_speed(self):
        """Test speed smoothing."""
        controller = FanController(self.config_path, self.status_path)
        fan_path = "test_fan"
        
        # Initial speed
        smooth = controller.smooth_speed(50, fan_path, step=10)
        self.assertEqual(smooth, 50)  # First call, no smoothing
        
        # Gradual increase
        controller.last_speeds[fan_path] = 50
        smooth = controller.smooth_speed(80, fan_path, step=10)
        self.assertEqual(smooth, 60)  # Limited by step
        
        # Gradual decrease
        controller.last_speeds[fan_path] = 80
        smooth = controller.smooth_speed(50, fan_path, step=10)
        self.assertEqual(smooth, 70)  # Limited by step

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir)

    def _create_controller_with_config(self, config_data: Dict):
        """Helper to create a controller instance with specific config."""
        with open(self.config_path, "w") as f:
            json.dump(config_data, f)
        controller = FanController(self.config_path, self.status_path)
        self.assertTrue(controller.load_config())
        return controller


if __name__ == "__main__":
    unittest.main()
