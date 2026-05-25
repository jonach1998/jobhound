from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv
from jobhound.app import JobHoundApp

APP_DIR = Path(__file__).resolve().parent
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s | %(message)s"


def main() -> None:
    parser = argparse.ArgumentParser(description="JobHound — automated job hunter")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run all profiles once and exit (useful for Cloud)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    logging.getLogger("JobSpy").setLevel(logging.WARNING)
    load_dotenv(APP_DIR.parent / ".env")

    app = JobHoundApp.from_env(APP_DIR)
    if args.once:
        app.run_profiles_once()
    else:
        app.start()


if __name__ == "__main__":
    main()
