from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from datetime import timedelta
import logging

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
    CONF_DELTA_INTERVAL_SECONDS,
    DEFAULT_DELTA_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


# A conservative "physics guard" to prevent spikes from poisoning period counters.
# Adjust if you have extremely large systems.
MAX_KW_ASSUMED = 50.0  # kW


@dataclass
class EnergyTotals:
    imported_kwh: float = 0.0
    exported_kwh: float = 0.0
    produced_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    co2_intensity_g_per_kwh: float = 0.0


@dataclass
class EnergyDeltas:
    dA_imported_kwh: float = 0.0
    dB_exported_kwh: float = 0.0
    dC_produced_kwh: float = 0.0
    dD_charge_kwh: float = 0.0
    dE_discharge_kwh: float = 0.0
    valid: bool = True
    reason: str | None = None


class EnergyCoreCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.interval_s = int(entry.data.get(CONF_DELTA_INTERVAL_SECONDS, DEFAULT_DELTA_INTERVAL_SECONDS))

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.interval_s),
        )

        self._prev_totals: Optional[EnergyTotals] = None
        self._seq: int = 0

        # Derived spike guard: max kWh allowed per interval
        self._max_kwh_per_interval = round(MAX_KW_ASSUMED * (self.interval_s / 3600.0), 6)

    # -----------------------------
    # Safe parsing helpers
    # -----------------------------
    def _read_energy_total_kwh(self, entity_id: str) -> Optional[float]:
        """Read a cumulative energy total and convert to kWh.
        Returns None if missing/unknown/unavailable/invalid.
        """
        st = self.hass.states.get(entity_id)
        if st is None:
            return None

        s = str(st.state).lower().strip()
        if s in ("unknown", "unavailable", "none", ""):
            return None

        try:
            val = float(st.state)
        except (ValueError, TypeError):
            return None

        unit = (st.attributes.get("unit_of_measurement") or "").lower().strip()
        if unit == "wh":
            return val / 1000.0
        if unit == "kwh":
            return val

        # Unit should have been validated in config flow, but keep this safe:
        return None

    def _sum_energy_kwh_strict(self, entity_ids: list[str]) -> Optional[float]:
        """Sum kWh totals across entities.
        Strict: if any entity is missing/invalid -> None (invalidate interval).
        """
        if not entity_ids:
            return 0.0

        total = 0.0
        for eid in entity_ids:
            v = self._read_energy_total_kwh(eid)
            if v is None:
                return None
            total += v

        return round(total, 6)

    def _read_float_safe(self, entity_id: str) -> float:
        st = self.hass.states.get(entity_id)
        if st is None:
            return 0.0

        s = str(st.state).lower().strip()
        if s in ("unknown", "unavailable", "none", ""):
            return 0.0

        try:
            return float(st.state)
        except (ValueError, TypeError):
            return 0.0

    def _delta_or_invalid(
        self,
        cur: float,
        prev: float,
    ) -> tuple[float, Optional[str]]:
        """Compute delta and validate monotonic + spike guard.
        Returns (delta_kwh, invalid_reason_if_any).
        """
        d = round(cur - prev, 6)

        if d < 0:
            return 0.0, "negative_delta"

        if d > self._max_kwh_per_interval:
            return 0.0, "spike_detected"

        return d, None

    # -----------------------------
    # Coordinator update
    # -----------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        data = self.entry.data

        imported_entities = data.get(CONF_IMPORTED_ENTITIES, [])
        exported_entities = data.get(CONF_EXPORTED_ENTITIES, [])
        produced_entities = data.get(CONF_PRODUCED_ENTITIES, [])
        charge_entities = data.get(CONF_BATTERY_CHARGE_ENTITIES, [])
        discharge_entities = data.get(CONF_BATTERY_DISCHARGE_ENTITIES, [])
        co2_entity = data.get(CONF_CO2_INTENSITY_ENTITY)

        # Read strict totals (None => invalidate interval)
        cur_imported = self._sum_energy_kwh_strict(imported_entities)
        cur_exported = self._sum_energy_kwh_strict(exported_entities)
        cur_produced = self._sum_energy_kwh_strict(produced_entities)
        cur_charge = self._sum_energy_kwh_strict(charge_entities)
        cur_discharge = self._sum_energy_kwh_strict(discharge_entities)

        # CO2 intensity isn't a cumulative meter; treat as best-effort float.
        co2_intensity = self._read_float_safe(co2_entity) if co2_entity else 0.0

        deltas = EnergyDeltas(valid=True, reason=None)

        # If any required totals are missing/invalid, mark interval invalid and DO NOT touch prev_totals.
        # This avoids "prev_total = 0" spikes that poison day/month/year.
        if any(v is None for v in (cur_imported, cur_exported, cur_produced, cur_charge, cur_discharge)):
            deltas.valid = False
            deltas.reason = "missing_input"

            # Keep totals stable (use previous totals if known; otherwise 0s).
            totals = self._prev_totals or EnergyTotals()
            totals.co2_intensity_g_per_kwh = co2_intensity

            self._seq += 1
            return {
                "totals": totals,
                "deltas": deltas,
                "seq": self._seq,
                "updated_at": dt_util.utcnow().isoformat(),
            }

        # Safe: all current totals exist
        totals = EnergyTotals(
            imported_kwh=float(cur_imported),
            exported_kwh=float(cur_exported),
            produced_kwh=float(cur_produced),
            battery_charge_kwh=float(cur_charge),
            battery_discharge_kwh=float(cur_discharge),
            co2_intensity_g_per_kwh=co2_intensity,
        )

        # First run: baseline only
        if self._prev_totals is None:
            deltas.valid = False
            deltas.reason = "initial"
            self._prev_totals = totals  # establish baseline
            self._seq += 1
            return {
                "totals": totals,
                "deltas": deltas,
                "seq": self._seq,
                "updated_at": dt_util.utcnow().isoformat(),
            }

        # Compute deltas with monotonic + spike validation
        prev = self._prev_totals

        dA, rA = self._delta_or_invalid(totals.imported_kwh, prev.imported_kwh)
        dB, rB = self._delta_or_invalid(totals.exported_kwh, prev.exported_kwh)
        dC, rC = self._delta_or_invalid(totals.produced_kwh, prev.produced_kwh)
        dD, rD = self._delta_or_invalid(totals.battery_charge_kwh, prev.battery_charge_kwh)
        dE, rE = self._delta_or_invalid(totals.battery_discharge_kwh, prev.battery_discharge_kwh)

        invalid_reason = next((r for r in (rA, rB, rC, rD, rE) if r is not None), None)
        if invalid_reason is not None:
            # Mark invalid and re-baseline to current totals so we recover cleanly next interval.
            deltas.valid = False
            deltas.reason = invalid_reason
            self._prev_totals = totals

            self._seq += 1
            return {
                "totals": totals,
                "deltas": deltas,
                "seq": self._seq,
                "updated_at": dt_util.utcnow().isoformat(),
            }

        # All good
        deltas.dA_imported_kwh = dA
        deltas.dB_exported_kwh = dB
        deltas.dC_produced_kwh = dC
        deltas.dD_charge_kwh = dD
        deltas.dE_discharge_kwh = dE
        deltas.valid = True
        deltas.reason = None

        # Update baseline
        self._prev_totals = totals
        self._seq += 1

        return {
            "totals": totals,
            "deltas": deltas,
            "seq": self._seq,
            "updated_at": dt_util.utcnow().isoformat(),
        }
