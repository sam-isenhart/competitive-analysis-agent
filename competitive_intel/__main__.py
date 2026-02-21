"""Allow `python -m competitive_intel` to run the pipeline."""

import asyncio
import sys

from competitive_intel.main import main

sys.exit(asyncio.run(main()))
