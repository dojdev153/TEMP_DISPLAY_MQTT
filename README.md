# Arduino DHT11 Temperature Monitor with I2C LCD, USB Serial, MQTT and VPS Dashboard

**Student:** HITAYEZU Frank Duff  
**Arduino:** Arduino Uno  
**Temperature sensor:** DHT11 three-pin module  
**VPS login:** `user218@157.173.101.159`  
**MQTT topic:** `rca/hitayezu-frank-duff/temperature`

> Security rule: never save the VPS SSH password or MQTT passwords in this repository, screenshots, source code, or `.env.example` files. Enter the SSH password only when the SSH/SCP command asks for it.

## 1. Project objective

The Arduino Uno reads temperature from a DHT11 sensor connected to digital pin D2. A 16x2 I2C LCD displays:

- Row 1: `HITAYEZU Frank Duff`, scrolling horizontally because it is longer than 16 characters.
- Row 2: the latest temperature in degrees Celsius.

The Arduino sends each valid reading to a PC through the USB serial connection. A Python PC application displays the reading in real time and publishes it as JSON to a Mosquitto MQTT broker on the VPS. A Flask dashboard on the VPS subscribes to the MQTT topic and streams updates to a browser through Server-Sent Events (SSE).

## 2. System architecture

```text
DHT11 temperature sensor
        |
        | digital data signal on Arduino D2
        v
Arduino Uno ---- I2C ----> 16x2 LCD
        |
        | USB serial: 9600 baud, 8N1, TEMP:<value>\n
        v
PC Python monitor
        |
        | MQTT 3.1.1, QoS 1, retained JSON
        v
Mosquitto broker on 157.173.101.159:1883
        |
        v
Flask dashboard -> SSE -> Nginx -> Web browser
```

The visual system architecture and wiring diagram are in:

```text
docs/system_architecture_and_wiring.pdf
```

## 3. Hardware required

- Arduino Uno
- DHT11 three-pin sensor module labeled `S`, `VCC`/middle, and `-`
- 16x2 LCD with four-pin I2C backpack
- Seven jumper wires
- USB cable between the Arduino and PC

## 4. Seven-wire connection

Disconnect the Arduino USB cable while making connections.

### 4.1 DHT11 to Arduino Uno - three wires

| Wire | DHT11 pin | Arduino Uno pin | Purpose |
|---:|---|---|---|
| 1 | `S` signal | `D2` | Digital temperature data |
| 2 | Middle pin / `VCC` | `5V` | Sensor power |
| 3 | `-` / `GND` | `GND` | Ground |

This wiring assumes the supplied DHT11 is a three-pin module. A bare four-pin DHT11 normally needs a pull-up resistor and uses a different physical pin arrangement.

### 4.2 I2C LCD backpack to Arduino Uno - four wires

| Wire | LCD backpack pin | Arduino Uno pin | Purpose |
|---:|---|---|---|
| 4 | `GND` | `GND` | Ground |
| 5 | Supply pin identified by the kit as `VSS (VCC)` | `5V` | LCD power |
| 6 | `SDA` | `A4` / `SDA` | I2C data |
| 7 | `SCL` | `A5` / `SCL` | I2C clock |

**Important:** Standard I2C backpacks normally label their positive supply pin `VCC` or `VDD`; `VSS` usually means ground. Before applying power, verify that the pin your kit calls `VSS (VCC)` is truly the positive supply pin specified by your instructor or module documentation.

## 5. Project structure

```text
embedded_temperature_mqtt/
├── arduino/
│   ├── temperature_lcd/
│   │   └── temperature_lcd.ino
│   └── i2c_scanner/
│       └── i2c_scanner.ino
├── pc_monitor/
│   ├── .env.example
│   ├── monitor.py
│   └── requirements.txt
├── vps_dashboard/
│   ├── .env.example
│   ├── app.py
│   ├── requirements.txt
│   ├── templates/
│   │   └── index.html
│   └── deploy/
│       ├── mosquitto-acl
│       ├── mosquitto-temperature.conf
│       ├── nginx-temperature-dashboard.conf
│       ├── temperature-dashboard.service
│       └── test-publish.sh
├── docs/
│   └── system_architecture_and_wiring.pdf
├── README.md
└── VPS_DEPLOYMENT.md
```

