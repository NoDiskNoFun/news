#!/usr/bin/python3

try:
    import os
    from sys import exit, stdin, stdout, argv
    from time import monotonic, time

    screensaver_mode = "-s" in argv[1:]
    hush_login_path = os.path.expanduser("~/.hush_login")
    if (
        os.path.isfile(hush_login_path) or (not stdin.isatty())
    ) and not screensaver_mode:
        exit(0)

    # Exit if for some fuckshit reason one of these called us.
    pid = os.getpid()
    while pid > 1:
        try:
            with open(f"/proc/{pid}/comm") as f:
                name = f.read().strip()
            if name in ["pacman", "yay", "makepkg", "ly-dm"]:
                exit(0)
            with open(f"/proc/{pid}/status") as f:
                pid = int(
                    next(line for line in f if line.startswith("PPid:")).split()[1]
                )
        except Exception:
            break

    if "HUSH_NEWS" in os.environ and os.environ["HUSH_NEWS"] == "1":
        exit(0)

    path = f"/tmp/news_run_{os.getuid()}.txt"
    try:
        with open(path, "r") as f:
            ts = int(f.read().strip())
        if time() - ts <= 2:
            exit(0)
    except (FileNotFoundError, ValueError):
        pass

    hush_news_path = os.path.expanduser("~/.hush_news")
    hush_updates_path = os.path.expanduser("~/.hush_updates")
    hush_disks_path = os.path.expanduser("~/.hush_disks")
    hush_smart_path = os.path.expanduser("~/.hush_smart")
    hush_news = (not os.geteuid()) or os.path.isfile(hush_news_path)
    hush_updates = (not os.geteuid()) or os.path.isfile(hush_updates_path)
    hush_disks = (not os.geteuid()) or os.path.isfile(hush_disks_path)
    hush_smart = (not os.geteuid()) or os.path.isfile(hush_smart_path)

    import asyncio, platform, psutil, socket, json, re
    import signal, shutil, termios, tty, select, fcntl
    import subprocess, shlex, types
    from collections import Counter
    from pathlib import Path
    from datetime import datetime, timedelta
except KeyboardInterrupt:
    import os

    os._exit(0)


def exit_on_buffer():
    if select.select([stdin], [], [], 0)[0] != []:
        os._exit(0)


exit_on_buffer()


def terminal_size() -> tuple:
    try:
        size = shutil.get_terminal_size(fallback=(999, 999))
        res = [size.columns, size.lines]
        if (not res[0]) or (not res[1]):
            return 999, 999
        return size.columns, size.lines
    except Exception:
        return 999, 999


CACHE_FILE = "/tmp/news_cache.json"

DEFAULT_CONF = """\"\"\"
BredOS-News Configuration

Refer to `https://wiki.bredos.org/e/en/customizations/news`,
for detailed instructions on how to configure.
\"\"\"

# Accent = "\\033[38;5;129m"
# Accent_Secondary = "\\033[38;5;104m"

# Hush_Updates = False
# Hush_Disks = False
# Hush_Smart = False
# Time_Tick = 0.1
# Time_Refresh = 0.25
# Onetime = False

\"\"\"
Shortcuts configuration

Shell commands, using $SHELL, and python functions are fully supported.
Only alphanumeric and symbol keys can be captured, no key combinations.
Capital keys work and can be bound to seperate shortcuts from lowercase.
\"\"\"

def shortcuts_help() -> None:
    print("Configured shortcuts:")
    for i in shortcuts.keys():
        shortcut = shortcuts[i]
        if is_function(shortcut):
            print(f" - {i}: Function {shortcut.__name__}")
        else:
            print(f' - {i}: \"{shortcuts[i]}\"')
    print("\\n")

shortcuts["1"] = "bredos-config"
shortcuts["0"] = "sudo sys-report"
shortcuts["?"] = shortcuts_help
"""

printed_lines = 0
last_lines = []
last_size = terminal_size()
ansi_re = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1B\\)|P[^\x1B]*\x1B\\|_[^\x1B]*\x1B\\|\^[^\x1B]*\x1B\\|X.)",
    re.DOTALL,
)
tix = 0
accent_dir = 1
_nansi = {}
_nansi_order = []
_last_run_data = {}
_run = []
_shell = os.environ["SHELL"]


def once(func):
    tag = func.__name__

    def wrapper(*args, **kwargs):
        entry = _last_run_data.get(tag)

        if entry:
            return entry

        result = func(*args, **kwargs)
        _last_run_data[tag] = result
        return result

    return wrapper


def phy_lines(lines: list[str]) -> list:
    res = []
    buf = ""
    for chunk in lines:
        buf += chunk
        while True:
            nl_pos = buf.find("\n")
            if nl_pos == -1:
                break
            # Append substring up to newline (excluding '\n')
            res.append(buf[:nl_pos])
            buf = buf[nl_pos + 1 :]

    # Append remainder if any (no trailing newline)
    if buf:
        res.append(buf)
    return res


