import signal
import socket
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import LCD_1in44


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")
PAGE_TITLES = ("IP ADDRESS", "HOSTNAME / MAC", "WI-FI SIGNAL", "CPU TEMP")


def get_network_info():
    result = subprocess.run(
        ["ip", "-4", "route", "get", "1.1.1.1"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "No network", "No link", "Unavailable"

    fields = result.stdout.split()
    try:
        ip_address = fields[fields.index("src") + 1]
        interface = fields[fields.index("dev") + 1]
    except (ValueError, IndexError) as error:
        raise RuntimeError(f"Could not determine the Pi's network details: {result.stdout}") from error

    mac_address = Path(f"/sys/class/net/{interface}/address").read_text().strip().upper()
    return ip_address, interface, mac_address


def get_wifi_signal():
    result = subprocess.run(["iw", "dev"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return "Unavailable", None

    interfaces = [
        line.strip().split(maxsplit=1)[1]
        for line in result.stdout.splitlines()
        if line.strip().startswith("Interface ")
    ]
    if not interfaces:
        return "Unavailable", None

    for interface in interfaces:
        link = subprocess.run(
            ["iw", "dev", interface, "link"],
            capture_output=True,
            text=True,
            check=False,
        )
        if link.returncode != 0 or "Connected to " not in link.stdout:
            continue

        for line in link.stdout.splitlines():
            fields = line.split()
            if fields and fields[0] == "signal:":
                return interface, float(fields[1])
        raise RuntimeError(f"Wi-Fi is connected but its signal level was not reported: {link.stdout}")

    return interfaces[0], None


def get_status():
    ip_address, interface, mac_address = get_network_info()
    wifi_interface, signal_dbm = get_wifi_signal()
    temperature = int(THERMAL_ZONE.read_text().strip()) / 1000
    return {
        "ip": ip_address,
        "hostname": socket.gethostname(),
        "interface": interface,
        "mac": mac_address,
        "wifi_interface": wifi_interface,
        "wifi_signal": signal_dbm,
        "temperature": temperature,
    }


def fitting_font(draw, text, font_path, size, max_width):
    while size > 8:
        font = ImageFont.truetype(font_path, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 1
    return ImageFont.truetype(font_path, 8)


def draw_centered(draw, text, y, font, fill, width):
    bounds = draw.textbbox((0, 0), text, font=font)
    x = (width - (bounds[2] - bounds[0])) // 2 - bounds[0]
    draw.text((x, y), text, font=font, fill=fill)


def make_screen(page, status, width, height):
    image = Image.new("RGB", (width, height), "#101827")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(FONT_BOLD, 11)
    small_font = ImageFont.truetype(FONT, 9)

    draw.rectangle((0, 0, width - 1, 4), fill="#27c6da")
    draw_centered(draw, PAGE_TITLES[page], 17, title_font, "#ffffff", width)

    if page == 0:
        value = status["ip"]
        font = fitting_font(draw, value, FONT_BOLD, 16, width - 12)
        draw_centered(draw, value, 61, font, "#75e39a", width)
    elif page == 1:
        hostname = status["hostname"]
        host_font = fitting_font(draw, hostname, FONT_BOLD, 13, width - 12)
        mac_font = fitting_font(draw, status["mac"], FONT, 10, width - 12)
        draw_centered(draw, hostname, 44, host_font, "#75e39a", width)
        draw_centered(draw, status["interface"], 70, small_font, "#aab7ca", width)
        draw_centered(draw, status["mac"], 87, mac_font, "#ffffff", width)
    elif page == 2:
        signal_dbm = status["wifi_signal"]
        if signal_dbm is None:
            draw_centered(draw, "Disconnected", 55, title_font, "#f2bd6b", width)
            draw_centered(draw, status["wifi_interface"], 76, small_font, "#aab7ca", width)
        else:
            percentage = max(0, min(100, round((signal_dbm + 100) * 2)))
            draw_centered(draw, f"{signal_dbm:.0f} dBm", 48, title_font, "#75e39a", width)
            draw_centered(draw, f"{percentage}%", 68, small_font, "#ffffff", width)
            for bar in range(5):
                bar_height = 8 + bar * 5
                color = "#27c6da" if percentage >= (bar + 1) * 20 else "#354256"
                x = 35 + bar * 12
                draw.rectangle(
                    (x, 108 - bar_height, x + 7, 108),
                    fill=color,
                )
    else:
        value = f"{status['temperature']:.1f} C"
        font = fitting_font(draw, value, FONT_BOLD, 22, width - 12)
        draw_centered(draw, value, 55, font, "#75e39a", width)

    draw.text((8, height - 14), "L/R", font=small_font, fill="#aab7ca")
    draw.text((width - 22, height - 14), f"{page + 1}/4", font=small_font, fill="#aab7ca")
    return image


def stop_on_sigterm(_signum, _frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    lcd = LCD_1in44.LCD()
    initialized = False
    try:
        lcd.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
        initialized = True
        page = 0
        previous_left = False
        previous_right = False
        last_navigation = 0.0
        next_refresh = 0.0
        screen_dirty = True

        while True:
            now = time.monotonic()
            left_pressed = lcd.digital_read(lcd.GPIO_KEY_LEFT_PIN) == 1
            right_pressed = lcd.digital_read(lcd.GPIO_KEY_RIGHT_PIN) == 1

            if now - last_navigation >= 0.25:
                if left_pressed and not previous_left:
                    page = (page - 1) % len(PAGE_TITLES)
                    last_navigation = now
                    screen_dirty = True
                elif right_pressed and not previous_right:
                    page = (page + 1) % len(PAGE_TITLES)
                    last_navigation = now
                    screen_dirty = True

            previous_left = left_pressed
            previous_right = right_pressed

            if screen_dirty or now >= next_refresh:
                status = get_status()
                lcd.LCD_ShowImage(make_screen(page, status, lcd.width, lcd.height), 0, 0)
                print(f"Showing page: {PAGE_TITLES[page]}", flush=True)
                screen_dirty = False
                next_refresh = now + 2

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        if initialized:
            lcd.module_exit()


if __name__ == "__main__":
    main()