## 6. Arduino setup

### 6.1 Install required Arduino libraries

In Arduino IDE, open **Sketch -> Include Library -> Manage Libraries** and install:

1. `LiquidCrystal I2C`
2. `DHT sensor library` by Adafruit
3. `Adafruit Unified Sensor` if Library Manager does not install it automatically

### 6.2 Upload the Arduino program

1. Open `arduino/temperature_lcd/temperature_lcd.ino`.
2. Connect the Arduino to the PC using USB.
3. Select **Tools -> Board -> Arduino Uno**.
4. Select the correct Arduino port under **Tools -> Port**.
5. Click **Verify** and then **Upload**.
6. Open **Tools -> Serial Monitor**.
7. Set the baud rate to `9600`.

Expected serial output:

```text
STATUS:Arduino DHT11 temperature monitor started
TEMP:25.00
TEMP:25.00
TEMP:26.00
```

If the sensor cannot be read, the Arduino displays `Sensor error` and sends:

```text
ERROR:DHT11_READ_FAILED
```

The DHT11 is read once every two seconds. The name scrolls independently every 350 milliseconds.

### 6.3 LCD troubleshooting

- If the backlight is on but text is invisible, slowly adjust the contrast potentiometer on the I2C backpack.
- If the LCD remains blank, change the address in the sketch from `0x27` to `0x3F`.
- Run `arduino/i2c_scanner/i2c_scanner.ino` to discover the actual I2C address.

### 6.4 DHT11 troubleshooting

- Confirm `S -> D2`, middle/VCC -> `5V`, and `- -> GND`.
- Do not connect the DHT11 signal pin to A0; this project uses the digital D2 pin.
- Do not read the sensor more frequently than the sketch already does.
- If every read fails, test the sensor using **File -> Examples -> DHT sensor library -> DHTtester** and set the sensor type to `DHT11`.

## 7. Serial communication between Arduino and PC

The USB cable creates a virtual serial port such as `COM3` on Windows.

| Setting | Value |
|---|---|
| Baud rate | `9600` bits per second |
| Data bits | `8` |
| Parity | None |
| Stop bits | `1` |
| Flow control | None |
| Encoding | ASCII-compatible text |
| End of message | Newline `\n` |
| Valid temperature format | `TEMP:<number>` |
| Example | `TEMP:25.00` |

This serial configuration is called **9600 8N1**.

The PC application ignores status and error lines and publishes only valid lines beginning with `TEMP:`.

## 8. PC monitoring and MQTT publishing

### 8.1 Create the Python environment

Open PowerShell in the project directory:

```powershell
cd embedded_temperature_mqtt\pc_monitor
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

### 8.2 Find the Arduino COM port

```powershell
python -m serial.tools.list_ports
```

You can also check **Tools -> Port** in Arduino IDE.

### 8.3 Configure `pc_monitor/.env`

```env
SERIAL_PORT=COM3
SERIAL_BAUD_RATE=9600

