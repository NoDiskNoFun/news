#!/usr/bin/python3

try:
    import os
    from sys import exit, stdin, stdout, argv
    from time import monotonic, time

    hush_login_path = os.path.expanduser("~/.hush_login")
    if os.path.isfile(hush_login_path) or not stdin.isatty():
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
    hush_news = (not os.geteuid()) or os.path.isfile(hush_news_path)
    hush_updates = (not os.geteuid()) or os.path.isfile(hush_updates_path)
    hush_disks = (not os.geteuid()) or os.path.isfile(hush_disks_path)

    import asyncio, platform, psutil, socket, json
    import signal, shutil, termios, tty, select, fcntl
    from collections import Counter
    from pathlib import Path
    from datetime import datetime, timedelta
except KeyboardInterrupt:
    import os

    os._exit(0)


CACHE_FILE = "/tmp/news_cache.json"
printed_lines = 0


def refresh_lines(new_lines: list[str]) -> None:
    global printed_lines

    physical_lines = []
    buf = ""

    for chunk in new_lines:
        buf += chunk
        while True:
            nl_pos = buf.find("\n")
            if nl_pos == -1:
                break
            # Append substring up to newline (excluding '\n')
            physical_lines.append(buf[:nl_pos])
            buf = buf[nl_pos + 1 :]

    # Append remainder if any (no trailing newline)
    if buf:
        physical_lines.append(buf)

    new_physical_lines = len(physical_lines)

    # Clear previous physical lines
    for _ in range(printed_lines):
        stdout.write("\x1b[1A\x1b[2K")

    # Print the new physical lines exactly as-is
    for pline in physical_lines:
        print(pline)

    # Clear leftovers if we previously printed more lines
    if printed_lines > new_physical_lines:
        for _ in range(printed_lines - new_physical_lines):
            print("\x1b[2K")

    printed_lines = new_physical_lines


