#!/bin/bash

# Load environment variables from Home Assistant options
MQTT_HOST=$(jq --raw-output '.mqtt_host' /data/options.json)
MQTT_PORT=$(jq --raw-output '.mqtt_port' /data/options.json)
MQTT_USER=$(jq --raw-output '.mqtt_user' /data/options.json)
MQTT_PASSWORD=$(jq --raw-output '.mqtt_password' /data/options.json)
URLS=$(jq --raw-output '.urls[]' /data/options.json)

# Run the bus schedule service Python script with the passed values
python3 bus_schedule_service.py
