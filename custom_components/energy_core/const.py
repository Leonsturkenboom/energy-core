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

DEFAULT_NAME = "Homie Energy Core"