def refresh_lines(new_lines: list[str]) -> None:
    global printed_lines, last_lines, last_size, tix, awidth
    curterm = terminal_size()
    if curterm != last_size:
        stdout.write("\033[2J\033[3J\033[H")
        last_lines = []
        printed_lines = 0
        tix = 0
        last_size = curterm

    physical_lines = []
    buf = ""

    physical_lines = phy_lines(new_lines)

    if physical_lines == last_lines:
        return

    new_physical_lines = len(physical_lines)

    # Move up N == printed_lines
    if printed_lines:
        stdout.write(f"\033[{printed_lines}F")

    # Terminal size checks
    if (curterm[1] < new_physical_lines + 1) or (
        curterm[0] < max(len(ansi_re.sub("", line)) for line in physical_lines)
    ):
        awidth = terminal_size()[0]
        physical_lines = [
            physical_lines[0],
            animation(),
        ]
        new_physical_lines = 2

    # Print the new physical lines exactly as-is
    for i in range(len(physical_lines)):
        if (new_physical_lines != printed_lines) or (
            physical_lines[i] != last_lines[i]
        ):
            stdout.write(f"\033[2K{physical_lines[i]}\n")
        else:
            print()

    # Clear leftovers if we previously printed more lines
    if printed_lines > new_physical_lines:
        for _ in range(printed_lines - new_physical_lines):
            print("\x1b[2K")
        stdout.write(f"\033[{printed_lines-new_physical_lines}F")

    printed_lines = new_physical_lines
    last_lines = physical_lines


sbcs = {
    "ArmSoM AIM7 ": "ArmSoM AIM7",
    "ArmSoM Sige7": "ArmSoM Sige7",
    "ArmSoM W3": "W3",
    "Banana Pi M7": "BPI M7",
    "Embedfire LubanCat-4": "LubanCat-4",
    "Firefly AIO-3588L MIPI101(Linux)": "AIO-3588L",
    "Firefly ITX-3588J HDMI(Linux)": "ITX-3588J",
    "FriendlyElec CM3588": "CM3588",
    "FriendlyElec NanoPC-T6": "NanoPC-T6",
    "FriendlyElec NanoPC-T6 LTS": "NanoPC-T6 LTS",
    "FriendlyElec NanoPi R6C": "NanoPi R6C",
    "FriendlyElec NanoPi R6S": "NanoPi R6S",
    "Fxblox RK1": "Fxblox RK1",
    "Fydetab Duo": "FydeTab Duo",
    "HINLINK H88K": "H88K",
    "Indiedroid Nova": "indieDroid Nova",
    "Khadas Edge2": "Edge2",
    "Khadas VIM4": "VIM4",
    "Khadas VIM 4": "VIM4",
    "Mekotronics R58 MiniPC (RK3588 MINIPC LP4x V1.0 BlueBerry Board)": "R58 MiniPC",
    "Mekotronics R58X (RK3588 EDGE LP4x V1.0 BlueBerry Board)": "R58X",
    "Mekotronics R58X-4G (RK3588 EDGE LP4x V1.2 BlueBerry Board)": "R58X-4G",
    "Mixtile Blade 3": "Blade 3",
    "Mixtile Blade 3 v1.0.1": "Blade 3",
    "Mixtile Core 3588E": "Core 3588E",
    "Milk-V Mars": "Mars",
    "Orange Pi 5": "OPi5",
    "Orange Pi 5 Ultra Orange Pi 5 Max": "OPi5 Ultra Max",
    "Orange Pi 5 Plus": "OPi5 Plus",
    "Orange Pi 5 Pro": "OPi5 Pro",
    "Orange Pi 5 Max": "OPi5 Max",
    "Orange Pi 5 Ultra": "OPi5 Ultra",
    "Orange Pi 5B": "OPi 5B",
    "Orange Pi CM5": "OPi CM5",
    "Orange Pi R2S": "OPi R2S",
    "Orange Pi RV": "OPi RV",
    "Orange Pi RV 2": "OPi RV2",
    "RK3588 CoolPi CM5 EVB Board": "CoolPi CM5 EVB",
    "RK3588 CoolPi CM5 NoteBook Board": "CoolPi CM5 Notebook",
    "RK3588 EDGE LP4x V1.2 MeiZhuo BlueBerry Board": "EDGE LP4x V1.2 BlueBerry",
    "RK3588 EDGE LP4x V1.4 BlueBerry Board": "EDGE LP4x V1.4 BlueBerry",
    "RK3588 MINIPC-MIZHUO LP4x V1.0 BlueBerry Board": "MINIPC-MIZHUO V1.0",
    "RK3588S CoolPi 4B Board": "CoolPi 4B",
    "ROC-RK3588S-PC V12(Linux)": "ROC-RK3588S-PC V12",
    "Radxa Orion O6": "Orion O6",
    "Radxa CM5 IO": "CM5 IO",
    "Radxa CM5 RPI CM4 IO": "CM5 RPI CM4 IO",
    "Radxa NX5 IO": "NX5 IO",
    "Radxa NX5 Module": "NX5 Module",
    "Radxa ROCK 5 ITX": "ROCK 5 ITX",
    "Radxa ROCK 5A": "ROCK 5A",
    "Radxa ROCK 5B": "ROCK 5B",
    "Radxa ROCK 5B Plus": "ROCK 5B Plus",
    "Radxa ROCK 5C": "ROCK 5C",
    "Radxa ROCK 5D": "ROCK 5D",
    "Rockchip RK3588": "RK3588",
    "Rockchip RK3588 EVB1 LP4 V10 Board": "EVB1 V10",
    "Rockchip RK3588 EVB1 LP4 V10 Board + DSI DSC PANEL MV2100UZ1 DISPLAY Ext Board": "EVB1 V10 + DSC PANEL",
    "Rockchip RK3588 EVB1 LP4 V10 Board + RK Ext HDMImale to eDP V10": "EVB1 V10 + HDMImale-eDP",
    "Rockchip RK3588 EVB1 LP4 V10 Board + RK HDMI to DP Ext Board": "EVB1 V10 + HDMI-DP",
    "Rockchip RK3588 EVB1 LP4 V10 Board + RK3588 EDP 8LANES V10 Ext Board": "EVB1 V10 + EDP 8LANES",
    "Rockchip RK3588 EVB1 LP4 V10 Board + Rockchip RK3588 EVB V10 Extboard": "EVB1 V10 + EVB V10 Extboard",
    "Rockchip RK3588 EVB1 LP4 V10 Board + Rockchip RK628 HDMI to MIPI Extboard": "EVB1 V10 + RK628 Extboard",
    "Rockchip RK3588 EVB2 LP4 V10 Board": "EVB2 V10",
    "Rockchip RK3588 EVB2 LP4 V10 eDP Board": "EVB2 V10 eDP",
    "Rockchip RK3588 EVB2 LP4 V10 eDP to DP Board": "EVB2 V10 eDP-DP",
    "Rockchip RK3588 EVB3 LP5 V10 Board": "EVB3 LP5 V10",
    "Rockchip RK3588 EVB3 LP5 V10 EDP Board": "EVB3 LP5 V10 EDP",
    "Rockchip RK3588 EVB4 LP4 V10 Board": "EVB4 LP4 V10",
    "Rockchip RK3588 EVB6 LP4 V10 Board": "EVB6 LP4 V10",
    "Rockchip RK3588 EVB7 LP4 V10 Board": "EVB7 LP4 V10",
    "Rockchip RK3588 EVB7 LP4 V11 Board": "EVB7 LP4 V11",
    "Rockchip RK3588 EVB7 V11 Board": "EVB7 V11",
    "Rockchip RK3588 EVB7 V11 Board + Rockchip RK628 HDMI to MIPI Extboard": "EVB7 V11 + RK628 Extboard",
    "Rockchip RK3588 NVR DEMO LP4 SPI NAND Board": "NVR DEMO SPI NAND",
    "Rockchip RK3588 NVR DEMO LP4 V10 Android Board": "NVR DEMO V10",
    "Rockchip RK3588 NVR DEMO LP4 V10 Board": "NVR DEMO V10",
    "Rockchip RK3588 NVR DEMO1 LP4 V21 Android Board": "NVR DEMO1 V21",
    "Rockchip RK3588 NVR DEMO1 LP4 V21 Board": "NVR DEMO1 V21",
    "Rockchip RK3588 NVR DEMO3 LP4 V10 Android Board": "NVR DEMO3 V10",
    "Rockchip RK3588 NVR DEMO3 LP4 V10 Board": "NVR DEMO3 V10",
    "Rockchip RK3588 PCIE EP Demo V11 Board": "PCIE EP Demo V11",
    "Rockchip RK3588 TOYBRICK LP4 X10 Board": "TOYBRICK X10",
    "Rockchip RK3588 TOYBRICK X10 Board": "TOYBRICK X10",
    "Rockchip RK3588 VEHICLE EVB V10 Board": "VEHICLE EVB V10",
    "Rockchip RK3588 VEHICLE EVB V20 Board": "VEHICLE EVB V20",
    "Rockchip RK3588 VEHICLE EVB V21 Board": "VEHICLE EVB V21",
    "Rockchip RK3588 VEHICLE EVB V22 Board": "VEHICLE EVB V22",
    "Rockchip RK3588 VEHICLE S66 Board V10": "VEHICLE S66 V10",
    "Rockchip RK3588-RK1608 EVB7 LP4 V10 Board": "RK1608 EVB7 LP4 V10",
    "Rockchip RK3588J": "RK3588J",
    "Rockchip RK3588M": "RK3588M",
    "Rockchip RK3588S": "RK3588S",
    "Rockchip RK3588S EVB1 LP4X V10 Board": "RK3588S EVB1 LP4X V10",
    "Rockchip RK3588S EVB2 LP5 V10 Board": "RK3588S EVB2 LP5 V10",
    "Rockchip RK3588S EVB3 LP4 V10 Board + Rockchip RK3588S EVB V10 Extboard": "RK3588S EVB3 LP4 V10 + Extboard",
    "Rockchip RK3588S EVB3 LP4 V10 Board + Rockchip RK3588S EVB V10 Extboard1": "RK3588S EVB3 LP4 V10 + Extboard1",
    "Rockchip RK3588S EVB3 LP4 V10 Board + Rockchip RK3588S EVB V10 Extboard2": "RK3588S EVB3 LP4 V10 + Extboard2",
    "Rockchip RK3588S EVB3 LP4X V10 Board": "RK3588S EVB3 LP4X V10",
    "Rockchip RK3588S EVB4 LP4X V10 Board": "RK3588S EVB4 LP4X V10",
    "Rockchip RK3588S EVB8 LP4X V10 Board": "RK3588S EVB8 LP4X V10",
    "Rockchip RK3588S TABLET RK806 SINGLE Board": "RK3588S TABLET RK806",
    "Rockchip RK3588S TABLET V10 Board": "RK3588S TABLET V10",
    "Rockchip RK3588S TABLET V11 Board": "RK3588S TABLET V11",
    "Turing Machines RK1": "Turing RK1",
}


