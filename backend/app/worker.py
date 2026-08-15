import argparse
import logging
import time

from app.core.config import settings
from app.core.logging import configure_logging
from app.db import SessionLocal
from app.operations_service import process_due_jobs


def run_once()->dict:
    with SessionLocal() as db: return process_due_jobs(db,settings.worker_batch_size)


def main():
    parser=argparse.ArgumentParser(description="LETTER durable job worker");parser.add_argument("--once",action="store_true");args=parser.parse_args()
    configure_logging(settings.log_level);logger=logging.getLogger("letter.worker")
    while True:
        try:
            result=run_once();logger.info("worker_cycle",extra=result)
        except Exception: logger.exception("worker_cycle_failed")
        if args.once: break
        time.sleep(settings.worker_poll_seconds)


if __name__=="__main__": main()
