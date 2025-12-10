from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_NAME
from .coordinator import EnergyCoreCoordinator, EnergyInputs


def _inputs(coordinator: EnergyCoreCoordinator) -> EnergyInputs:
    return coordinator.data.get("inputs")


def _clamp_min0(x: float) -> float:
    return x if x > 0 else 0.0


@dataclass
class ECDescription:
    key: str
    name: str
    unit: str
    device_class: Optional[SensorDeviceClass]
    state_class: Optional[SensorStateClass]
    icon: Optional[str]
    value_fn: Callable[[EnergyCoreCoordinator], float]


DESCRIPTIONS: list[ECDescription] = [
    # Base totals from inputs
    ECDescription(
        key="ec_imported_energy",
        name="EC Imported Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:transmission-tower-import",
        value_fn=lambda c: _inputs(c).imported_kwh,
    ),
    ECDescription(
        key="ec_exported_energy",
        name="EC Exported Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:transmission-tower-export",
        value_fn=lambda c: _inputs(c).exported_kwh,
    ),
    ECDescription(
        key="ec_produced_energy",
        name="EC Produced Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:solar-power",
        value_fn=lambda c: _inputs(c).produced_kwh,
    ),
    ECDescription(
        key="ec_battery_charge_energy",
        name="EC Battery Charge Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-up",
        value_fn=lambda c: _inputs(c).battery_charge_kwh,
    ),
    ECDescription(
        key="ec_battery_discharge_energy",
        name="EC Battery Discharge Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-down",
        value_fn=lambda c: _inputs(c).battery_discharge_kwh,
    ),

    # Input-only allocation derived totals
    ECDescription(
        key="ec_self_consumed_energy",
        name="EC Self Consumed Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:home-lightning-bolt",
        value_fn=lambda c: _clamp_min0(
            _inputs(c).produced_kwh - _inputs(c).exported_kwh - _inputs(c).battery_charge_kwh
        ),
    ),
    ECDescription(
        key="ec_self_stored_energy",
        name="EC Self Stored Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-charging-70",
        value_fn=lambda c: min(
            _inputs(c).battery_charge_kwh,
            _clamp_min0(_inputs(c).produced_kwh - _inputs(c).exported_kwh),
        ),
    ),
    ECDescription(
        key="ec_imported_battery_energy",
        name="EC Imported Battery Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-charging",
        value_fn=lambda c: _clamp_min0(
            _inputs(c).battery_charge_kwh - _clamp_min0(_inputs(c).produced_kwh - _inputs(c).exported_kwh)
        ),
    ),
    ECDescription(
        key="ec_exported_battery_energy",
        name="EC Exported Battery Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-right",
        value_fn=lambda c: min(_inputs(c).battery_discharge_kwh, _inputs(c).exported_kwh),
    ),
    ECDescription(
        key="ec_self_battery_energy",
        name="EC Self Battery Energy",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery",
        value_fn=lambda c: _clamp_min0(_inputs(c).battery_discharge_kwh - _inputs(c).exported_kwh),
    ),

    # Net KPIs (treat as measurements)
    ECDescription(
        key="ec_net_energy_use",
        name="EC Net Energy Use (On-site)",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-sankey",
        value_fn=lambda c: _inputs(c).imported_kwh + _inputs(c).produced_kwh - _inputs(c).exported_kwh,
    ),
    ECDescription(
        key="ec_net_import_energy",
        name="EC Net Import Energy (Grid)",
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:swap-horizontal",
        value_fn=lambda c: _inputs(c).imported_kwh - _inputs(c).exported_kwh,
    ),

    # Self sufficiency (0-100%)
    ECDescription(
        key="ec_self_sufficiency",
        name="EC Self Sufficiency",
        unit="%",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent",
        value_fn=lambda c: _calc_self_sufficiency_percent(c),
    ),

    # Emissions (simple period-average approach)
    ECDescription(
        key="ec_emissions_imported",
        name="EC Emissions Imported",
        unit="g CO2-eq",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud-upload",
        value_fn=lambda c: (_inputs(c).imported_kwh * _inputs(c).co2_intensity_g_per_kwh),
    ),
    ECDescription(
        key="ec_emissions_avoided",
        name="EC Emissions Avoided",
        unit="g CO2-eq",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud-download",
        value_fn=lambda c: (_inputs(c).exported_kwh * _inputs(c).co2_intensity_g_per_kwh),
    ),
    ECDescription(
        key="ec_emissions_net",
        name="EC Emissions Net",
        unit="g CO2-eq",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud",
        value_fn=lambda c: ((_inputs(c).imported_kwh - _inputs(c).exported_kwh) * _inputs(c).co2_intensity_g_per_kwh),
    ),
]


def _calc_self_sufficiency_percent(c: EnergyCoreCoordinator) -> float:
    i = _inputs(c)
    denom = i.imported_kwh + (i.produced_kwh - i.exported_kwh)
    if denom <= 0:
        return 0.0
    ss = 1.0 - (i.imported_kwh / denom)
    if ss < 0:
        ss = 0.0
    if ss > 1:
        ss = 1.0
    return round(ss * 100.0, 2)


class EnergyCoreSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnergyCoreCoordinator, description: ECDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class

    @property
    def native_value(self) -> float:
        try:
            val = self.entity_description.value_fn(self.coordinator)
            return round(float(val), 6)
        except Exception:
            return 0.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnergyCoreCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnergyCoreSensor(coordinator, d) for d in DESCRIPTIONS])