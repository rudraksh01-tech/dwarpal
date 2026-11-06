"""Wait for the Groq free-tier daily token quota, then record the missing runs and run the evaluation.

    python -m eval.finish_when_quota

Groq's free tier allows 200,000 tokens a day per model on a rolling
24-hour window. This script checks every 20 minutes and, once there is
room, records the playground runs that are still missing and then runs
`eval.run_eval 5`. Progress goes to eval/finish.log.
"""

import logging
import subprocess
import sys
import time
from datetime import datetime

from dwarpal import config
from dwarpal.checks.guards import groq_client


LOG = config.PROJECT_ROOT / "eval" / "finish.log"
RECORDINGS = config.PROJECT_ROOT / "frontend" / "public" / "recordings"
WANTED = ["clean", "rug_pull", "result_injection", "service_notice", "shadowing", "polite_poisoning__original"]
CHECK_EVERY_S = 20 * 60


def log(message):
    line = f"{datetime.now():%Y-%m-%d %H:%M} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def quota_free(tokens_needed=40_000):
    """True when a request of about tokens_needed would fit today's quota."""
    try:
        groq_client().chat.completions.create(
            model=config.GROQ_MODEL, messages=[{"role": "user", "content": "x" * 200}], max_tokens=1,
        )
    except Exception as error:
        log(f"not yet: {str(error)[:140]}")
        return False

    return True


def run(*args):
    log("running: " + " ".join(args))
    result = subprocess.run([sys.executable, "-W", "ignore", "-m", *args], cwd=config.PROJECT_ROOT)
    log(f"exit code {result.returncode}")
    return result.returncode


def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # The recordings that already exist from earlier sessions are not redone
    missing = [name for name in WANTED if name != "clean" and not (RECORDINGS / f"{name}.json").exists()]
    missing = ["clean"] + missing   # clean was recorded with the old Hinglish question; redo it in English
    log(f"waiting for quota; will record {missing} and then evaluate")

    while not quota_free():
        time.sleep(CHECK_EVERY_S)

    for name in missing:
        while run("demo.record", name) != 0:
            log("recording failed (probably the quota again); waiting")
            time.sleep(CHECK_EVERY_S)

    while not quota_free():
        time.sleep(CHECK_EVERY_S)

    run("eval.run_eval", "5")
    log("done")


if __name__ == "__main__":
    main()