@once
def hw_impl_id_to_vendor(impl_id: int) -> str:
    vendors = {
        0x41: "ARM",
        0x42: "Broadcom",
        0x43: "Cavium",
        0x44: "DEC",
        0x46: "FUJITSU",
        0x48: "HiSilicon",
        0x49: "Infineon",
        0x4D: "Motorola",
        0x4E: "NVIDIA",
        0x50: "APM",
        0x51: "Qualcomm",
        0x53: "Samsung",
        0x56: "Marvell",
        0x61: "Apple",
        0x66: "Faraday",
        0x69: "Intel",
        0x6D: "Microsoft",
        0x70: "Phytium",
        0xC0: "Ampere",
    }
    return vendors.get(impl_id, "Unknown")


@once
def arm_part_id_to_name(part_id: int) -> str:
    arm_parts = {
        0x810: "ARM810",
        0x920: "ARM920",
        0x922: "ARM922",
        0x926: "ARM926",
        0x940: "ARM940",
        0x946: "ARM946",
        0x966: "ARM966",
        0xA20: "ARM1020",
        0xA22: "ARM1022",
        0xA26: "ARM1026",
        0xB02: "ARM11 MPCore",
        0xB36: "ARM1136",
        0xB56: "ARM1156",
        0xB76: "ARM1176",
        0xC05: "Cortex-A5",
        0xC07: "Cortex-A7",
        0xC08: "Cortex-A8",
        0xC09: "Cortex-A9",
        0xC0D: "Cortex-A17",  # Originally A12
        0xC0F: "Cortex-A15",
        0xC0E: "Cortex-A17",
        0xC14: "Cortex-R4",
        0xC15: "Cortex-R5",
        0xC17: "Cortex-R7",
        0xC18: "Cortex-R8",
        0xC20: "Cortex-M0",
        0xC21: "Cortex-M1",
        0xC23: "Cortex-M3",
        0xC24: "Cortex-M4",
        0xC27: "Cortex-M7",
        0xC60: "Cortex-M0+",
        0xD01: "Cortex-A32",
        0xD02: "Cortex-A34",
        0xD03: "Cortex-A53",
        0xD04: "Cortex-A35",
        0xD05: "Cortex-A55",
        0xD06: "Cortex-A65",
        0xD07: "Cortex-A57",
        0xD08: "Cortex-A72",
        0xD09: "Cortex-A73",
        0xD0A: "Cortex-A75",
        0xD0B: "Cortex-A76",
        0xD0C: "Neoverse-N1",
        0xD0D: "Cortex-A77",
        0xD0E: "Cortex-A76AE",
        0xD13: "Cortex-R52",
        0xD15: "Cortex-R82",
        0xD16: "Cortex-R52+",
        0xD20: "Cortex-M23",
        0xD21: "Cortex-M33",
        0xD22: "Cortex-M55",
        0xD23: "Cortex-M85",
        0xD40: "Neoverse-V1",
        0xD41: "Cortex-A78",
        0xD42: "Cortex-A78AE",
        0xD43: "Cortex-A65AE",
        0xD44: "Cortex-X1",
        0xD46: "Cortex-A510",
        0xD47: "Cortex-A710",
        0xD48: "Cortex-X2",
        0xD49: "Neoverse-N2",
        0xD4A: "Neoverse-E1",
        0xD4B: "Cortex-A78C",
        0xD4C: "Cortex-X1C",
        0xD4D: "Cortex-A715",
        0xD4E: "Cortex-X3",
        0xD4F: "Neoverse-V2",
        0xD80: "Cortex-A520",
        0xD81: "Cortex-A720",
        0xD82: "Cortex-X4",
        0xD84: "Neoverse-V3",
        0xD85: "Cortex-X925",
        0xD87: "Cortex-A725",
    }
    return arm_parts.get(part_id, "Unknown")