sbc_list = [
    "ArmSoM AIM7 ",
    "ArmSoM Sige7",
    "ArmSoM W3",
    "Banana Pi M7",
    "Embedfire LubanCat-4",
    "Firefly AIO-3588L MIPI101(Linux)",
    "Firefly ITX-3588J HDMI(Linux)",
    "FriendlyElec CM3588",
    "FriendlyElec NanoPC-T6",
    "FriendlyElec NanoPC-T6 LTS",
    "FriendlyElec NanoPi R6C",
    "FriendlyElec NanoPi R6S",
    "Fxblox RK1",
    "Fydetab Duo",
    "HINLINK H88K",
    "Indiedroid Nova",
    "Khadas Edge2",
    "Mekotronics R58 MiniPC (RK3588 MINIPC LP4x V1.0 BlueBerry Board)",
    "Mekotronics R58X (RK3588 EDGE LP4x V1.0 BlueBerry Board)",
    "Mekotronics R58X-4G (RK3588 EDGE LP4x V1.2 BlueBerry Board)",
    "Mixtile Blade 3",
    "Mixtile Blade 3 v1.0.1",
    "Mixtile Core 3588E",
    "Orange Pi 5",
    "Orange Pi 5 Ultra" "Orange Pi 5 Max",
    "Orange Pi 5 Plus",
    "Orange Pi 5 Pro",
    "Orange Pi 5 Max",
    "Orange Pi 5 Ultra",
    "Orange Pi 5B",
    "Orange Pi CM5",
    "RK3588 CoolPi CM5 EVB Board",
    "RK3588 CoolPi CM5 NoteBook Board",
    "RK3588 EDGE LP4x V1.2 MeiZhuo BlueBerry Board",
    "RK3588 EDGE LP4x V1.4 BlueBerry Board",
    "RK3588 MINIPC-MIZHUO LP4x V1.0 BlueBerry Board",
    "RK3588S CoolPi 4B Board",
    "ROC-RK3588S-PC V12(Linux)",
    "Radxa CM5 IO",
    "Radxa CM5 RPI CM4 IO",
    "Radxa NX5 IO",
    "Radxa NX5 Module",
    "Radxa ROCK 5 ITX",
    "Radxa ROCK 5A",
    "Radxa ROCK 5B",
    "Radxa ROCK 5B Plus",
    "Radxa ROCK 5C",
    "Radxa ROCK 5D",
    "Rockchip RK3588",
    "Rockchip RK3588 EVB1 LP4 V10 Board",
    "Rockchip RK3588 EVB1 LP4 V10 Board + DSI DSC PANEL MV2100UZ1 DISPLAY Ext Board",
    "Rockchip RK3588 EVB1 LP4 V10 Board + RK Ext HDMImale to eDP V10",
    "Rockchip RK3588 EVB1 LP4 V10 Board + RK HDMI to DP Ext Board",
    "Rockchip RK3588 EVB1 LP4 V10 Board + RK3588 EDP 8LANES V10 Ext Board",
    "Rockchip RK3588 EVB1 LP4 V10 Board + Rockchip RK3588 EVB V10 Extboard",
    "Rockchip RK3588 EVB1 LP4 V10 Board + Rockchip RK628 HDMI to MIPI Extboard",
    "Rockchip RK3588 EVB2 LP4 V10 Board",
    "Rockchip RK3588 EVB2 LP4 V10 eDP Board",
    "Rockchip RK3588 EVB2 LP4 V10 eDP to DP Board",
    "Rockchip RK3588 EVB3 LP5 V10 Board",
    "Rockchip RK3588 EVB3 LP5 V10 EDP Board",
    "Rockchip RK3588 EVB4 LP4 V10 Board",
    "Rockchip RK3588 EVB6 LP4 V10 Board",
    "Rockchip RK3588 EVB7 LP4 V10 Board",
    "Rockchip RK3588 EVB7 LP4 V11 Board",
    "Rockchip RK3588 EVB7 V11 Board",
    "Rockchip RK3588 EVB7 V11 Board + Rockchip RK628 HDMI to MIPI Extboard",
    "Rockchip RK3588 NVR DEMO LP4 SPI NAND Board",
    "Rockchip RK3588 NVR DEMO LP4 V10 Android Board",
    "Rockchip RK3588 NVR DEMO LP4 V10 Board",
    "Rockchip RK3588 NVR DEMO1 LP4 V21 Android Board",
    "Rockchip RK3588 NVR DEMO1 LP4 V21 Board",
    "Rockchip RK3588 NVR DEMO3 LP4 V10 Android Board",
    "Rockchip RK3588 NVR DEMO3 LP4 V10 Board",
    "Rockchip RK3588 PCIE EP Demo V11 Board",
    "Rockchip RK3588 TOYBRICK LP4 X10 Board",
    "Rockchip RK3588 TOYBRICK X10 Board",
    "Rockchip RK3588 VEHICLE EVB V10 Board",
    "Rockchip RK3588 VEHICLE EVB V20 Board",
    "Rockchip RK3588 VEHICLE EVB V21 Board",
    "Rockchip RK3588 VEHICLE EVB V22 Board",
    "Rockchip RK3588 VEHICLE S66 Board V10",
    "Rockchip RK3588-RK1608 EVB7 LP4 V10 Board",
    "Rockchip RK3588J",
    "Rockchip RK3588M",
    "Rockchip RK3588S",
    "Rockchip RK3588S EVB1 LP4X V10 Board",
    "Rockchip RK3588S EVB2 LP5 V10 Board",
    "Rockchip RK3588S EVB3 LP4 V10 Board + Rockchip RK3588S EVB V10 Extboard",
    "Rockchip RK3588S EVB3 LP4 V10 Board + Rockchip RK3588S EVB V10 Extboard1",
    "Rockchip RK3588S EVB3 LP4 V10 Board + Rockchip RK3588S EVB V10 Extboard2",
    "Rockchip RK3588S EVB3 LP4X V10 Board",
    "Rockchip RK3588S EVB4 LP4X V10 Board",
    "Rockchip RK3588S EVB8 LP4X V10 Board",
    "Rockchip RK3588S TABLET RK806 SINGLE Board",
    "Rockchip RK3588S TABLET V10 Board",
    "Rockchip RK3588S TABLET V11 Board",
    "Turing Machines RK1",
]


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


