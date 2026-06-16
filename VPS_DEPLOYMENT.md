# VPS Deployment Guide

This guide deploys the MQTT broker and real-time dashboard on `157.173.101.159` using the account `user218`.

> Never place the SSH password or MQTT passwords in source code, Git, screenshots, or commands. Type the SSH password only at the terminal prompt. Use different passwords for SSH, `pc_publisher`, and `dashboard_reader`.

## 1. Connect and check permissions

From PowerShell or the VS Code terminal:

```powershell
ssh user218@157.173.101.159
```

After login:

```bash
whoami
sudo -v
```

The recommended deployment needs `sudo` for Mosquitto, Nginx, systemd, the firewall, and ports below 1024. If `sudo -v` is denied, ask the VPS administrator to perform the system-level steps.

## 2. Install the server packages

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients nginx python3 python3-venv python3-pip ufw
```

## 3. Upload the dashboard folder

Run this on the Windows PC from the project root:

```powershell
scp -r .\vps_dashboard user218@157.173.101.159:~/temperature-dashboard
```

Then reconnect and verify:

```bash
ssh user218@157.173.101.159
cd ~/temperature-dashboard
ls
```

## 4. Create the two MQTT accounts

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd pc_publisher
sudo mosquitto_passwd /etc/mosquitto/passwd dashboard_reader
sudo chown root:mosquitto /etc/mosquitto/passwd
sudo chmod 640 /etc/mosquitto/passwd
```

Use two different MQTT passwords:

- Put the `pc_publisher` password in `pc_monitor/.env` on the PC.
- Put the `dashboard_reader` password in `~/temperature-dashboard/.env` on the VPS.

## 5. Configure Mosquitto

```bash
cd ~/temperature-dashboard
sudo cp deploy/mosquitto-temperature.conf /etc/mosquitto/conf.d/temperature.conf
sudo cp deploy/mosquitto-acl /etc/mosquitto/acl
sudo chown root:mosquitto /etc/mosquitto/acl
sudo chmod 640 /etc/mosquitto/acl
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
```

Confirm that port 1883 is listening:

```bash
sudo ss -ltnp | grep 1883
```

## 6. Test MQTT locally on the VPS

In SSH terminal 1:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -u dashboard_reader -P 'DASHBOARD_READER_PASSWORD' \
  -t 'rca/hitayezu-frank-duff/temperature' -v
```

In SSH terminal 2:

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -u pc_publisher -P 'PC_PUBLISHER_PASSWORD' \
  -t 'rca/hitayezu-frank-duff/temperature' \
  -q 1 -r \
  -m '{"device":"arduino-uno-dht11","sensor":"DHT11","student":"HITAYEZU Frank Duff","temperature":25.0,"unit":"C","timestamp":"2026-06-16T12:00:00Z"}'
```

Terminal 1 should receive the JSON message.

## 7. Install the dashboard application

```bash
cd ~/temperature-dashboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set the dashboard MQTT password:

```env
HOST=127.0.0.1
PORT=3000

MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=dashboard_reader
MQTT_PASSWORD=REPLACE_WITH_DASHBOARD_READER_PASSWORD
MQTT_TOPIC=rca/hitayezu-frank-duff/temperature
```

Protect the file and test the app:

```bash
chmod 600 .env
python app.py
```

From a second SSH terminal:

```bash
curl http://127.0.0.1:3000/health
```

Stop the manual Flask server with `Ctrl+C` before starting systemd.

## 8. Run the dashboard using systemd

The provided service file is configured for `user218` and `/home/user218/temperature-dashboard`.

```bash
cd ~/temperature-dashboard
sudo cp deploy/temperature-dashboard.service /etc/systemd/system/temperature-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now temperature-dashboard
sudo systemctl status temperature-dashboard --no-pager
```

View logs:

```bash
sudo journalctl -u temperature-dashboard -f
```

## 9. Configure Nginx

```bash
cd ~/temperature-dashboard
sudo cp deploy/nginx-temperature-dashboard.conf /etc/nginx/sites-available/temperature-dashboard
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/temperature-dashboard /etc/nginx/sites-enabled/temperature-dashboard
sudo nginx -t
sudo systemctl reload nginx
```

## 10. Open the firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
sudo ufw status
```

A provider firewall or security group may also need inbound TCP ports `22`, `80`, and `1883`.

## 11. Open and test the dashboard

Open:

```text
http://157.173.101.159
```

On the PC, configure `pc_monitor/.env`, close Arduino Serial Monitor, and run:

```powershell
python monitor.py
```

The dashboard should update after the PC publishes the first DHT11 reading.

## 12. Useful diagnostics

```bash
sudo systemctl status mosquitto --no-pager
sudo systemctl status temperature-dashboard --no-pager
sudo systemctl status nginx --no-pager
sudo journalctl -u mosquitto -n 100 --no-pager
sudo journalctl -u temperature-dashboard -n 100 --no-pager
sudo nginx -t
curl http://127.0.0.1:3000/health
```

## 13. Temporary user-only dashboard test

This fallback does not install Mosquitto, Nginx, or systemd. It is only useful when an administrator has already provided an MQTT broker and opened a suitable application port.

```bash
cd ~/temperature-dashboard
source .venv/bin/activate
nohup gunicorn --workers 1 --threads 4 --bind 0.0.0.0:3000 --timeout 0 app:app > dashboard.log 2>&1 &
```

The dashboard would then be reached at `http://157.173.101.159:3000` only if TCP port 3000 is permitted. The recommended final setup is still Nginx on port 80 with the systemd service.
