"""Flask dashboard that subscribes to MQTT and streams readings with SSE."""

from __future__ import annotations

import json
import os
import queue
import threading
from collections import deque
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, stream_with_context

load_dotenv()

APP_HOST = os.getenv("HOST", "127.0.0.1")
APP_PORT = int(os.getenv("PORT", "3000"))
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "").strip()
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC", "rca/hitayezu-frank-duff/temperature"
)



BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

history: deque[dict[str, Any]] = deque(maxlen=120)
latest_reading: dict[str, Any] | None = None
subscribers: set[queue.Queue[dict[str, Any]]] = set()
state_lock = threading.Lock()


def on_connect(
    client: mqtt.Client,
    userdata: object,
    flags: mqtt.ConnectFlags,
    reason_code: mqtt.ReasonCode,
    properties: mqtt.Properties | None,
) -> None:
    if not reason_code.is_failure:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}", flush=True)
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"[MQTT] Subscribed to {MQTT_TOPIC}", flush=True)
    else:
        print(f"[MQTT] Connection failed: {reason_code}", flush=True)


def on_message(
    client: mqtt.Client,
    userdata: object,
    message: mqtt.MQTTMessage,
) -> None:
    global latest_reading

    if message.topic != MQTT_TOPIC:
        return

    try:
        payload = json.loads(message.payload.decode("utf-8"))
        temperature = float(payload["temperature"])
        payload["temperature"] = temperature
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"[MQTT] Ignored invalid payload: {exc}", flush=True)
        return

    with state_lock:
        latest_reading = payload
        history.append(payload)
        current_subscribers = tuple(subscribers)

    for subscriber in current_subscribers:
        try:
            subscriber.put_nowait(payload)
        except queue.Full:
            # Drop a stale item rather than blocking the MQTT network thread.
            try:
                subscriber.get_nowait()
                subscriber.put_nowait(payload)
            except queue.Empty:
                pass

    print(f"[DATA] {temperature:.2f} °C", flush=True)


mqtt_client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="vps-temperature-dashboard",
    protocol=mqtt.MQTTv311,
)
if MQTT_USERNAME:
    mqtt_client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD if MQTT_PASSWORD else None,
    )
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
mqtt_client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/health")
def health() -> Response:
    return jsonify(status="ok", mqttConnected=mqtt_client.is_connected())


@app.get("/events")
def events() -> Response:
    subscriber: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=10)

    with state_lock:
        subscribers.add(subscriber)
        snapshot = list(history)

    @stream_with_context
    def event_stream():
        try:
            yield f"event: history\ndata: {json.dumps(snapshot)}\n\n"

            while True:
                try:
                    reading = subscriber.get(timeout=15)
                    yield f"event: temperature\ndata: {json.dumps(reading)}\n\n"
                except queue.Empty:
                    # SSE comment keeps proxies and browsers from timing out.
                    yield ": keepalive\n\n"
        finally:
            with state_lock:
                subscribers.discard(subscriber)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, threaded=True)