def get_active_ipv4_interfaces() -> dict:
    active_interfaces = {}
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if (
                addr.family == socket.AF_INET
                and addr.address != "127.0.0.1"
                and not iface.startswith(("br-", "docker", "virbr"))
            ):
                active_interfaces[iface] = addr.address
    return active_interfaces


async def get_system_info() -> dict:
    hostname = platform.node()
    os_info = f"GNU/Linux {platform.release()} {platform.machine()}"

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

    cpu_model = None

    with open("/proc/cpuinfo", "r") as f:
        cpuinfo = f.read()
        cpuinfo = cpuinfo.splitlines()

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

    with open("/proc/loadavg") as f:
        load_avg = f.read().split()[0]

    with open("/proc/stat") as f:
        processes = sum(1 for line in f if line.startswith("processes"))

    disk_usage = os.statvfs("/")
    total_space = disk_usage.f_frsize * disk_usage.f_blocks / (1024**3)  # GB
    used_space = (
        (disk_usage.f_blocks - disk_usage.f_bfree) * disk_usage.f_frsize / (1024**3)
    )  # GB
    usage_percent = (used_space / total_space) * 100

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
        "disk_usage": f"{usage_percent:.1f}% of {total_space:.2f}GB",
        "logged_in_users": logged_in_users,
        "memory_usage": f"{mem_usage_percent:.1f}%",
        "net_ifs": net_ifs,
        "swap_usage": (
            f"{swap_usage_percent:.1f}%" if swap_usage_percent is not None else None
        ),
    }


async def get_service_statuses(command: str):
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
    user_statuses = await get_service_statuses(
        "systemctl --user list-units --type=service --no-legend --no-pager | awk '{print $4}'"
    )

    total_statuses = system_statuses + user_statuses
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
            timestamp = data.get("timestamp")
            smart = data.get("smart")
            msgs = []

            if shutil.which("checkupdates") is None:
                msgs.append(
                    "Install `pacman-contrib` to view available updates during login.\n"
                )
            if shutil.which("yay") is None:
                msgs.append(
                    "Install `yay` to view development package updates during login.\n"
                )
            ago = time_ago(timestamp)

            return [
                updates,
                devel_updates,
                news,
                [f"{colors.bland_t}(Latest check was {ago}){colors.endc}"] + msgs,
                smart,
            ]
    except:
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
    return (" " * (collumns - len(current_str) + 2)) + "   "


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


