# Solar Hot Water — Setup Guide

## 1. Pi Setup

### 1.1 Prerequisites

The Pi should already have:
- Raspberry Pi OS (Bookworm or later)
- Python 3.11+
- DS18B20 sensors wired to GPIO pin 17 (1-wire bus)
- Pump relay on GPIO BOARD13, boiler relay on GPIO BOARD11

### 1.2 Install dependencies

```bash
sudo apt update
sudo apt install -y python3-pip python3-gpiozero
cd ~/projects/Solar
pip install -r requirements.txt
```

### 1.3 Enable 1-wire bus

Add to `/boot/firmware/config.txt` (persists across reboots):

```
dtoverlay=w1-gpio,gpiopin=17
```

Then reboot, or load immediately:

```bash
sudo dtoverlay w1-gpio gpiopin=17
sudo modprobe w1-gpio
sudo modprobe w1-therm
```

Verify sensors are detected:

```bash
ls /sys/bus/w1/devices/28-*
```

You should see three device directories (one per DS18B20).

### 1.4 Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Follow the printed URL to authenticate in a browser. Note the Pi's Tailscale IP (shown after auth, or run `tailscale ip -4`).

### 1.5 Start the app (first run)

```bash
cd ~/projects/Solar
sudo MOCK_HARDWARE=0 python3 -m app.main
```

On first run, the app prints:

```
============================================================
  INITIAL ADMIN PASSWORD: <random-string>
============================================================
```

**Save this password** — you'll need it to log in. You can change it later from the Settings tab.

Press Ctrl+C to stop. The next step sets it up to run on boot.

### 1.6 Install as systemd service (auto-start on boot)

```bash
sudo cp ~/projects/Solar/solar-hotwater.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable solar-hotwater
sudo systemctl start solar-hotwater
```

Check it's running:

```bash
sudo systemctl status solar-hotwater
```

View logs (including the initial password if you missed it):

```bash
sudo journalctl -u solar-hotwater -e
```

The service will now start automatically on every boot, and restart if it crashes.

### 1.7 Enable HTTPS (required for PWA install)

Tailscale can serve the app over HTTPS with an automatic certificate:

```bash
sudo tailscale serve --bg 8080
```

This makes the app available at `https://<pi-hostname>.<tailnet-name>.ts.net`. Find your URL:

```bash
tailscale serve status
```

### 1.8 Firewall (optional, extra hardening)

Block port 8080 from everything except Tailscale:

```bash
sudo iptables -A INPUT -i tailscale0 -p tcp --dport 8080 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j DROP

# Make persistent across reboots:
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```

---

## 2. Accessing from a Laptop

### 2.1 Install Tailscale

- **Linux**: `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`
- **macOS**: Download from https://tailscale.com/download/mac
- **Windows**: Download from https://tailscale.com/download/windows

Sign in with the **same account** you used on the Pi.

### 2.2 Open the app

In any browser, go to:

```
https://<pi-hostname>.<tailnet-name>.ts.net
```

or, using the Tailscale IP directly:

```
http://100.x.y.z:8080
```

Log in with the password from step 1.5.

---

## 3. Accessing from Android (mobile)

### 3.1 Install Tailscale

Install **Tailscale** from the Google Play Store. Sign in with the same account.

### 3.2 Open the app

Open Chrome and go to the same URL as above:

```
https://<pi-hostname>.<tailnet-name>.ts.net
```

### 3.3 Install as PWA (home screen app)

1. In Chrome, tap the three-dot menu (top right)
2. Tap **"Add to Home screen"** or **"Install app"**
3. Confirm

The app now appears on your home screen and launches in standalone mode (no browser chrome), just like a native app.

> **Note**: Tailscale must be connected for the app to reach the Pi. The Tailscale Android app runs as a VPN in the background — leave it on.

---

## 4. Sensor Replacement

If a sensor fails:

1. Wire the new DS18B20 to the same 1-wire bus (GPIO pin 17)
2. Open the app, go to **Settings > Sensors**
3. The new sensor will appear in the dropdown (detected automatically from the 1-wire bus)
4. Assign the new sensor to the correct role (Panel / Inflow / Outflow)
5. Tap **Save Sensor Config**

The change takes effect immediately — no restart needed.

---

## 5. Updating the App

After pulling new code on the Pi:

```bash
cd ~/projects/Solar
git pull  # or however you transfer files
sudo systemctl restart solar-hotwater
```

---

## 6. Troubleshooting

**App won't start:**
```bash
sudo journalctl -u solar-hotwater -n 50
```

**Sensors not detected:**
```bash
ls /sys/bus/w1/devices/28-*
# If empty, check wiring and:
sudo dtoverlay w1-gpio gpiopin=17
```

**Can't reach app from phone/laptop:**
- Confirm Tailscale is running on both devices: `tailscale status`
- Try pinging the Pi: `ping <pi-tailscale-ip>`
- Check the service is running: `sudo systemctl status solar-hotwater`

**Forgot password:**
```bash
# Reset to a new random password:
sudo systemctl stop solar-hotwater
rm ~/projects/Solar/app/solar.db
sudo systemctl start solar-hotwater
# Check journalctl for the new password
sudo journalctl -u solar-hotwater | grep PASSWORD
```
Note: this also resets schedule, alerts, and sensor assignments to defaults.

**Reset only the password (keep other settings):**
```bash
python3 -c "
import hashlib, json, sqlite3, time
new_pw = input('New password: ')
h = hashlib.sha256(new_pw.encode()).hexdigest()
conn = sqlite3.connect('$HOME/projects/Solar/app/solar.db')
conn.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
    ('password_hash', json.dumps(h), time.strftime('%Y-%m-%dT%H:%M:%S')))
conn.commit()
print('Done')
"
```
