import os
import json
import logging
from threading import Lock

logger = logging.getLogger("air-controller.config")

class ConfigManager:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.lock = Lock()
        self.config = {}
        self.load()

    def load(self):
        """Loads configuration from file. Fallbacks to default empty structures if missing."""
        with self.lock:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file {self.config_path} not found. Initializing empty config.")
                self.config = {
                    "refresh_interval_seconds": 1.0,
                    "active_profile": "Standard",
                    "profiles": {},
                    "fans": {}
                }
                return
            
            try:
                with open(self.config_path, "r") as f:
                    self.config = json.load(f)
                    logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to parse config file {self.config_path}: {e}")
                # Keep existing config or init defaults if empty
                if not self.config:
                    self.config = {}

    def get_config(self):
        """Returns a snapshot copy of the current configuration."""
        with self.lock:
            # Simple deep copy using json dump/load to prevent mutation outside manager
            return json.loads(json.dumps(self.config))

    def save(self, new_config):
        """Atomically saves the config to file and updates memory."""
        with self.lock:
            self.config = new_config
            try:
                # Write to a temp file first then rename to ensure atomicity
                temp_path = self.config_path + ".tmp"
                with open(temp_path, "w") as f:
                    json.dump(self.config, f, indent=2)
                os.replace(temp_path, self.config_path)
                logger.info(f"Saved configuration to {self.config_path}")
                return True
            except Exception as e:
                logger.error(f"Error saving config file to {self.config_path}: {e}")
                return False
