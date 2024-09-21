#!/bin/bash

# Load environment variables from Home Assistant options
MQTT_HOST=$(jq --raw-output '.mqtt_host' /data/options.json)
MQTT_PORT=$(jq --raw-output '.mqtt_port' /data/options.json)
MQTT_USER=$(jq --raw-output '.mqtt_user' /data/options.json)
MQTT_PASSWORD=$(jq --raw-output '.mqtt_password' /data/options.json)
URLS=$(jq --raw-output '.urls[]' /data/options.json | paste -sd "," -)  # Combine URLs into a comma-separated list

# Verify that all required configurations are present
if [ -z "$MQTT_HOST" ] || [ -z "$MQTT_PORT" ] || [ -z "$MQTT_USER" ] || [ -z "$MQTT_PASSWORD" ] || [ -z "$URLS" ]; then
  echo "Error: Missing required configuration. Ensure mqtt_host, mqtt_port, mqtt_user, mqtt_password, and urls are set."
  exit 1
fi

# Export variables so they are accessible to the Python script
export MQTT_HOST
export MQTT_PORT
export MQTT_USER
export MQTT_PASSWORD
export URLS

# Run the bus schedule service Python script with the passed values
python3 bus_schedule_service.py
