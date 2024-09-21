#!/bin/bash

# Load environment variables from Home Assistant options
MQTT_HOST=$(jq --raw-output '.mqtt_host' /data/options.json)
MQTT_PORT=$(jq --raw-output '.mqtt_port' /data/options.json)
MQTT_USER=$(jq --raw-output '.mqtt_user' /data/options.json)
MQTT_PASSWORD=$(jq --raw-output '.mqtt_password' /data/options.json)
URLS=$(jq --raw-output '.urls[]' /data/options.json | paste -sd "," -)

# Debugging: Print loaded configurations
echo "MQTT_HOST: $MQTT_HOST"
echo "MQTT_PORT: $MQTT_PORT"
echo "MQTT_USER: $MQTT_USER"
echo "MQTT_PASSWORD: $MQTT_PASSWORD"
echo "URLS: $URLS"

# Check for missing configurations
if [ -z "$MQTT_HOST" ] || [ -z "$MQTT_PORT" ] || [ -z "$MQTT_USER" ] || [ -z "$MQTT_PASSWORD" ] || [ -z "$URLS" ]; then
  echo "Error: Missing required configuration. Ensure mqtt_host, mqtt_port, mqtt_user, mqtt_password, and urls are set."
  exit 1
fi

# Export variables so the Python script can access them
export MQTT_HOST
export MQTT_PORT
export MQTT_USER
export MQTT_PASSWORD
export URLS

# Debugging: Print confirmation before running Python script
echo "Starting bus schedule service..."

# Run the Python script and capture any errors
python3 bus_schedule_service.py

# After the Python script finishes
echo "Bus schedule service finished."
