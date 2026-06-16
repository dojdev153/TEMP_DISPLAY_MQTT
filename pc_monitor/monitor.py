"""Read DHT11 temperature values from Arduino serial and publish them to MQTT."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Final

import paho.mqtt.client as mqtt
import serial
from dotenv import load_dotenv
from serial.tools import list_ports

load_dotenv()

SERIAL_PORT: Final[str] = os.getenv("SERIAL_PORT", "COM3")
SERIAL_BAUD_RATE: Final[int] = int(os.getenv("SERIAL_BAUD_RATE", "9600"))

MQTT_HOST: Final[str] = os.getenv("MQTT_HOST", "157.173.101.159")
MQTT_PORT: Final[int] = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME: Final[str] = os.getenv("MQTT_USERNAME", "pc_publisher")
MQTT_PASSWORD: Final[str] = os.getenv("MQTT_PASSWORD", "CHANGE_ME")
MQTT_TOPIC: Final[str] = os.getenv(
    "MQTT_TOPIC", "rca/hitayezu-frank-duff/temperature"
)
MQTT_CONNECTED = threading.Event()


def available_ports() -> str:
    ports = [f"{p.device} ({p.description})" for p in list_ports.comports()]
    return "\n".join(ports) if ports else "No serial ports detected."


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if not reason_code.is_failure:
        MQTT_CONNECTED.set()
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        MQTT_CONNECTED.clear()
        print(f"[MQTT] Connection failed: {reason_code}")


def create_mqtt_client() -> mqtt.Client:

    MQTT_CONNECTED.clear()
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="hitayezu-pc-temperature-publisher",
        protocol=mqtt.MQTTv311,
    )
    # Only send authentication details when a username is configured.
def create_mqtt_client() -> mqtt.Client:
    MQTT_CONNECTED.clear()
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="hitayezu-pc-temperature-publisher",
        protocol=mqtt.MQTTv311,
    )
    
    # Indented by 4 spaces to stay inside the function
    if MQTT_USERNAME:
        client.username_pw_set(
            MQTT_USERNAME,
            MQTT_PASSWORD if MQTT_PASSWORD else None,
        )
        
    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    if not MQTT_CONNECTED.wait(timeout=10):
        client.loop_stop()
        client.disconnect()
        raise ConnectionError(
            "MQTT CONNACK was not accepted within 10 seconds. "
            "Check the broker, firewall, username, password and ACL."
        )

    return client


def parse_temperature(line: str) -> float | None:
    if not line.startswith("TEMP:"):
        return None

    try:
        return float(line.split(":", maxsplit=1)[1].strip())
    except (IndexError, ValueError):
        print(f"[SERIAL] Ignored malformed line: {line!r}")
        return None


def main() -> int:


    try:
        mqtt_client = create_mqtt_client()
    except Exception as exc:
        print(f"ERROR: Could not connect to MQTT broker: {exc}")
        return 1

    try:
        arduino = serial.Serial(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        )
    except serial.SerialException as exc:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print(f"ERROR: Could not open {SERIAL_PORT}: {exc}")
        print("Detected serial ports:")
        print(available_ports())
        return 1

    print("=" * 64)
    print(" Arduino -> PC -> MQTT temperature monitor")
    print(f" Serial: {SERIAL_PORT} at {SERIAL_BAUD_RATE} baud, 8N1")
    print(f" MQTT:   {MQTT_HOST}:{MQTT_PORT}")
    print(f" Topic:  {MQTT_TOPIC}")
    print(" Press Ctrl+C to stop")
    print("=" * 64)

    # Arduino Uno normally resets when the serial port is opened.
    time.sleep(2)
    arduino.reset_input_buffer()

    try:
        while True:
            raw_line = arduino.readline()
            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            temperature = parse_temperature(line)
            if temperature is None:
                print(f"[ARDUINO] {line}")
                continue

            timestamp = datetime.now(timezone.utc).isoformat()
            payload = {
    "device": "arduino-uno-dht11",
    "sensor": "DHT11",
    "student": "HITAYEZU Frank Duff",
    "temperature": round(temperature, 2),
    "unit": "C",
    "timestamp": timestamp,
       }

            result = mqtt_client.publish(
                MQTT_TOPIC,
                json.dumps(payload),
                qos=1,
                retain=True,
            )
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Publish failed immediately: {mqtt.error_string(result.rc)}")
                continue

            try:
                result.wait_for_publish(timeout=5)
            except (RuntimeError, ValueError) as exc:
                print(f"[MQTT] Publish failed: {exc}")
                continue

            if not result.is_published():
                print("[MQTT] Publish acknowledgement timed out after 5 seconds")
                continue

            local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[{local_time}] Temperature: {temperature:6.2f} °C "
                f"-> MQTT published (mid={result.mid})"
            )

    except KeyboardInterrupt:
        print("\nStopping monitor...")
    except serial.SerialException as exc:
        print(f"\nSerial connection lost: {exc}")
        return 1
    finally:
        arduino.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