MQTT_HOST=157.173.101.159
MQTT_PORT=1883
MQTT_USERNAME=pc_publisher
MQTT_PASSWORD=REPLACE_WITH_PC_PUBLISHER_PASSWORD
MQTT_TOPIC=rca/hitayezu-frank-duff/temperature
```

Replace `COM3` with the actual Arduino port. The MQTT password is created later on the VPS and is different from the SSH password.

### 8.4 Run the PC program

Close Arduino Serial Monitor first; otherwise it may keep the COM port busy.

```powershell
python monitor.py
```

Expected output:

```text
[MQTT] Connected to 157.173.101.159:1883
[2026-06-16 14:22:06] Temperature:  25.00 °C -> MQTT published (mid=1)
```

## 9. MQTT communication

| Item | Value |
|---|---|
| Broker host | `157.173.101.159` |
| Broker port | `1883` |
| Protocol | MQTT 3.1.1 |
| Topic | `rca/hitayezu-frank-duff/temperature` |
| Publisher account | `pc_publisher` |
| Dashboard account | `dashboard_reader` |
| QoS | `1` |
| Retained message | Yes |
| Payload | JSON |

Example JSON payload:

```json
{
  "device": "arduino-uno-dht11",
  "sensor": "DHT11",
  "student": "HITAYEZU Frank Duff",
  "temperature": 25.0,
  "unit": "C",
  "timestamp": "2026-06-16T12:22:06.532019+00:00"
}
```

A retained message lets a newly opened dashboard receive the most recent reading immediately.

## 10. VPS deployment using `user218`

The same commands are also available as a separate checklist in `VPS_DEPLOYMENT.md`.

### 10.1 Connect by SSH

From PowerShell or the VS Code terminal:

```powershell
ssh user218@157.173.101.159
```

Enter the SSH password only when prompted. Do not add it to the command.

After connecting, check whether the account has sudo rights:

```bash
whoami
sudo -v
```

The full deployment below requires `sudo` because Mosquitto, Nginx, systemd services, port 80, and the firewall are system resources. If `user218` is not sudo-enabled, ask the VPS administrator to run the commands marked with `sudo` or grant the required access.

### 10.2 Install server packages

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients nginx python3 python3-venv python3-pip ufw
```

### 10.3 Upload the dashboard project

Run this from Windows PowerShell in the project root, not from inside the SSH session:

```powershell
scp -r .\vps_dashboard user218@157.173.101.159:~/temperature-dashboard
```

Reconnect to the VPS and verify:

```bash
ssh user218@157.173.101.159
cd ~/temperature-dashboard
ls
```

### 10.4 Create MQTT users

Create two MQTT accounts with two different passwords:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd pc_publisher
sudo mosquitto_passwd /etc/mosquitto/passwd dashboard_reader
sudo chown root:mosquitto /etc/mosquitto/passwd
sudo chmod 640 /etc/mosquitto/passwd
```

- Put the `pc_publisher` password in `pc_monitor/.env` on the PC.
- Put the `dashboard_reader` password in `~/temperature-dashboard/.env` on the VPS.
- Do not use the SSH password as either MQTT password.

### 10.5 Configure Mosquitto

```bash
cd ~/temperature-dashboard
sudo cp deploy/mosquitto-temperature.conf /etc/mosquitto/conf.d/temperature.conf
sudo cp deploy/mosquitto-acl /etc/mosquitto/acl
sudo chown root:mosquitto /etc/mosquitto/acl
sudo chmod 640 /etc/mosquitto/acl
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
sudo systemctl status mosquitto --no-pager
```

Check the listener:

```bash
sudo ss -ltnp | grep 1883
```

### 10.6 Test MQTT on the VPS

Terminal 1:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -u dashboard_reader -P 'DASHBOARD_READER_PASSWORD' \
  -t 'rca/hitayezu-frank-duff/temperature' -v
```

Terminal 2:

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -u pc_publisher -P 'PC_PUBLISHER_PASSWORD' \
  -t 'rca/hitayezu-frank-duff/temperature' \
  -q 1 -r \
  -m '{"device":"arduino-uno-dht11","sensor":"DHT11","student":"HITAYEZU Frank Duff","temperature":25.0,"unit":"C","timestamp":"2026-06-16T12:00:00Z"}'
```

Terminal 1 should receive the JSON.

### 10.7 Install the dashboard Python environment

```bash
cd ~/temperature-dashboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set:

```env
HOST=127.0.0.1
PORT=3000

MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=dashboard_reader
MQTT_PASSWORD=REPLACE_WITH_DASHBOARD_READER_PASSWORD
MQTT_TOPIC=rca/hitayezu-frank-duff/temperature
```

Protect the file:

```bash
chmod 600 ~/temperature-dashboard/.env
```

