import os
import time
import re
import winreg
from datetime import datetime

INTERVAL = 60      # секунд
ITERATIONS = 5     # 5 минут
RATE_RE = re.compile(
    r"Current download rate:\s*([\d.]+)\s*(Mbps|Kbps)",
    re.IGNORECASE
)

def get_steam_path():
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam", "InstallPath"),
    ]
    for root, key, value in keys:
        try:
            with winreg.OpenKey(root, key) as k:
                path, _ = winreg.QueryValueEx(k, value)
                if os.path.isdir(path):
                    return path
        except FileNotFoundError:
            pass
    return None

def get_current_download_rate(log_path, last_pos=0):
    """
    Ищет последнюю строку 'Current download rate' в content_log.txt

    :param log_path: путь к content_log.txt
    :return: (rate_mib_s, new_position) или (None, last_pos)
    """
    rate = None

    with open(log_path, encoding="utf-8", errors="ignore") as log:
        log.seek(last_pos)

        for line in log:
            match = RATE_RE.search(line)
            if match:
                download_rate = float(match.group(1))
                unit = match.group(2)
                if unit == 'Mbps':
                    rate = download_rate / 8  # Mbps → MiB/s
                elif unit == 'Kbps':
                    rate = download_rate / 8196  # Kbps → MiB/s
                elif unit == 'Gbps':
                    rate = download_rate * 128  # Gbps → MiB/s

        new_pos = log.tell()

    return rate, new_pos

def get_app_download_state(steamapps, appid):
    """
    Возвращает состояние игры по appmanifest_<appid>.acf
    """
    manifest = os.path.join(steamapps, f"appmanifest_{appid}.acf")
    if not os.path.isfile(manifest):
        return "Unknown"

    data = {}

    try:
        with open(manifest, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if '"' in line:
                    parts = line.strip().split('"')
                    if len(parts) >= 4:
                        data[parts[1]] = parts[3]
    except Exception:
        return "Unknown"

    if data.get("UpdateResult") == "4" and data.get("SizeOnDisk") == "0":
        return "Paused"

    if data.get("UpdateResult") == "0" and data.get("SizeOnDisk") == "0":
        return "Downloading"

    return "Unknown"

def get_game_name(steamapps, appid):
    manifest = os.path.join(steamapps, f"appmanifest_{appid}.acf")
    if not os.path.isfile(manifest):
        return f"AppID {appid}"
    try:
        with open(manifest, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        m = re.search(r'"name"\s+"(.+?)"', text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return f"AppID {appid}"

def monitor():
    steam = get_steam_path()
    if not steam:
        print(" Steam не найден")
        return

    steamapps = os.path.join(steam, "steamapps")
    downloading = os.path.join(steamapps, "downloading")
    log_path = os.path.join(steam, "logs", "content_log.txt")

    if not os.path.isdir(downloading):
        print(" Папка steamapps\\downloading не найдена")
        return

    print(f" Steam найден: {steam}")
    print("Мониторинг загрузок Steam\n")
    print("Ctrl + C для остановки\n" + "-" * 70)

    previous_sizes = {}
    try:
        for i in range(ITERATIONS):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Итерация {i+1}/{ITERATIONS}")
            log_pos = 0
            active = False
            for appid in os.listdir(downloading):
                app_path = os.path.join(downloading, appid)

                if not appid.isdigit() or not os.path.isdir(app_path):
                    continue

                status = get_app_download_state(steamapps, appid)
                game_name = get_game_name(steamapps, appid)
                if status == "Downloading":
                    speed, log_pos = get_current_download_rate(log_path, log_pos)
                else:
                    speed = 0
                print(f" {game_name}")
                print(f" {speed:.2f} MiB/s | {status}")
                active = True

            if not active:
                print(" Нет активных загрузок")

            print("-" * 70)
            time.sleep(INTERVAL)

        print("Мониторинг завершён")
    except KeyboardInterrupt:
        print("\n Остановлено пользователем")
        

if __name__ == "__main__":
    monitor()
