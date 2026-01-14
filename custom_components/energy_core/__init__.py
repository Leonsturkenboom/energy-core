from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import EnergyCoreCoordinator
from .influxdb_logger import InfluxDBLogger

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = EnergyCoreCoordinator(hass, entry)

    # Initialize notification metrics store
    await coordinator.async_setup_metrics_store()

    # Start event-driven state listeners
    await coordinator.async_start_listeners()

    # Perform initial data fetch to establish baseline
    # May show "missing_input" if entities aren't ready yet
    await coordinator.async_refresh()

    # Initialize InfluxDB logger (for forecaster)
    influxdb_logger = InfluxDBLogger(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "influxdb_logger": influxdb_logger,
    }

    # Forward to platforms - sensors can now safely access coordinator.data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start InfluxDB logger after sensors are set up
    await influxdb_logger.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].get(entry.entry_id)
        if entry_data:
            # Stop InfluxDB logger
            influxdb_logger = entry_data.get("influxdb_logger")
            if influxdb_logger:
                await influxdb_logger.async_stop()

            # Stop event listeners
            coordinator = entry_data.get("coordinator")
            if coordinator:
                await coordinator.async_stop_listeners()

        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
        if not domain_data:
            hass.data.pop(DOMAIN, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
