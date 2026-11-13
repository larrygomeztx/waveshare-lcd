# Waveshare 1.44-inch LCD status display

A Raspberry Pi status display for the Waveshare 1.44-inch LCD HAT (128 x 128,
ST7735S). Use the HAT's joystick left/right directions to cycle through:

1. IPv4 address used by the default route
2. Hostname, active network interface, and that interface's MAC address
3. Wi-Fi signal strength in dBm and an approximate percentage, or a
   disconnected status
4. CPU temperature in degrees Celsius

The display refreshes its status every two seconds. The Wi-Fi page reports
wireless signal only when Wi-Fi is connected; the MAC page shows the MAC for
the interface used by the default route (which can be Ethernet).

## Hardware

- Raspberry Pi running Raspberry Pi OS / Debian
- Waveshare 1.44-inch LCD HAT, connected to the GPIO header
- SPI enabled, using SPI0 CE0 (`/dev/spidev0.0`)

The HAT uses BCM GPIO 27 (reset), 25 (data/command), 24 (backlight), and 26/5
for joystick right/left. The LCD uses SPI0 MOSI/SCLK/CE0. Avoid other hardware
that uses these pins.

## Software requirements

- Python 3
- Python modules: `gpiozero`, `lgpio`, `numpy`, `Pillow`, and `spidev`
- System tools: `ip` (`iproute2`) and `iw`
- DejaVu Sans font at `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
- User account with access to the `spi` and `gpio` groups
- systemd, if installing the boot service

`requirements.txt` lists the Python module names. On Raspberry Pi OS, use the
distribution packages below rather than installing into the system Python with
pip.

## Installation

From the Pi terminal, install the system packages:

```sh
sudo apt update
sudo apt install -y python3 python3-gpiozero python3-lgpio python3-numpy \
  python3-pil python3-spidev fonts-dejavu-core iproute2 iw
```

Enable SPI if it is not already enabled:

```sh
sudo raspi-config
```

Choose **Interface Options** (or **Interfacing Options** on older releases) →
**SPI** → **Enable**, then reboot if prompted. Confirm SPI is available:

```sh
ls -l /dev/spidev0.0
```

The account running the display needs SPI and GPIO access. Add the current
account to both groups if necessary, then log out and back in (or reboot) for
the group changes to take effect:

```sh
sudo usermod -aG spi,gpio "$USER"
```

Place `display_ip.py`, `LCD_1in44.py`, and `config.py` together in one
directory. The installed service expects them at
`/home/arista/Projects/waveshare-ip`; edit the service file if you use a
different directory or account.

## Run manually

From the project directory:

```sh
python3 display_ip.py
```

Stop the app with Ctrl+C. The LCD and GPIO resources are released on exit.

## Start automatically at boot

From the project directory, install and enable the provided systemd service:

```sh
sudo install -m 644 waveshare-ip.service /etc/systemd/system/waveshare-ip.service
sudo systemctl daemon-reload
sudo systemctl enable --now waveshare-ip.service
```

Check its status and logs:

```sh
systemctl status waveshare-ip.service
journalctl -u waveshare-ip.service -f
```

The service runs as `arista` and adds the `spi` and `gpio` supplementary
groups. Update `User`, `WorkingDirectory`, and `ExecStart` in
`waveshare-ip.service` before installing if your account or project path is
different. After editing the installed unit, run `sudo systemctl daemon-reload`
and `sudo systemctl restart waveshare-ip.service`.

To disable automatic startup:

```sh
sudo systemctl disable --now waveshare-ip.service
```

## Troubleshooting

- **LCD is blank:** check the HAT seating, SPI enablement, and `/dev/spidev0.0`.
  Check `journalctl -u waveshare-ip.service -e` for startup errors.
- **Permission denied for SPI/GPIO:** verify the service user belongs to the
  `spi` and `gpio` groups, then reboot or restart after changing membership.
- **Wi-Fi page says disconnected:** this is expected while `wlan0` is not
  connected; the page reads the connected wireless link's signal from `iw`.
- **Service does not start:** use `systemctl status waveshare-ip.service` and
  confirm the paths and user configured in the unit match the installation.

## Driver source

`LCD_1in44.py` and `config.py` are from Waveshare's Raspberry Pi demo for the
[1.44-inch LCD HAT](https://www.waveshare.com/wiki/1.44inch_LCD_HAT). The
driver source includes its license notice.
