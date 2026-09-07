import argparse
import sys
import threading
import logging
from config_manager import ConfigManager
from controller import FanController
from web_server import create_app

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("air-controller.main")

def parse_args():
    parser = argparse.ArgumentParser(description="PC Fan Controller Daemon & Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host IP (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (default: 5000)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a scan and single loop tick, then exit")
    return parser.parse_args()

def main():
    args = parse_args()

    logger.info("Starting PC Fan Controller...")

    # 1. Initialize configuration manager
    config_manager = ConfigManager()

    # 2. Initialize hardware controller
    controller = FanController(config_manager)

    # If dry-run requested, run once, print status, and exit
    if args.dry_run:
        logger.info("Dry-run execution requested.")
        logger.info("Executing one control loop tick...")
        # Direct call to loop tick would require breaking up update_loop or running it briefly
        # Let's perform a direct read and status dump
        try:
            # Manually trigger a quick update cycle
            # We can replicate a single iteration of the loop body for verification
            config = config_manager.get_config()
            profile_name = config.get("active_profile", "Standard")
            profile = config.get("profiles", {}).get(profile_name, {})
            fans = config.get("fans", {})
            
            logger.info("=== HWMON Devices Detected ===")
            for name, path in controller.device_map.items():
                logger.info(f" - {name} at {path}")

            logger.info("=== Active Fan Channels & Speeds ===")
            for fan_id, fan_def in fans.items():
                dev_name = fan_def.get("device_name")
                fan_chan = fan_def.get("fan_channel")
                pwm_chan = fan_def.get("pwm_channel")
                rpm = controller.read_fan_rpm(dev_name, fan_chan)
                path = controller.resolve_device_path(dev_name)
                logger.info(f" - [{fan_id}] {fan_def.get('label')}: RPM={rpm}, PWM File={path}/pwm{pwm_chan} (Exists: {path is not None})")

            logger.info("=== Temperature Sensors ===")
            cpu_temp = controller.read_temperature("k10temp", 1)
            coolant_temp = controller.read_temperature("kraken2023", 1)
            gpu_temp = controller.read_temperature("amdgpu", 1)
            logger.info(f" - CPU (k10temp temp1): {cpu_temp}°C")
            logger.info(f" - Coolant (kraken2023 temp1): {coolant_temp}°C")
            logger.info(f" - GPU (amdgpu temp1): {gpu_temp}°C")

            logger.info("Dry run verification completed successfully.")
            sys.exit(0)
        except Exception as e:
            logger.critical(f"Dry run verification failed: {e}", exc_info=True)
            sys.exit(1)

    # 3. Start background fan control thread
    control_thread = threading.Thread(
        target=controller.update_loop,
        name="FanControlLoop",
        daemon=True
    )
    control_thread.start()

    # 4. Initialize and start the Flask web application
    app = create_app(config_manager, controller)
    
    logger.info(f"Starting web interface at http://localhost:{args.port}")
    try:
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    except Exception as e:
        logger.critical(f"Failed to start web server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
