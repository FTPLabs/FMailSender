#!/usr/bin/env python3
"""
Replit Credit Monitor — авто-коммит изменений.
Запуск: python credit_monitor.py &
"""
import os, time, subprocess, sys
from datetime import datetime

CHECK_INTERVAL = 300
AUTO_COMMIT_INTERVAL = 1800

def do_commit(reason="checkpoint"):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    msg = f"auto-commit [{ts}] {reason}"
    cmds = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", msg, "--allow-empty"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if "nothing to commit" in (r.stdout + r.stderr):
            print(f"[monitor] Nothing to commit at {ts}")
            return True
        if r.returncode != 0 and "nothing" not in r.stderr:
            print(f"[monitor] {' '.join(cmd)} error: {r.stderr[:100]}")
            return False
    print(f"[monitor] Committed: {msg}")
    return True

def main():
    print("[monitor] Started. Interval:", AUTO_COMMIT_INTERVAL, "s")
    do_commit("startup")
    last_commit = time.time()
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            if time.time() - last_commit >= AUTO_COMMIT_INTERVAL:
                do_commit("periodic checkpoint")
                last_commit = time.time()
        except KeyboardInterrupt:
            do_commit("shutdown")
            break
        except Exception as e:
            print(f"[monitor] Error: {e}")

if __name__ == "__main__":
    main()