@once
def get_sys_id() -> tuple:
    hostname = platform.node()
    os_info = f"GNU/Linux {platform.release()} {platform.machine()}"

    cpu_model = None
    vendor = None
    part_name = None
    cpu_model = None
    cpu_implementer = None
    cpu_part = None

    with open("/proc/cpuinfo") as f:
        cpuinfo = f.read().splitlines()

    for line in cpuinfo:
        if "cpu model" in line or "model name" in line:
            cpu_model = line.split(":", 1)[1].strip()
            break

    if cpu_model is None:
        cpu_implementer = None
        cpu_part = None
        for line in cpuinfo:
            if "CPU implementer" in line:
                cpu_implementer = int(line.split(":")[1].strip(), 16)
            elif "CPU part" in line:
                cpu_part = int(line.split(":")[1].strip(), 16)

            if cpu_implementer is not None and cpu_part is not None:
                break

        vendor = hw_impl_id_to_vendor(cpu_implementer)
        part_name = arm_part_id_to_name(cpu_part)

        cpu_model = f"{vendor} {part_name}"

    cpu_count = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)

    mem = psutil.virtual_memory()
    total_memory = f"{mem.total // (1024**2)} MB"

    return (
        hostname,
        os_info,
        cpu_model,
        vendor,
        part_name,
        cpu_count,
        cpu_threads,
        total_memory,
    )


def get_active_ipv4_interfaces() -> dict:
    active_interfaces = {}
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if (
                addr.family == socket.AF_INET
                and addr.address != "127.0.0.1"
                and not iface.startswith(("br-", "docker", "virbr", "ve-"))
            ):
                active_interfaces[iface] = addr.address
    return active_interfaces


