"""InfluxDB logger for Energy Core 15-minute data."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_INFLUXDB_ENABLED,
    CONF_INFLUXDB_URL,
    CONF_INFLUXDB_TOKEN,
    CONF_INFLUXDB_ORG,
    CONF_INFLUXDB_BUCKET,
    CONF_PRESENCE_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_WIND_SENSOR,
    CONF_SOLAR_SENSOR,
    DEFAULT_INFLUXDB_ORG,
    DEFAULT_INFLUXDB_BUCKET,
)

_LOGGER = logging.getLogger(__name__)

# InfluxDB add-on default URL
INFLUXDB_ADDON_URL = "http://a0d7b954-influxdb:8086"


class InfluxDBLogger:
    """Logger that writes 15-minute energy data to InfluxDB."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the InfluxDB logger."""
        self.hass = hass
        self.entry = entry
        self._remove_listener: Optional[callback] = None
        self._session: Optional[aiohttp.ClientSession] = None

        # Cache config
        self._enabled = False
        self._url = ""
        self._token = ""
        self._org = DEFAULT_INFLUXDB_ORG
        self._bucket = DEFAULT_INFLUXDB_BUCKET

    def _load_config(self) -> None:
        """Load configuration from entry options or data."""
        config = {**self.entry.data, **self.entry.options}

        self._enabled = config.get(CONF_INFLUXDB_ENABLED, False)
        self._url = config.get(CONF_INFLUXDB_URL, "")
        self._token = config.get(CONF_INFLUXDB_TOKEN, "")
        self._org = config.get(CONF_INFLUXDB_ORG, DEFAULT_INFLUXDB_ORG)
        self._bucket = config.get(CONF_INFLUXDB_BUCKET, DEFAULT_INFLUXDB_BUCKET)

        # Auto-detect InfluxDB add-on if URL is empty
        if not self._url and self._enabled:
            self._url = INFLUXDB_ADDON_URL
            _LOGGER.info("InfluxDB URL not configured, using add-on default: %s", self._url)

    async def async_start(self) -> None:
        """Start the InfluxDB logger."""
        self._load_config()

        if not self._enabled:
            _LOGGER.debug("InfluxDB logging is disabled")
            return

        if not self._token:
            _LOGGER.warning("InfluxDB logging enabled but no token configured")
            return

        # Create aiohttp session
        self._session = aiohttp.ClientSession()

        # Schedule writes at 0, 15, 30, 45 minutes
        self._remove_listener = async_track_time_change(
            self.hass,
            self._handle_quarter_hour,
            minute=[0, 15, 30, 45],
            second=30,  # 30 seconds after to ensure sensor has updated
        )

        _LOGGER.info(
            "InfluxDB logger started - writing to %s/%s every 15 minutes",
            self._url,
            self._bucket
        )

    async def async_stop(self) -> None:
        """Stop the InfluxDB logger."""
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

        if self._session:
            await self._session.close()
            self._session = None

        _LOGGER.info("InfluxDB logger stopped")

    async def _handle_quarter_hour(self, _now: datetime) -> None:
        """Handle quarter-hour trigger to write data."""
        if not self._enabled or not self._session:
            return

        try:
            await self._write_data_point()
        except Exception as ex:
            _LOGGER.error("Failed to write to InfluxDB: %s", ex)

    def _read_sensor_state(self, entity_id: Optional[str]) -> Optional[float]:
        """Read a float value from a sensor entity."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _read_presence(self, entity_id: Optional[str]) -> Optional[str]:
        """Read presence value from entity."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state

    async def _write_data_point(self) -> None:
        """Write a data point to InfluxDB."""
        config = {**self.entry.data, **self.entry.options}

        # Read the 15m sensor
        sensor_state = self.hass.states.get("sensor.ec_net_energy_use_on_site_15m")
        if sensor_state is None:
            _LOGGER.warning("15m sensor not found, skipping InfluxDB write")
            return

        # Get value from sensor state
        try:
            value = float(sensor_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid 15m sensor value: %s", sensor_state.state)
            return

        # Get attributes from config entities
        presence = self._read_presence(config.get(CONF_PRESENCE_ENTITY))
        temperature = self._read_sensor_state(config.get(CONF_TEMPERATURE_SENSOR))
        wind_speed = self._read_sensor_state(config.get(CONF_WIND_SENSOR))
        solar_radiation = self._read_sensor_state(config.get(CONF_SOLAR_SENSOR))

        # Build InfluxDB line protocol
        # Measurement: quarter_hourly_net_energy_attr (compatible with forecaster)
        # Tags: presence
        # Fields: value, outside_temperature_meteo, outside_wind_speed, shortwave_radiation
        timestamp = dt_util.utcnow()
        timestamp_ns = int(timestamp.timestamp() * 1e9)

        # Build tags
        tags = []
        if presence:
            # Escape special characters in tag values
            presence_escaped = presence.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")
            tags.append(f"presence={presence_escaped}")

        tags_str = "," + ",".join(tags) if tags else ""

        # Build fields
        fields = [f"value={value}"]
        if temperature is not None:
            fields.append(f"outside_temperature_meteo={temperature}")
        if wind_speed is not None:
            fields.append(f"outside_wind_speed={wind_speed}")
        if solar_radiation is not None:
            fields.append(f"shortwave_radiation={solar_radiation}")

        fields_str = ",".join(fields)

        # Line protocol format: measurement,tags fields timestamp
        line = f"quarter_hourly_net_energy_attr{tags_str} {fields_str} {timestamp_ns}"

        # Write to InfluxDB
        url = f"{self._url}/api/v2/write?org={self._org}&bucket={self._bucket}&precision=ns"
        headers = {
            "Authorization": f"Token {self._token}",
            "Content-Type": "text/plain; charset=utf-8",
        }

        try:
            async with self._session.post(url, data=line, headers=headers) as response:
                if response.status == 204:
                    _LOGGER.debug(
                        "Wrote to InfluxDB: value=%.6f, presence=%s, temp=%s",
                        value, presence, temperature
                    )
                else:
                    text = await response.text()
                    _LOGGER.error(
                        "InfluxDB write failed (status %d): %s",
                        response.status, text
                    )
        except aiohttp.ClientError as ex:
            _LOGGER.error("InfluxDB connection error: %s", ex)