Test the Flask application manually:

```bash
source ~/temperature-dashboard/.venv/bin/activate
cd ~/temperature-dashboard
python app.py
```

From another SSH terminal:

```bash
curl http://127.0.0.1:3000/health
```

Stop the manual server with `Ctrl+C` before enabling systemd.

### 10.8 Install the dashboard systemd service

The supplied service is already configured for `user218` and `/home/user218/temperature-dashboard`.

```bash
cd ~/temperature-dashboard
sudo cp deploy/temperature-dashboard.service /etc/systemd/system/temperature-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now temperature-dashboard
sudo systemctl status temperature-dashboard --no-pager
```

Logs:

```bash
sudo journalctl -u temperature-dashboard -f
```

Health test:

```bash
curl http://127.0.0.1:3000/health
```

Expected response:

```json
{"mqttConnected":true,"status":"ok"}
```

### 10.9 Configure Nginx

```bash
cd ~/temperature-dashboard
sudo cp deploy/nginx-temperature-dashboard.conf /etc/nginx/sites-available/temperature-dashboard
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/temperature-dashboard /etc/nginx/sites-enabled/temperature-dashboard
sudo nginx -t
sudo systemctl reload nginx
```

### 10.10 Configure the firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
sudo ufw status
```

The VPS provider may also have an external firewall/security group. It must allow inbound TCP `22`, `80`, and `1883`.

### 10.11 Open the dashboard

```text
http://157.173.101.159
```

## 11. Complete operating sequence

1. Disconnect USB and connect all seven jumper wires.
2. Reconnect the Arduino through USB.
3. Upload `temperature_lcd.ino`.
4. Confirm the scrolling name and temperature on the LCD.
5. Confirm `TEMP:<value>` in Serial Monitor.
6. Close Serial Monitor.
7. Verify Mosquitto, the dashboard service, and Nginx on the VPS.
8. Put the MQTT publisher password and correct COM port in `pc_monitor/.env`.
9. Run `python monitor.py` on the PC.
10. Open `http://157.173.101.159`.
11. Warm or cool the DHT11 and confirm the LCD, PC console, and dashboard update.

## 12. Useful commands

```bash
sudo systemctl restart mosquitto
sudo systemctl restart temperature-dashboard
sudo systemctl reload nginx

sudo systemctl status mosquitto --no-pager
sudo systemctl status temperature-dashboard --no-pager
sudo systemctl status nginx --no-pager

sudo journalctl -u mosquitto -n 100 --no-pager
sudo journalctl -u temperature-dashboard -n 100 --no-pager
sudo nginx -t
```

## 13. Common errors

### `ModuleNotFoundError: No module named 'DHT'`

Install `DHT sensor library by Adafruit` in Arduino Library Manager.

### `ERROR:DHT11_READ_FAILED`

Check the three DHT11 wires and confirm the signal wire is on D2.

### LCD backlight works but there is no text

Adjust the backpack contrast potentiometer and verify the I2C address.

### Python cannot open `COM3`

Use the actual Arduino COM port and close Arduino Serial Monitor.

### MQTT connection refused or timed out

Check Mosquitto status, port 1883, the VPS firewall, MQTT username/password, and the ACL topic.

### Dashboard opens but has no values

Check that the PC publisher is running, the MQTT topic matches exactly, and the dashboard service reports `mqttConnected:true`.

### SSH connection times out

Confirm that the VPS is running, SSH is listening on port 22, and the provider firewall permits your network to reach TCP port 22.


## 14. Official references

- Arduino library entry for Adafruit DHT Sensor Library: https://docs.arduino.cc/libraries/dht-sensor-library/
- Adafruit DHT Sensor Library repository and installation notes: https://github.com/adafruit/DHT-sensor-library
- Eclipse Paho MQTT Python client documentation: https://eclipse.dev/paho/files/paho.mqtt.python/html/
- Mosquitto configuration manual: https://mosquitto.org/man/mosquitto-conf-5.html