async def main() -> None:
    info_task = get_system_info()
    services_task = count_failed_systemd()
    updates_task = get_updates()

    device = None
    sbc_declared = detect_install_device()
    if sbc_declared in sbc_list:
        device = sbc_declared

    system_info = await info_task
    msg = []

    msg.append(
        f"{colors.yellow_t if os.geteuid() else colors.red_t}{colors.bold}Welcome to BredOS{colors.endc} ({system_info['os_info']})\n"
    )
    msg.append(
        f"{colors.yellow_t if os.geteuid() else colors.red_t}{colors.bold}\n*{colors.endc} Documentation:  https://wiki.bredos.org/\n"
    )
    msg.append(
        f"{colors.yellow_t if os.geteuid() else colors.red_t}{colors.bold}*{colors.endc} Support:        https://discord.gg/beSUnWGVH2\n\n"
    )

    device_str = ""
    if device is not None:
        device_str += f"{colors.okblue if os.geteuid() else colors.red_t}Device:{colors.endc} {device}"

    hostname_str = f"{colors.okblue if os.geteuid() else colors.red_t}Hostname:{colors.endc} {system_info['hostname']}"

    uptime_str = f"{colors.okblue if os.geteuid() else colors.red_t}Uptime:{colors.endc} {system_info['uptime']}"
    logged_str = f"{colors.okblue if os.geteuid() else colors.red_t}Users logged in:{colors.endc} {system_info['logged_in_users']}"

    cpu_str = f"{colors.okblue if os.geteuid() else colors.red_t}CPU:{colors.endc} {system_info['cpu_model']} ({system_info['cpu_count']}c, {system_info['cpu_threads']}t)"
    load_str = f"{colors.okblue if os.geteuid() else colors.red_t}System load:{colors.endc} {system_info['system_load']}"

    memory_str = f"{colors.okblue if os.geteuid() else colors.red_t}Memory:{colors.endc} {system_info['memory_usage']} of {system_info['total_memory']} used"

    swap_str = ""
    upd_str = ""

    if system_info["swap_usage"] is not None:
        swap_str = f"{colors.okblue if os.geteuid() else colors.red_t}Swap usage:{colors.endc} {system_info['swap_usage']}"

    collumns = max(len(device_str), len(uptime_str), len(cpu_str), len(memory_str))

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
    msg.append(swap_str + "\n")

    usage_str = f"{colors.okblue if os.geteuid() else colors.red_t}Usage of /:{colors.endc} {system_info['disk_usage']}"
    msg.append(usage_str)
    splitter = True
    last = usage_str
    for netname, ip in system_info["net_ifs"].items():
        if splitter:
            msg.append(seperator(last, collumns))
        last = f"{colors.okblue if os.geteuid() else colors.red_t}{netname}:{colors.endc} {ip}"
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
                upd_str = f"\n{colors.bold}{colors.cyan_t}{updates[0]} updates available.{colors.endc}\n"
            elif updates[0] and updates[1]:
                upd_str = f"\n{colors.bold}{colors.cyan_t}{updates[0] + updates[1]} updates available, of which {updates[1]} are development packages.{colors.endc}\n"
            elif updates[1]:
                upd_str = f"\n{colors.bold}{colors.cyan_t}{updates[1]} development updates available.{colors.endc}\n"
            else:
                upd_str = f"\n{colors.green_t}You are up to date!{colors.endc}\n"
            for i in updates[3]:
                upd_str += i + "\n"
        elif isinstance(updates, str):
            upd_str = updates

        if upd_str:
            msg.append(upd_str + "\n")

    if not hush_news:
        if hush_updates:
            msg.append("\n")
        if isinstance(updates, list):
            news = updates[2]
            msg += [news if news else "Failed to fetch news.", "\n"]
        else:
            msg.append("Failed to fetch news.")

    show_url = False
    if not hush_disks:
        if isinstance(updates[4], dict):
            for drive in updates[4].keys():
                state = updates[4][drive]
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
            f"{colors.bold}{colors.green_t}System is operating normally.{colors.endc}\n"
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

    msg.append(f"\n{colors.bland_t}[Press any key to enter the shell]{colors.endc}")
    refresh_lines(msg)


async def loop_main() -> None:
    # This is some whacko ass code.

    fd = stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    stdout.write("\033[?25l")

    def handle_exit(signum=None, frame=None) -> None:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        stdout.write("\r\033[K\033[1F\033[K\033[?25h")
        stdout.flush()
        path = f"/tmp/news_run_{os.getuid()}.txt"
        with open(path, "w") as f:
            f.write(str(int(time())))
        os._exit(0)

    signal.signal(signal.SIGINT, handle_exit)

    while True:
        await main()
        for _ in range(20):
            dr, _, _ = select.select([stdin], [], [], 0)
            if dr != []:
                key = stdin.read(1)
                if key != "\n":
                    fcntl.ioctl(stdin, termios.TIOCSTI, key.encode())
                handle_exit()
            await asyncio.sleep(0.04)


if __name__ == "__main__":
    asyncio.run(loop_main())
