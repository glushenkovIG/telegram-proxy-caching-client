import pytest
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Running tests...")
    # Run pytest with verbosity
    exit_code = pytest.main(["-v", "tests/"])
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
