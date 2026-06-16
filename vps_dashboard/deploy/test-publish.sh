#!/usr/bin/env bash
set -euo pipefail

HOST="${MQTT_HOST:-157.173.101.159}"
USER="${MQTT_USERNAME:-pc_publisher}"
TOPIC="${MQTT_TOPIC:-rca/hitayezu-frank-duff/temperature}"

if [[ -z "${MQTT_PASSWORD:-}" ]]; then
  echo "Set MQTT_PASSWORD first. Example:"
  echo "  export MQTT_PASSWORD='your-password'"
  exit 1
fi

mosquitto_pub \
  -h "$HOST" \
  -p 1883 \
  -u "$USER" \
  -P "$MQTT_PASSWORD" \
  -t "$TOPIC" \
  -q 1 \
  -r \
  -m '{"device":"arduino-uno-dht11","sensor":"DHT11","student":"HITAYEZU Frank Duff","temperature":25.50,"unit":"C","timestamp":"2026-06-16T12:00:00Z"}'

echo "Test reading published to $TOPIC"
