#!/usr/bin/env -S python3 -u
import os
import json
import time
import socket
import subprocess
import pyinotify
import requests

CACHE_FILE = "/tmp/news_cache.json"
WATCH_DIR = "/var/lib/pacman/"
PACMAN_LOCK = WATCH_DIR + "db.lck"

RETRY_DELAY = 10
NORMAL_DELAY = 1800
MAX_RETRIES = 20
WATCHDOG_TIMEOUT = 5

MUTEX_LOCK = False


def has_internet() -> bool:
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("9.9.9.9", 53))
        return True
    except Exception:
        return False


def run_command(cmd):
    for _ in range(MAX_RETRIES):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: os.nice(20),
            )
            stdout, _ = proc.communicate(timeout=WATCHDOG_TIMEOUT)
            lines = stdout.decode().strip().splitlines()
            return [l for l in lines if l]
        except Exception:
            time.sleep(1)
    return None


def get_updates():
    return len(run_command(["checkupdates"]) or [])


def get_devel_updates():
    dat = run_command(["yay", "-Qua", "--devel"])
    if dat:
        dat = dat[1:]
    return len(dat or [])


def fetch_news():
    try:
        response = requests.get(
            "https://raw.githubusercontent.com/BredOS/news/refs/heads/main/notice.txt",
            timeout=5,
        )
        response.raise_for_status()
        return response.text
    except:
        return False


def write_cache(updates, devel_updates, news) -> None:
    payload = {
        "updates": updates,
        "devel_updates": devel_updates,
        "news": news,
        "timestamp": int(time.time()),
    }
    try:
        tmp = CACHE_FILE + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        os.rename(tmp, CACHE_FILE)
        print(f'Cache updated. (Timestamp: {payload["timestamp"]})')
    except Exception:
        print("Failed")


def wait_for_unlock() -> None:
    print("Detected pacman db lock, waiting")
    while os.path.exists(PACMAN_LOCK):
        time.sleep(1)


def check_and_update() -> bool:
    global MUTEX_LOCK
    if MUTEX_LOCK:
        return False
    MUTEX_LOCK = True
    if not has_internet():
        MUTEX_LOCK = False
        return False
    print("Update check triggered")
    updates = get_updates()
    devel = get_devel_updates()
    news = fetch_news()
    if updates is None and devel is None:
        MUTEX_LOCK = False
        return False
    write_cache(updates, devel, news)
    MUTEX_LOCK = False
    return True


def run_periodic() -> None:
    while True:
        ok = check_and_update()
        time.sleep(RETRY_DELAY if not ok and not has_internet() else NORMAL_DELAY)


class Handler(pyinotify.ProcessEvent):
    def process_IN_CLOSE_WRITE(self, event):
        wait_for_unlock()
        check_and_update()

    def process_IN_MOVED_TO(self, event):
        wait_for_unlock()
        check_and_update()


def run_watcher() -> pyinotify.ThreadedNotifier:
    wm = pyinotify.WatchManager()
    notifier = pyinotify.ThreadedNotifier(wm, Handler())
    wm.add_watch(WATCH_DIR, pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO)
    notifier.start()
    return notifier


def main() -> None:
    notifier = run_watcher()
    try:
        run_periodic()
    finally:
        notifier.stop()


if __name__ == "__main__":
    print("Starting..")
    try:
        main()
    except KeyboardInterrupt:
        pass
    except:
        pass
    print("Bye!")
