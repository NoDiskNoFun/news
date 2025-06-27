#!/usr/bin/env -S python3 -u
import os, re, json, time, glob, sys, io, pwd
import socket, subprocess, pyinotify, requests
import platform, tomllib
from datetime import datetime

# Rebind stdout/stderr to unbuffered UTF-8 streams for systemd
sys.stdout = io.TextIOWrapper(
    open(sys.stdout.fileno(), "wb", 0), encoding="utf-8", line_buffering=True
)
sys.stderr = io.TextIOWrapper(
    open(sys.stderr.fileno(), "wb", 0), encoding="utf-8", line_buffering=True
)


CACHE_FILE = "/tmp/news_cache.json"
WATCH_DIR = "/var/lib/pacman/"
PACMAN_LOCK = WATCH_DIR + "db.lck"

RETRY_DELAY = 10
NORMAL_DELAY = 1800
MAX_RETRIES = 20
WATCHDOG_TIMEOUT = 5

MUTEX_LOCK = False

_last_run_data = {}


def once_per_day(func):
    tag = func.__name__

    def wrapper(*args, **kwargs):
        now = datetime.now()
        entry = _last_run_data.get(tag)

        if entry:
            last_run, cached_result = entry
            if now.date() == last_run.date():
                print(f"[once_per_day_cached] Skipping {tag}, returning cached result.")
                return cached_result

        result = func(*args, **kwargs)
        _last_run_data[tag] = (now, result)
        return result

    return wrapper


@once_per_day
def emmc_lifetime_estimation() -> dict:
    results = {}

    for dev_path in glob.glob("/dev/mmcblk[0-9]"):
        devname = os.path.basename(dev_path)
        sys_dev_path = os.path.realpath(f"/sys/block/{devname}/device")
        type_path = os.path.join(sys_dev_path, "type")

        try:
            with open(type_path) as f:
                dev_type = f.read().strip()
            if dev_type != "MMC":
                continue  # Not an eMMC device
        except FileNotFoundError:
            continue  # Unexpected sysfs layout, skip

        try:
            output = subprocess.check_output(
                ["mmc", "extcsd", "read", dev_path],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except subprocess.CalledProcessError:
            continue  # command failed unexpectedly

        match_a = re.search(
            r"EXT_CSD_DEVICE_LIFE_TIME_EST_TYP_A\]:\s+0x([0-9A-Fa-f]+)", output
        )
        match_b = re.search(
            r"EXT_CSD_DEVICE_LIFE_TIME_EST_TYP_B\]:\s+0x([0-9A-Fa-f]+)", output
        )

        if not match_a or not match_b:
            continue  # could not parse values

        val_a = int(match_a.group(1), 16)
        val_b = int(match_b.group(1), 16)

        def hex_to_percent(val):
            return min(val, 10) * 10  # clamp to 100%

        percent = max(hex_to_percent(val_a), hex_to_percent(val_b))
        results[dev_path] = percent

    return results


@once_per_day
def smart_health_report() -> dict:
    devices = []
    result = {}

    try:
        scan_output = subprocess.check_output(["smartctl", "--scan-open"], text=True)
        devices = [line.split()[0] for line in scan_output.splitlines()]
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to scan for SMART devices") from e

    for dev in devices:
        try:
            output = subprocess.check_output(["smartctl", "-Aj", "-Hj", dev], text=True)
            data = json.loads(output)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            result[dev] = "CRIT"
            continue

        # Check overall SMART support + health
        smart = data.get("smart_status", {})
        if not smart.get("passed", False):
            result[dev] = "CRIT"
            continue

        # Look for reallocated sectors (ID 5)
        reallocated = 0
        attrs = data.get("ata_smart_attributes", {}).get("table", [])
        for attr in attrs:
            if attr.get("id") == 5:  # Reallocated_Sector_Ct
                reallocated = attr.get("raw", {}).get("value", 0)
                break

        attrs = data.get("nvme_smart_health_information_log", {}).get("table", [])
        if "percentage_used" in attrs and attrs["percentage_used"] > 40:
            reallocated = 1

        if reallocated > 0:
            result[dev] = "WARN"
        else:
            result[dev] = "OK"

    eMMCs = emmc_lifetime_estimation()
    for mmc in eMMCs:
        if eMMCs[mmc] > 75:
            result[mmc] = "CRIT"
        elif eMMCs[mmc] > 50:
            result[mmc] = "WARN"
        else:
            result[mmc] = "OK"

    return result


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
    res = run_command(["checkupdates"])
    return len(res) if isinstance(res, list) else res


def get_devel_updates():
    users_with_yay = []

    # Find all users with yay cache
    for p in pwd.getpwall():
        homedir = p.pw_dir
        yay_cache = os.path.join(homedir, ".cache/yay")
        if os.path.isdir(yay_cache):
            users_with_yay.append((p.pw_name, homedir))

    update_set = set()

    # Step 2: Run yay -Qua --devel for each user
    for username, _ in users_with_yay:
        retries = 0
        while retries < 3:
            try:
                out = run_command(["sudo", "-u", username, "yay", "-Qua", "--devel"])
                if isinstance(out, list):
                    update_set.update(out)
                    break
                else:
                    raise Exception
            except:
                retries += 1

    return len(update_set)  # Return total number of unique updates


def fetch_news() -> str | bool:
    try:
        response = requests.get(
            "https://raw.githubusercontent.com/BredOS/news/refs/heads/main/notice.txt",
            timeout=5,
        )
        response.raise_for_status()
        return response.text
    except:
        return False


def fetch_upd_recommends() -> str:
    try:
        response = requests.get(
            "https://raw.githubusercontent.com/BredOS/news/refs/heads/main/upd_recommends.toml",
            timeout=5,
        )
        response.raise_for_status()
        data = tomllib.loads(response.text)

        arch = platform.machine().lower()
        val = data.get(arch, "Unknown")

        if isinstance(val, str):
            return val
        elif isinstance(val, int):
            return {0: "Yes", 1: "Maybe", 2: "No", 3: "F*ck NO"}.get(val, "Unknown")
        else:
            return "Unknown"
    except:
        return "Unknown"


def write_cache(updates, devel_updates, news, upd_recommends, smart) -> None:
    payload = {
        "updates": updates,
        "devel_updates": devel_updates,
        "news": news,
        "updrecommends": upd_recommends,
        "timestamp": int(time.time()),
        "smart": smart,
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
    upd_recommends = fetch_upd_recommends()
    smart = smart_health_report()
    if updates is None or devel is None:
        MUTEX_LOCK = False
        return False
    write_cache(updates, devel, news, upd_recommends, smart)
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
    # except:
    #     pass
    print("Bye!")
