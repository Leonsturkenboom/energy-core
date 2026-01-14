from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, List
from datetime import datetime, timedelta
import asyncio

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnergyCoreCoordinator, EnergyDeltas, EnergyTotals
from .notifications import NOTIFICATION_RULES, get_active_notifications


def _deltas(coordinator: EnergyCoreCoordinator) -> EnergyDeltas:
    return coordinator.data.get("deltas")


def _totals(coordinator: EnergyCoreCoordinator) -> EnergyTotals:
    return coordinator.data.get("totals")


def _seq(coordinator: EnergyCoreCoordinator) -> int:
    return int(coordinator.data.get("seq", 0))


def _interval_valid(coordinator: EnergyCoreCoordinator) -> bool:
    d = _deltas(coordinator)
    return bool(getattr(d, "valid", False))


def _clamp_min0(x: float) -> float:
    return x if x > 0 else 0.0


def _calc_self_sufficiency_percent_from_parts(imported_kwh: float, produced_kwh: float, exported_kwh: float) -> float:
    denom = imported_kwh + (produced_kwh - exported_kwh)
    if denom <= 0:
        return 0.0
    ss = 1.0 - (imported_kwh / denom)
    ss = max(0.0, min(1.0, ss))
    return round(ss * 100.0, 2)


@dataclass
class ECDescription(SensorEntityDescription):
    """Energy Core sensor description with a value function and counter behavior."""
    value_fn: Callable[[EnergyCoreCoordinator], float] = lambda c: 0.0
    allow_negative: bool = False  # whether period/lifetime sums may go below zero
    include_period_counters: bool = True
    include_overall_counter: bool = True  # overall = lifetime-like
    period_keys: list[str] | None = None  # if set, only create these periods (e.g., ["p15m", "phour", "pday"])


