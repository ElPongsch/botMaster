"""botMaster v2.0 - Main entry point"""
import logging
import sys
from botmaster import load_settings, Orchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("botmaster.log")
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for botMaster orchestrator"""
    logger.info("Starting botMaster v2.0 Orchestrator...")

    # Load settings
    settings = load_settings()
    logger.info(f"Loaded settings (data_dir: {settings.data_dir})")

    # Initialize orchestrator
    orchestrator = Orchestrator(settings)

    # Start Telegram bot if enabled
    if settings.enable_telegram_polling:
        logger.info("Starting Telegram bot interface...")
        try:
            orchestrator.start_telegram_bot()
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
        finally:
            orchestrator.cleanup()
    else:
        logger.info("Telegram polling disabled - running in manual mode")
        logger.info("Orchestrator ready. Use Python API to interact.")

        # Example: Process a request programmatically
        # response = orchestrator.process_request("What is 2+2?")
        # print(response)


if __name__ == "__main__":
    main()
