from __future__ import annotations

DOMAIN = "energy_core"

# Config keys (Inputs A-F + optional presence)
CONF_IMPORTED_ENTITIES = "imported_entities"          # A
CONF_EXPORTED_ENTITIES = "exported_entities"          # B
CONF_PRODUCED_ENTITIES = "produced_entities"          # C
CONF_BATTERY_CHARGE_ENTITIES = "battery_charge_entities"      # D
CONF_BATTERY_DISCHARGE_ENTITIES = "battery_discharge_entities" # E
CONF_CO2_INTENSITY_ENTITY = "co2_intensity_entity"    # F
CONF_PRESENCE_ENTITY = "presence_entity"              # optional

# Weather sensors for forecaster (optional)
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_WIND_SENSOR = "wind_sensor"
CONF_SOLAR_SENSOR = "solar_sensor"

# Default weather sensor entity_ids
DEFAULT_TEMPERATURE_SENSOR = "sensor.open_meteo_hourly_temperature_forecast"
DEFAULT_WIND_SENSOR = "sensor.open_meteo_hourly_wind_forecast"
DEFAULT_SOLAR_SENSOR = "sensor.gecombineerde_productie_totaal"

# InfluxDB configuration (optional)
CONF_INFLUXDB_ENABLED = "influxdb_enabled"
CONF_INFLUXDB_URL = "influxdb_url"
CONF_INFLUXDB_TOKEN = "influxdb_token"
CONF_INFLUXDB_ORG = "influxdb_org"
CONF_INFLUXDB_BUCKET = "influxdb_bucket"

# InfluxDB defaults
DEFAULT_INFLUXDB_ORG = "Homie"
DEFAULT_INFLUXDB_BUCKET = "homeassistant"

DEFAULT_NAME = "Homie Energy Core"