# -----------------------------
# Base + derived DELTA sensors (per-interval)
# -----------------------------
DESCRIPTIONS: list[ECDescription] = [
    # Base deltas (kWh per interval) - No device_class to avoid state_class conflict
    ECDescription(
        key="ec_imported_energy",
        name="EC Imported Energy",
        icon="mdi:transmission-tower-import",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _deltas(c).dA_imported_kwh if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_exported_energy",
        name="EC Exported Energy",
        icon="mdi:transmission-tower-export",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _deltas(c).dB_exported_kwh if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_produced_energy",
        name="EC Produced Energy",
        icon="mdi:solar-power",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _deltas(c).dC_produced_kwh if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_battery_charge_energy",
        name="EC Battery Charge Energy",
        icon="mdi:battery-arrow-up",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _deltas(c).dD_charge_kwh if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_battery_discharge_energy",
        name="EC Battery Discharge Energy",
        icon="mdi:battery-arrow-down",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _deltas(c).dE_discharge_kwh if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_net_battery_flow",
        name="EC Net Battery Flow",
        icon="mdi:battery-sync",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: (
            _deltas(c).dE_discharge_kwh - _deltas(c).dD_charge_kwh
        ) if _interval_valid(c) else 0.0,
        allow_negative=True,
        include_period_counters=True,
        include_overall_counter=False,  # Not useful for cumulative totals
        period_keys=["p15m", "phour", "pday"],  # Only short periods, not week/month/year
    ),

    # Derived splits (kWh per interval) - No device_class to avoid state_class conflict
    ECDescription(
        key="ec_self_consumed_energy",
        name="EC Self Consumed Energy",
        icon="mdi:home-lightning-bolt",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(
            _deltas(c).dC_produced_kwh - _deltas(c).dB_exported_kwh - _deltas(c).dD_charge_kwh
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_self_stored_energy",
        name="EC Self Stored Energy",
        icon="mdi:battery-charging-70",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: min(
            _deltas(c).dD_charge_kwh,
            _clamp_min0(_deltas(c).dC_produced_kwh - _deltas(c).dB_exported_kwh),
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_imported_battery_energy",
        name="EC Imported Battery Energy",
        icon="mdi:battery-charging",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(
            _deltas(c).dD_charge_kwh - _clamp_min0(_deltas(c).dC_produced_kwh - _deltas(c).dB_exported_kwh)
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_exported_battery_energy",
        name="EC Exported Battery Energy",
        icon="mdi:battery-charging-wireless",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: min(_deltas(c).dE_discharge_kwh, _deltas(c).dB_exported_kwh) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_self_consumed_battery_energy",
        name="EC Self Consumed Battery Energy",
        icon="mdi:battery",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(_deltas(c).dE_discharge_kwh - _deltas(c).dB_exported_kwh) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_imported_residual_energy",
        name="EC Imported Residual Energy",
        icon="mdi:transmission-tower-import",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(
            _deltas(c).dA_imported_kwh
            - _clamp_min0(
                _deltas(c).dD_charge_kwh
                - _clamp_min0(_deltas(c).dC_produced_kwh - _deltas(c).dB_exported_kwh)
            )
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_exported_residual_energy",
        name="EC Exported Residual Energy",
        icon="mdi:transmission-tower-export",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(_deltas(c).dB_exported_kwh - _deltas(c).dE_discharge_kwh) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),

    # Net KPIs (signed is allowed) - No device_class to avoid state_class conflict
    ECDescription(
        key="ec_net_energy_use",
        name="EC Net Energy Use (On-site)",
        icon="mdi:chart-sankey",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: (
            _deltas(c).dA_imported_kwh + _deltas(c).dC_produced_kwh - _deltas(c).dB_exported_kwh
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,  # should not go negative in normal accounting
    ),
    ECDescription(
        key="ec_net_energy_imported_grid",
        name="EC Net Energy Imported (Grid)",
        icon="mdi:swap-horizontal",
        device_class=None,  # Interval energy, not cumulative
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: (_deltas(c).dA_imported_kwh - _deltas(c).dB_exported_kwh) if _interval_valid(c) else 0.0,
        allow_negative=True,
    ),

    # Self sufficiency (ratio; do NOT sum percent for period/overall)
    ECDescription(
        key="ec_self_sufficiency",
        name="EC Self Sufficiency",
        icon="mdi:percent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        value_fn=lambda c: _calc_self_sufficiency_percent_from_parts(
            _deltas(c).dA_imported_kwh, _deltas(c).dC_produced_kwh, _deltas(c).dB_exported_kwh
        ) if _interval_valid(c) else 0.0,
        include_period_counters=False,  # handled by dedicated ratio period sensor below
        include_overall_counter=False,
    ),

    # Emissions (outputs in kg CO2-eq; input intensity is g/kWh, so divide by 1000)
    ECDescription(
        key="ec_emissions_imported",
        name="EC Emissions Imported",
        icon="mdi:cloud-upload",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kg CO2-eq",
        value_fn=lambda c: (
            (_deltas(c).dA_imported_kwh * _totals(c).co2_intensity_g_per_kwh) / 1000.0
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_emissions_avoided",
        name="EC Emissions Avoided",
        icon="mdi:cloud-download",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kg CO2-eq",
        value_fn=lambda c: (
            (_deltas(c).dB_exported_kwh * _totals(c).co2_intensity_g_per_kwh) / 1000.0
        ) if _interval_valid(c) else 0.0,
        allow_negative=False,
    ),
    ECDescription(
        key="ec_emissions_net",
        name="EC Emissions Net",
        icon="mdi:cloud",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kg CO2-eq",
        value_fn=lambda c: (
            ((_deltas(c).dA_imported_kwh - _deltas(c).dB_exported_kwh) * _totals(c).co2_intensity_g_per_kwh) / 1000.0
        ) if _interval_valid(c) else 0.0,
        allow_negative=True,
    ),
]


# -----------------------------
# Period counter specs (includes overall)
# -----------------------------
@dataclass
class PeriodSpec:
    key: str
    label: str
    start_fn: Callable[[datetime], datetime]


def _local_floor(now_utc: datetime) -> datetime:
    return dt_util.as_local(now_utc)


def _start_overall(_: datetime) -> datetime:
    # Constant bucket start => never resets => "overall"
    return dt_util.as_utc(datetime(1970, 1, 1))


def _start_15m(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    minute = (nl.minute // 15) * 15
    start_local = nl.replace(minute=minute, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_hour(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_day(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_week(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=nl.weekday())
    return dt_util.as_utc(start_local)


def _start_month(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_year(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


PERIODS: list[PeriodSpec] = [
    PeriodSpec(key="p15m", label="15m", start_fn=_start_15m),
    PeriodSpec(key="phour", label="Hour", start_fn=_start_hour),
    PeriodSpec(key="pday", label="Day", start_fn=_start_day),
    PeriodSpec(key="pweek", label="Week", start_fn=_start_week),
    PeriodSpec(key="pmonth", label="Month", start_fn=_start_month),
    PeriodSpec(key="pyear", label="Year", start_fn=_start_year),
    PeriodSpec(key="poverall", label="Overall", start_fn=_start_overall),
]


# -----------------------------
# Persistent accumulator store (generic)
# -----------------------------
class AccumulatorStore:
    """
    Stores per-sensor period accumulators so counters survive restarts.

    Schema:
    {
      "<base_key>": {
        "<period_key>": {
          "start": "<iso>",
          "sum": <float>,
          "last_seq": <int>
        }
      }
    }
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self._store = Store(hass, 1, f"{DOMAIN}.{entry_id}.accumulators")
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        async with self._lock:
            if self._loaded:
                return
            self._data = await self._store.async_load() or {}
            self._loaded = True

    def get(self, base_key: str, period_key: str) -> Optional[dict[str, Any]]:
        return self._data.get(base_key, {}).get(period_key)

    async def async_set(self, base_key: str, period_key: str, record: dict[str, Any]) -> None:
        base = self._data.setdefault(base_key, {})
        base[period_key] = record
        await self._store.async_save(self._data)


# -----------------------------
# Base sensor
# -----------------------------
class EnergyCoreSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnergyCoreCoordinator, description: ECDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_icon = description.icon

    @property
    def native_value(self) -> float:
        try:
            val = self.entity_description.value_fn(self.coordinator)
            return round(float(val), 6)
        except Exception:
            return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = _deltas(self.coordinator)
        return {
            "interval_valid": bool(getattr(d, "valid", False)),
            "interval_reason": getattr(d, "reason", None),
            "seq": _seq(self.coordinator),
        }


# -----------------------------
# Generic sum period counter (works for kWh and kg CO2-eq; signed optional)
# -----------------------------
class EnergyCoreSumPeriodSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnergyCoreCoordinator, base: ECDescription, period: PeriodSpec, store: AccumulatorStore) -> None:
        super().__init__(coordinator)
        self._base = base
        self._period = period
        self._store = store

        self._attr_unique_id = f"{coordinator.entry.entry_id}_{base.key}_{period.key}"
        self._attr_name = f"{base.name} {period.label}"
        self._attr_icon = base.icon

        self._attr_device_class = base.device_class
        self._attr_native_unit_of_measurement = base.native_unit_of_measurement
        # Period sensors are cumulative totals - use TOTAL_INCREASING for energy
        if base.device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        self._period_start: Optional[datetime] = None
        self._sum: float = 0.0
        self._last_seq: int = 0
        self._loaded = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._store.async_load()

        rec = self._store.get(self._base.key, self._period.key)
        if rec:
            try:
                start_raw = rec.get("start")
                self._sum = float(rec.get("sum", 0.0))
                self._last_seq = int(rec.get("last_seq", 0))
                start = dt_util.parse_datetime(start_raw) if start_raw else None
                if start is not None:
                    self._period_start = start if start.tzinfo else dt_util.as_utc(start)
            except Exception:
                pass

        self._loaded = True

    def _current_value(self) -> float:
        try:
            return float(self._base.value_fn(self.coordinator))
        except Exception:
            return 0.0

    def _reset_if_needed(self, now: datetime) -> None:
        start = self._period.start_fn(now)
        if self._period_start != start:
            self._period_start = start
            self._sum = 0.0
            self._last_seq = 0

    @property
    def native_value(self) -> float:
        now = dt_util.utcnow()
        self._reset_if_needed(now)

        cur_seq = _seq(self.coordinator)
        if cur_seq != self._last_seq:
            v = self._current_value()
            if not self._base.allow_negative:
                v = _clamp_min0(v)

            if _interval_valid(self.coordinator):
                self._sum = round(self._sum + v, 6)

            self._last_seq = cur_seq

            if self._loaded:
                rec = {
                    "start": self._period_start.isoformat() if self._period_start else None,
                    "sum": float(self._sum),
                    "last_seq": int(self._last_seq),
                }
                self.hass.async_create_task(self._store.async_set(self._base.key, self._period.key, rec))

        return round(self._sum, 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "period_key": self._period.key,
            "period_label": self._period.label,
            "period_start_utc": self._period_start.isoformat() if self._period_start else None,
            "last_seq": self._last_seq,
        }


# -----------------------------
# Self sufficiency period sensor (ratio over accumulated parts)
# -----------------------------
class EnergyCoreSelfSufficiencyPeriodSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:percent"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: EnergyCoreCoordinator, period: PeriodSpec, store: AccumulatorStore) -> None:
        super().__init__(coordinator)
        self._period = period
        self._store = store

        self._attr_unique_id = f"{coordinator.entry.entry_id}_ec_self_sufficiency_{period.key}"
        self._attr_name = f"EC Self Sufficiency {period.label}"

        self._period_start: Optional[datetime] = None
        self._sum_imported: float = 0.0
        self._sum_produced: float = 0.0
        self._sum_exported: float = 0.0
        self._last_seq: int = 0
        self._loaded = False

        # Store under this base_key
        self._base_key = "ec_self_sufficiency_ratio_parts"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._store.async_load()

        rec = self._store.get(self._base_key, self._period.key)
        if rec:
            try:
                start_raw = rec.get("start")
                self._sum_imported = float(rec.get("sum_imported", 0.0))
                self._sum_produced = float(rec.get("sum_produced", 0.0))
                self._sum_exported = float(rec.get("sum_exported", 0.0))
                self._last_seq = int(rec.get("last_seq", 0))
                start = dt_util.parse_datetime(start_raw) if start_raw else None
                if start is not None:
                    self._period_start = start if start.tzinfo else dt_util.as_utc(start)
            except Exception:
                pass

        self._loaded = True

    def _reset_if_needed(self, now: datetime) -> None:
        start = self._period.start_fn(now)
        if self._period_start != start:
            self._period_start = start
            self._sum_imported = 0.0
            self._sum_produced = 0.0
            self._sum_exported = 0.0
            self._last_seq = 0

    @property
    def native_value(self) -> float:
        now = dt_util.utcnow()
        self._reset_if_needed(now)

        cur_seq = _seq(self.coordinator)
        if cur_seq != self._last_seq:
            if _interval_valid(self.coordinator):
                d = _deltas(self.coordinator)
                self._sum_imported = round(self._sum_imported + max(0.0, d.dA_imported_kwh), 6)
                self._sum_produced = round(self._sum_produced + max(0.0, d.dC_produced_kwh), 6)
                self._sum_exported = round(self._sum_exported + max(0.0, d.dB_exported_kwh), 6)

            self._last_seq = cur_seq

            if self._loaded:
                rec = {
                    "start": self._period_start.isoformat() if self._period_start else None,
                    "sum_imported": float(self._sum_imported),
                    "sum_produced": float(self._sum_produced),
                    "sum_exported": float(self._sum_exported),
                    "last_seq": int(self._last_seq),
                }
                self.hass.async_create_task(self._store.async_set(self._base_key, self._period.key, rec))

        return _calc_self_sufficiency_percent_from_parts(self._sum_imported, self._sum_produced, self._sum_exported)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "period_key": self._period.key,
            "period_label": self._period.label,
            "period_start_utc": self._period_start.isoformat() if self._period_start else None,
            "last_seq": self._last_seq,
            "sum_imported_kwh": self._sum_imported,
            "sum_produced_kwh": self._sum_produced,
            "sum_exported_kwh": self._sum_exported,
        }


# -----------------------------
# Notification sensor
# -----------------------------
class EnergyCoreNotificationSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    """Notification sensor that shows warnings/info/tips."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:bell-alert"

    def __init__(self, coordinator: EnergyCoreCoordinator, rule_key: str, rule_name: str) -> None:
        super().__init__(coordinator)
        self._rule_key = rule_key
        self._rule_name = rule_name

        self._attr_unique_id = f"{coordinator.entry.entry_id}_{rule_key}"
        self._attr_name = f"{rule_name}"

    @property
    def native_value(self) -> str:
        """Return the notification message or 'off' if not active."""
        # Check if notifications are enabled
        notifications_enabled = self.hass.states.get("input_boolean.ec_notifications_enabled")
        if notifications_enabled and notifications_enabled.state == "off":
            return "off"

        # Get presence mode for holiday suppression
        presence_entity = self.coordinator.entry.options.get("presence_entity")
        presence_mode = None
        if presence_entity:
            presence_state = self.hass.states.get(presence_entity)
            if presence_state:
                presence_mode = presence_state.state

        # Get input entities from coordinator config for data gap detection
        from .const import (
            CONF_IMPORTED_ENTITIES,
            CONF_EXPORTED_ENTITIES,
            CONF_PRODUCED_ENTITIES,
        )

        input_entities = {
            "imported": self.coordinator.entry.data.get(CONF_IMPORTED_ENTITIES, []),
            "exported": self.coordinator.entry.data.get(CONF_EXPORTED_ENTITIES, []),
            "produced": self.coordinator.entry.data.get(CONF_PRODUCED_ENTITIES, []),
        }

        # Get notification data from metrics store
        data = self.coordinator.metrics_store.get_notification_data(
            self.hass,
            self.coordinator.data or {},
            input_entities
        )

        # Get active notifications
        language = self.hass.config.language if self.hass.config.language in ["nl", "en"] else "en"
        active_notifications = get_active_notifications(data, presence_mode, language)

        # Return message if this notification is active
        if self._rule_key in active_notifications:
            return active_notifications[self._rule_key]

        return "off"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return extra attributes for filtering."""
        return {
            "tag": "Homie",
            "category": "energy",
            "severity": self._get_severity(),
        }

    def _get_severity(self) -> str:
        """Get severity level for this notification."""
        for rule in NOTIFICATION_RULES:
            if rule.key == self._rule_key:
                return rule.severity
        return "info"


# -----------------------------
# Setup
# -----------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnergyCoreCoordinator = hass.data[DOMAIN][entry.entry_id]

    store = AccumulatorStore(hass, entry.entry_id)
    await store.async_load()

    base_entities: List[SensorEntity] = [EnergyCoreSensor(coordinator, d) for d in DESCRIPTIONS]

    period_entities: List[SensorEntity] = []

    # Generic sum period counters for supported bases
    for d in DESCRIPTIONS:
        if not d.include_period_counters:
            continue
        for p in PERIODS:
            if p.key == "poverall" and not d.include_overall_counter:
                continue
            # If period_keys is specified, only create those periods
            if d.period_keys is not None and p.key not in d.period_keys:
                continue
            period_entities.append(EnergyCoreSumPeriodSensor(coordinator, d, p, store))

    # Dedicated ratio period sensors for self sufficiency (hour/day/week/month/year/overall)
    for p in PERIODS:
        period_entities.append(EnergyCoreSelfSufficiencyPeriodSensor(coordinator, p, store))

    # Notification sensors
    notification_entities: List[SensorEntity] = []
    for rule in NOTIFICATION_RULES:
        notification_entities.append(EnergyCoreNotificationSensor(coordinator, rule.key, rule.name))

    async_add_entities(base_entities + period_entities + notification_entities)