def get_storage_usages() -> dict:
    mounts = {}
    seen_devices = set()

    with open("/proc/mounts", "r") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 2:
                continue
            device, mountpoint = parts[0], parts[1]

            # Skip non-real devices
            if not device.startswith(("/dev/", "UUID=", "LABEL=")):
                continue

            # Skip duplicates
            real_device = os.path.realpath(device)
            if real_device in seen_devices:
                continue
            seen_devices.add(real_device)

            try:
                stats = os.statvfs(mountpoint)
                total_bytes = stats.f_frsize * stats.f_blocks
                free_bytes = stats.f_frsize * stats.f_bavail
                used_bytes = total_bytes - free_bytes
                if total_bytes == 0:
                    continue  # Skip empty fs
                percent_used = round((used_bytes / total_bytes) * 100, 1)
            except Exception:
                continue  # Skip unreadable

            if (
                "/efi" in mountpoint or "/boot" in mountpoint or len(mountpoint) > 40
            ):  # Don't do boot partitions or Panda's gayshit
                continue

            try:
                fstype = subprocess.check_output(
                    ["findmnt", "-no", "FSTYPE", "--target", mountpoint],
                    timeout=2,
                    text=True,
                ).strip()

                if fstype == "btrfs":
                    subvol = subprocess.check_output(
                        ["btrfs", "subvolume", "show", mountpoint],
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    for line in subvol.splitlines():
                        if line.strip().startswith("Name:"):
                            name = line.strip().split(":", 1)[1].strip()
                            if name not in ("@", "/"):
                                break  # skip subvols like @home
                    else:
                        mounts[mountpoint] = [percent_used, total_bytes]
                else:
                    mounts[mountpoint] = [percent_used, total_bytes]
            except:
                mounts[mountpoint] = [percent_used, total_bytes]  # fallback

    if "/" in mounts:
        mounts["Usage of /"] = mounts["/"]
        del mounts["/"]
    return mounts


async def get_system_info() -> dict:
    (
        hostname,
        os_info,
        cpu_model,
        vendor,
        part_name,
        cpu_count,
        cpu_threads,
        total_memory,
    ) = get_sys_id()

    uptime_seconds = int(psutil.boot_time())
    uptime = datetime.now() - datetime.fromtimestamp(uptime_seconds)
    days, seconds = uptime.days, uptime.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    uptime_str = ""
    if days:
        uptime_str += f"{days} days"
        if hours:
            uptime_str += f" {hours} hours"
        if minutes:
            uptime_str += f" {minutes} minutes"
    elif hours:
        uptime_str += f"{hours} hours"
        if minutes:
            uptime_str += f" {minutes} minutes"
    elif minutes:
        uptime_str += f"{minutes} minutes"
    else:
        uptime_str += "seconds"

    with open("/proc/loadavg") as f:
        load_avg = f.read().split()[0]

    with open("/proc/stat") as f:
        processes = sum(1 for line in f if line.startswith("processes"))

    disks = get_storage_usages()

    logged_in_users = 0
    try:
        users_process = await asyncio.create_subprocess_exec(
            "who",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await users_process.communicate()
        seen_users = set()
        lines = stdout.decode().split("\n")
        lines.pop()
        for i in lines:
            user = i.split(" ")[0]
            if user not in seen_users:
                seen_users.add(user)
        logged_in_users = len(seen_users)
    except:
        pass

    with open("/proc/meminfo") as f:
        meminfo = {line.split(":")[0]: int(line.split()[1]) for line in f}
    mem_usage_percent = (
        (meminfo["MemTotal"] - meminfo["MemAvailable"]) / meminfo["MemTotal"] * 100
    )

    swap_usage_percent = (
        (100 - (meminfo["SwapFree"] / meminfo["SwapTotal"] * 100))
        if meminfo["SwapTotal"] > 0
        else None
    )

    net_ifs = get_active_ipv4_interfaces()

    return {
        "system_load": load_avg,
        "processes": processes,
        "hostname": hostname,
        "uptime": uptime_str,
        "cpu_model": cpu_model,
        "cpu_count": cpu_count,
        "cpu_threads": cpu_threads,
        "os_info": os_info,
        "total_memory": total_memory,
        "disks": disks,
        "logged_in_users": logged_in_users,
        "memory_usage": f"{mem_usage_percent:.1f}%",
        "net_ifs": net_ifs,
        "swap_usage": (
            f"{swap_usage_percent:.1f}%" if swap_usage_percent is not None else None
        ),
    }


async def get_service_statuses(command: str) -> Counter:
    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    statuses = [
        line.strip()
        for line in stdout.decode().strip().split("\n")
        if line and line not in ["running", "exited", "dead"]
    ]
    return Counter(statuses)


async def count_failed_systemd() -> dict:
    system_statuses = await get_service_statuses(
        "systemctl list-units --type=service --no-legend --no-pager | awk '{print $4}'"
    )

    # user_statuses = await get_service_statuses(
    #     "systemctl --user list-units --type=service --no-legend --no-pager | awk '{print $4}'"
    # )

    total_statuses = system_statuses  # + user_statuses
    total_count = sum(total_statuses.values())

    return {"total": total_count, "breakdown": dict(total_statuses)}


def time_ago(ts):
    delta = int(time()) - int(ts)
    if delta < 60:
        return f"{delta}s ago"
    elif delta < 3600:
        return f"{delta // 60}m ago"
    elif delta < 86400:
        return f"{delta // 3600}h ago"
    else:
        return f"{delta // 86400}d ago"


async def get_updates():
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            updates = data.get("updates")
            devel_updates = data.get("devel_updates")
            news = data.get("news")
            updrecommends = data.get("updrecommends", "Unknown")
            timestamp = data.get("timestamp")
            smart = data.get("smart")
            msgs = []

            if shutil.which("yay") is None:
                msgs.append(
                    "Install `yay` to view development package updates during login.\n"
                )
            ago = time_ago(timestamp)

            return [
                updates,
                devel_updates,
                news,
                updrecommends,
                [f"{colors.bland_t}(Latest check was {ago}){colors.endc}"] + msgs,
                smart,
            ]
    except Exception as err:
        return f"\n{colors.bland_t}The updates status has not yet refreshed. Check back later.{colors.endc}\n"


def detect_install_device() -> str:
    try:
        with open("/sys/firmware/devicetree/base/model", "r") as model_file:
            device = model_file.read().rstrip("\n").rstrip("\x00")
            return device
    except FileNotFoundError:
        try:
            with open("/sys/class/dmi/id/product_name", "r") as product_name_file:
                device = product_name_file.read().rstrip("\n")
                return device
        except FileNotFoundError:
            return "unknown"


def seperator(current_str: str, collumns: int) -> None:
    return (" " * (collumns - len(nansi(current_str)) + 2)) + "   "


class colors:
    # Main
    okay = "\033[92m"
    warning = "\033[93m"
    error = "\033[91m"

    # Styling
    underline = "\033[4m"
    bold = "\033[1m"
    endc = "\033[0m"  # use to reset

    # Okay
    okblue = "\033[94m"
    okcyan = "\033[96m"

    # Coloured Text
    black_t = "\033[30m"
    red_t = "\033[31m"
    green_t = "\033[32m"
    yellow_t = "\033[33m"
    blue_t = "\033[34m"
    magenta_t = "\033[35m"
    cyan_t = "\033[36m"
    white_t = "\033[37m"
    bland_t = "\033[2;37m"

    # Background
    white_bg_black_bg = "\033[38;5;0m\033[48;5;255m"
    inverse = "\033[7m"
    uninverse = "\033[27m"

    # Accents
    accent = okblue
    accent2 = yellow_t


def nansi(inpt: str) -> str:
    if "\033" not in inpt:
        return inpt.replace("\n", "")

    if inpt in _nansi:
        # Move to most recently used
        _nansi_order.remove(inpt)
        _nansi_order.append(inpt)
        return _nansi[inpt]

    result = ansi_re.sub("", inpt).rstrip().replace("\n", "")

    # Add to cache
    _nansi[inpt] = result
    _nansi_order.append(inpt)

    # Evict LRU if over capacity
    if len(_nansi_order) > 50:
        oldest = _nansi_order.pop(0)
        del _nansi[oldest]

    return result


def animation() -> str:
    global awidth, tix, accent_dir
    prompt = (
        "Press any key to enter -- System Ready -- "
        if os.geteuid()
        else "CAUTION -!!- "
    )
    repeated = prompt * (((awidth - 4) // len(prompt)) + 3)

    scroll_start = tix % len(prompt)
    scrolled = repeated[scroll_start : scroll_start + (awidth - 4)]

    accent_width = 10
    cycle_len = awidth - accent_width + 1  # valid start positions for accent

    # Total steps for a full ping-pong cycle
    total_steps = max(2 * (cycle_len - 1), 2)

    step = tix * 3 % total_steps

    # Ping-pong motion calculation (no changes to `tix`)
    if step >= cycle_len:
        pos = total_steps - step  # moving left
    else:
        pos = step  # moving right

    if (not scroll_start) and not pos:
        tix = 0

    inner = (
        scrolled[:pos]
        + (colors.accent if os.geteuid() else colors.error)
        + scrolled[pos : pos + accent_width]
        + colors.bland_t
        + scrolled[pos + accent_width :]
    )

    tix += 1
    return f"{colors.bland_t}[ {inner} ]{colors.endc}"


async def main() -> None:
    global awidth, tix
    info_task = get_system_info()
    services_task = count_failed_systemd()
    updates_task = get_updates()

    device = None
    sbc_declared = detect_install_device()
    if sbc_declared in sbcs.keys():
        device = sbcs[sbc_declared]
    else:
        device = sbc_declared

    system_info = await info_task
    msg = []

    msg.append(
        f"{colors.accent2 if os.geteuid() else colors.red_t}{colors.bold}Welcome to BredOS{colors.endc} {colors.bland_t}({system_info['os_info']}){colors.endc}\n"
    )
    msg.append(
        f"{colors.accent2 if os.geteuid() else colors.red_t}{colors.bold}\n*{colors.endc} Documentation:  https://wiki.bredos.org/\n"
    )
    msg.append(
        f"{colors.accent2 if os.geteuid() else colors.red_t}{colors.bold}*{colors.endc} Support:        https://discord.gg/beSUnWGVH2\n\n"
    )

    msg.append(
        f"        {colors.bland_t}System Info as of {datetime.now().strftime('%a %d @ %H:%M:%S')}{colors.endc}\n"
    )

    device_str = ""
    if device is not None:
        device_str += f"{colors.accent if os.geteuid() else colors.red_t}Device:{colors.endc} {colors.accent2}{device}{colors.endc}"

    hostname_str = f"{colors.accent if os.geteuid() else colors.red_t}Hostname:{colors.endc} {system_info['hostname']}"

    uptime_str = f"{colors.accent if os.geteuid() else colors.red_t}Uptime:{colors.endc} {system_info['uptime']}"
    logged_str = f"{colors.accent if os.geteuid() else colors.red_t}Users logged in:{colors.endc} {system_info['logged_in_users']}"

    cpu_str = f"{colors.accent if os.geteuid() else colors.red_t}CPU:{colors.endc} {system_info['cpu_model']} ({system_info['cpu_count']}c, {system_info['cpu_threads']}t)"
    load_str = f"{colors.accent if os.geteuid() else colors.red_t}System load:{colors.endc} {system_info['system_load']}"

    memory_str = f"{colors.accent if os.geteuid() else colors.red_t}Memory:{colors.endc} {system_info['memory_usage']} of {system_info['total_memory']} used"

    swap_str = ""
    upd_str = ""

    splitter = True
    last = memory_str

    if system_info["swap_usage"] is not None:
        swap_str = f"{colors.accent if os.geteuid() else colors.red_t}Swap usage:{colors.endc} {system_info['swap_usage']}\n"
        splitter = False

    collumns = max(
        len(nansi(device_str)),
        len(nansi(uptime_str)),
        len(nansi(cpu_str)),
        len(nansi(memory_str)),
        len(nansi(swap_str)),
    )

    msg.append(device_str)
    if device_str:
        msg.append(seperator(device_str, collumns))
    msg.append(hostname_str + "\n")

    msg.append(uptime_str)
    msg.append(seperator(uptime_str, collumns))
    msg.append(logged_str + "\n")

    msg.append(cpu_str)
    msg.append(seperator(cpu_str, collumns))
    msg.append(load_str + "\n")

    msg.append(memory_str)

    if swap_str:
        msg.append(seperator(memory_str, collumns))
        msg.append(swap_str)

    for netname, ip in system_info["net_ifs"].items():
        if splitter:
            msg.append(seperator(last, collumns))
        last = f"{colors.accent if os.geteuid() else colors.red_t}{netname}:{colors.endc} {ip}"
        msg.append(last)
        if splitter:
            msg.append("\n")
        splitter = not splitter

    if not hush_disks:
        human_readable = lambda b: (
            lambda u=["B", "KB", "MB", "GB", "TB", "PB", "EB"]: (
                i := max(0, min(len(u) - 1, (b.bit_length() - 1) // 10)),
                f"{b/1024**i:.1f}{u[i]}",
            )[1]
        )()

        disks = sorted(list(system_info["disks"].keys()))
        if "Usage of /" in disks:
            disks.insert(0, disks.pop(disks.index("Usage of /")))

        for disk in disks:
            if len(disk) > 15:
                if splitter:
                    msg.append("\n")
                    splitter = False
            if splitter:
                msg.append(seperator(last, collumns))
            dstr = (
                str(system_info["disks"][disk][0])
                + "% of "
                + human_readable(system_info["disks"][disk][1])
            )
            last = f"{colors.accent if os.geteuid() else colors.red_t}{disk}:{colors.endc} {dstr}"
            msg.append(last)
            if splitter:
                msg.append("\n")
            splitter = not splitter

    if splitter:
        msg.append("\n")

    updates = await updates_task

    if not hush_updates:
        if isinstance(updates, list):
            if updates[0] and not updates[1]:
                upd_str = f"\n{colors.bold}{colors.cyan_t}{updates[0]} updates available.{colors.endc} "
            elif updates[0] and updates[1]:
                upd_str = f"\n{colors.bold}{colors.cyan_t}{updates[0] + updates[1]} updates available, of which {updates[1]} are development packages.{colors.endc}\n"
            elif updates[1]:
                upd_str = f"\n{colors.bold}{colors.cyan_t}{updates[1]} development updates available.{colors.endc}\n"
            else:
                upd_str = f"\n{colors.accent2 if colors.accent2 != colors.yellow_t else colors.green_t}You are up to date!{colors.endc} "
            for i in updates[4]:
                upd_str += i + "\n"
            if (updates[0] or updates[1]) and updates[3] != "Unknown":
                upd_str += (
                    f"{colors.accent}Should you update:{colors.endc} {updates[3]}\n"
                )

        elif isinstance(updates, str):
            upd_str = updates

        if upd_str:
            msg.append(upd_str + "\n")

    if os.getlogin() == "bred" and os.path.exists("/usr/bin/Bakery"):
        msg.append(f"{colors.yellow_t}Setup is {colors.bold}INCOMPLETE{colors.endc}!\n")
        msg.append(
            f"If you wish to complete it from the command line, run `{colors.bland_t}{colors.bold}Bakery --tui{colors.endc}`\n"
        )
        msg.append("\n")
    else:
        if not hush_news:
            if hush_updates:
                msg.append("\n")
            if isinstance(updates, list):
                news = updates[2]
                msg += [(news if news else "Failed to fetch news.\n"), "\n"]
            else:
                msg += ["Failed to fetch news.", "\n", "\n"]

    show_url = False
    if not hush_smart:
        if isinstance(updates[5], dict):
            for drive in updates[5].keys():
                state = updates[5][drive]
                if state == "WARN":
                    msg.append(
                        f'{colors.bold}{colors.yellow_t}Drive "{drive}" reliability compromised - Backup your data{colors.endc}\n'
                    )
                    show_url = True
                elif state == "CRIT":
                    msg.append(
                        f'{colors.bold}{colors.red_t}DRIVE "{drive}" CRITICAL HEALTH - BACKUP YOUR DATA{colors.endc}\n'
                    )
                    show_url = True

        if show_url:
            msg.append(
                f"\n{colors.bold}For more information, visit:\n{colors.blue_t}https://wiki.bredos.org/en/how-to/disk-failure{colors.endc}\n\n"
            )

    if not os.geteuid():
        msg.append(
            "\n"
            + colors.red_t
            + "You're running as ROOT! Be careful and good luck!"
            + colors.endc
            + "\n"
        )

    services = await services_task
    if hush_updates and hush_news:
        msg.append("\n")
    if not services["total"]:
        msg.append(
            f"{colors.bold}{colors.accent2 if colors.accent2 != colors.yellow_t else colors.green_t}System is operating normally.{colors.endc}\n"
        )
    else:
        for i in services["breakdown"].keys():
            n = services["breakdown"][i]
            if i == "failed":
                msg.append(
                    f"{colors.bold}{colors.red_t}{n}{colors.endc} services have {colors.bold}{colors.red_t}{i}{colors.endc}\n"
                )
            else:
                msg.append(
                    f'{colors.bold}{colors.yellow_t}{n}{colors.endc} services report status {colors.bold}{colors.yellow_t}"{i}"{colors.endc}\n'
                )

    plines = phy_lines(msg)
    sz = terminal_size()
    awidth = max(len(nansi(line)) for line in plines)
    if (awidth > sz[0]) or (len(plines) > sz[1]):
        kernl = list(msg[0])
        kernst = kernl.index("(") + 1
        kernend = kernl.index(")")
        sps = 0
        for i in range(kernst, kernend):
            kernl[i] = " "
            sps += 1
        smallmsg = "Terminal too small"
        if len(smallmsg) < sps and 0:
            msg[0] = msg[0][:kernst] + colors.warning + smallmsg + colors.bland_t + ")"
        else:
            stm = ((sps - len(smallmsg)) // 2) + 1
            kernl.insert(kernst + 1, colors.warning)
            kernl.insert(kernend, colors.bland_t)
            for i in range(len(smallmsg)):
                kernl[kernst + stm + i] = smallmsg[i]
            msg[0] = "".join(kernl)
    msg.append(animation())

    refresh_lines(msg)


async def delay(duration: float) -> None:
    loop = asyncio.get_running_loop()
    evt = asyncio.Event()
    loop.call_later(duration, evt.set)
    await evt.wait()


async def suspend(until: float) -> None:
    while until > monotonic():
        stdout.write(f"\033[1F\033[2K{animation()}\n")
        stdout.flush()
        await delay(Time_Tick)


def shell_inject(text: str) -> bool:
    try:
        for ch in text:
            fcntl.ioctl(stdin, termios.TIOCSTI, ch.encode())
        return True
    except KeyboardInterrupt:
        pass
    except:
        pass
    return False


def is_function(obj) -> bool:
    return isinstance(obj, (types.FunctionType, types.BuiltinFunctionType))


def shortcut_handler(text: str) -> bool:
    global _run
    if text and text[0] in shortcuts.keys():
        shortcut = shortcuts[text[0]]
        if is_function(shortcut):
            try:  # Yay, arbitrary code goooooooo
                shortcut()
            except KeyboardInterrupt:
                pass
            except:
                pass
        elif not shell_inject(f" {shortcut}\n"):
            _run = [_shell, "-c", f'eval "{shortcut}"; exec {_shell}']
    else:
        shell_inject(text)


def kill_parent(sig=signal.SIGKILL):
    parent_pid = os.getppid()
    try:
        os.kill(parent_pid, sig)
    except:
        pass


async def loop_main() -> None:
    global screensaver_mode
    # Pure aneurism.

    if screensaver_mode:
        stdout.write("\033[?1049h\033[2J\033[H")

    fd = stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    stdout.write("\033[?25l")

    def handle_exit(signum=None, frame=None) -> None:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            if screensaver_mode:
                stdout.write("\033[?1049l")
            stdout.write("\r\033[K\033[1F\033[K\033[?25h\0")
            stdout.flush()
            path = f"/tmp/news_run_{os.getuid()}.txt"
            with open(path, "w") as f:
                f.write(str(int(time())))
        except KeyboardInterrupt:
            pass
        except:
            pass

        if _run:
            try:
                subprocess.run(_run)
                kill_parent()
            except KeyboardInterrupt:
                pass
            except:
                pass

        os._exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGQUIT, handle_exit)
    signal.signal(signal.SIGTSTP, handle_exit)

    try:
        while True:
            stamp = monotonic()
            await main()
            for _ in range(20):
                dr, _, _ = select.select([stdin], [], [], 0)
                if dr != []:
                    buf = os.read(fd, 4096).decode(errors="ignore")
                    if (
                        buf.isalnum()
                        or len(buf) - 1
                        or ord(buf) in [4, 12]
                        or buf[0] in shortcuts.keys()
                    ) and not screensaver_mode:
                        # Do not inject if not a alphanum / Ctrl-D / Arrow key
                        shortcut_handler(buf)
                    handle_exit()
            if Onetime:
                handle_exit()
            await suspend(stamp + Time_Refresh)
    except Exception as err:
        print("\nUNHANDLED EXCEPTION!\n")
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        if screensaver_mode:
            stdout.write("\033[?1049l")
        stdout.write("\r\033[K\033[1F\033[K\033[?25h\0")
        stdout.flush()
        raise err


# .newsrc proper options

Accent = None
Accent_Secondary = None

Hush_Updates = None
Hush_Disks = None
Hush_Smart = None
Time_Tick = 0.1
Time_Refresh = 0.25
Onetime = False

shortcuts = {}

newsrc_path = os.path.expanduser("~/.newsrc")
if os.path.isfile(newsrc_path):
    with open(newsrc_path) as f:
        try:
            exec(f.read(), globals())
        except KeyboardInterrupt:
            print(
                "Ctrl-C detected while loading `~/.newsrc`, experiencing severe brain damage."
            )
        except:
            print("Exception while loading `~/.newsrc`, ignoring.")
else:  # Install and run default configuration
    try:
        with open(newsrc_path, "w") as f:
            f.write(DEFAULT_CONF)
    except:
        pass
    exec(DEFAULT_CONF, globals())

# Inject settings
try:
    if Accent is not None and isinstance(Accent, str):
        setattr(colors, "accent", Accent)
except:
    pass

try:
    if Accent_Secondary is not None and isinstance(Accent_Secondary, str):
        setattr(colors, "accent2", Accent_Secondary)
except:
    pass

if Hush_Updates is not None and isinstance(Hush_Updates, bool):
    hush_updates = Hush_Updates

if Hush_Disks is not None and isinstance(Hush_Disks, bool):
    hush_disks = Hush_Disks

if Hush_Smart is not None and isinstance(Hush_Smart, bool):
    hush_smart = Hush_Smart

if not (isinstance(Time_Tick, float) or isinstance(Time_Tick, int)):
    Time_Tick = 0.1

if not (isinstance(Time_Refresh, float) or isinstance(Time_Refresh, int)):
    Time_Refresh = 0.25

# Main event loop
if __name__ == "__main__":
    asyncio.run(loop_main())
