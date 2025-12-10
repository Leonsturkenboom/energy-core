from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_IMPORTED_ENTITIES,
    CONF_EXPORTED_ENTITIES,
    CONF_PRODUCED_ENTITIES,
    CONF_BATTERY_CHARGE_ENTITIES,
    CONF_BATTERY_DISCHARGE_ENTITIES,
    CONF_CO2_INTENSITY_ENTITY,
)

@dataclass
class EnergyInputs:
    imported_kwh: float = 0.0
    exported_kwh: float = 0.0
    produced_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    co2_intensity_g_per_kwh: float = 0.0


class EnergyCoreCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=None,
            name=DOMAIN,
            update_interval=None,  # event-driven-ish; we rely on HA state changes later
        )
        self.entry = entry

    def _state_to_kwh(self, entity_id: str) -> float:
        st = self.hass.states.get(entity_id)
        if st is None:
            return 0.0
        try:
            val = float(st.state)
        except (ValueError, TypeError):
            return 0.0

        unit = (st.attributes.get("unit_of_measurement") or "").lower()
        if unit == "wh":
            return val / 1000.0
        # assume kWh if unknown
        return val

    def _state_to_float(self, entity_id: str) -> float:
        st = self.hass.states.get(entity_id)
        if st is None:
            return 0.0
        try:
            return float(st.state)
        except (ValueError, TypeError):
            return 0.0

    def _sum_kwh(self, entity_ids: list[str]) -> float:
        return round(sum(self._state_to_kwh(e) for e in entity_ids), 6)

    async def _async_update_data(self) -> dict[str, Any]:
        data = self.entry.data

        imported_entities = data.get(CONF_IMPORTED_ENTITIES, [])
        exported_entities = data.get(CONF_EXPORTED_ENTITIES, [])
        produced_entities = data.get(CONF_PRODUCED_ENTITIES, [])
        charge_entities = data.get(CONF_BATTERY_CHARGE_ENTITIES, [])
        discharge_entities = data.get(CONF_BATTERY_DISCHARGE_ENTITIES, [])
        co2_entity = data.get(CONF_CO2_INTENSITY_ENTITY)

        inputs = EnergyInputs(
            imported_kwh=self._sum_kwh(imported_entities),
            exported_kwh=self._sum_kwh(exported_entities),
            produced_kwh=self._sum_kwh(produced_entities),
            battery_charge_kwh=self._sum_kwh(charge_entities),
            battery_discharge_kwh=self._sum_kwh(discharge_entities),
            co2_intensity_g_per_kwh=self._state_to_float(co2_entity) if co2_entity else 0.0,
        )

        return {
            "inputs": inputs,
            "updated_at": dt_util.utcnow().isoformat(),
        }