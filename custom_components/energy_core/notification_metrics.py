"""Lightweight historical metrics storage for notifications."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class NotificationMetricsStore:
    """Store for notification metrics with 90-day retention."""

    def __init__(self, hass: HomeAssistant, storage_key: str = "energy_core_notification_metrics"):
        """Initialize the metrics store."""
        self.hass = hass
        self.storage_key = storage_key
        self._data: dict[str, Any] = {
            "daily_snapshots": [],  # List of daily snapshots
            "last_updated": None,
        }
        self._loaded = False

    async def async_load(self) -> None:
        """Load data from storage."""
        try:
            store_path = Path(self.hass.config.path(".storage", self.storage_key))
            if store_path.exists():
                with open(store_path, "r") as f:
                    self._data = json.load(f)
                _LOGGER.debug("Loaded notification metrics from storage")
            else:
                _LOGGER.debug("No existing notification metrics found, starting fresh")
        except Exception as e:
            _LOGGER.error(f"Error loading notification metrics: {e}")
            self._data = {"daily_snapshots": [], "last_updated": None}

        self._loaded = True
        await self._cleanup_old_snapshots()

    async def async_save(self) -> None:
        """Save data to storage."""
        if not self._loaded:
            _LOGGER.warning("Cannot save notification metrics before loading")
            return

        try:
            store_path = Path(self.hass.config.path(".storage", self.storage_key))
            store_path.parent.mkdir(parents=True, exist_ok=True)

            self._data["last_updated"] = dt_util.now().isoformat()

            with open(store_path, "w") as f:
                json.dump(self._data, f, indent=2)
            _LOGGER.debug("Saved notification metrics to storage")
        except Exception as e:
            _LOGGER.error(f"Error saving notification metrics: {e}")

    async def _cleanup_old_snapshots(self) -> None:
        """Remove snapshots older than 90 days."""
        cutoff_date = (dt_util.now() - timedelta(days=90)).date().isoformat()
        original_count = len(self._data["daily_snapshots"])

        self._data["daily_snapshots"] = [
            snapshot for snapshot in self._data["daily_snapshots"]
            if snapshot.get("date", "") >= cutoff_date
        ]

        removed_count = original_count - len(self._data["daily_snapshots"])
        if removed_count > 0:
            _LOGGER.debug(f"Cleaned up {removed_count} old snapshots")
            await self.async_save()

    async def add_daily_snapshot(self, snapshot: dict[str, Any]) -> None:
        """
        Add a daily snapshot of metrics.

        Args:
            snapshot: Dictionary with keys like:
                - date: ISO date string (YYYY-MM-DD)
                - net_use: Daily net energy use
                - production: Daily production
                - export: Daily export
                - night_use: Night consumption (00:00-07:00)
                - emissions: Daily CO2 emissions
                - self_sufficiency: Self-sufficiency ratio
        """
        if not self._loaded:
            await self.async_load()

        snapshot_date = snapshot.get("date")
        if not snapshot_date:
            _LOGGER.error("Cannot add snapshot without date")
            return

        # Remove existing snapshot for same date
        self._data["daily_snapshots"] = [
            s for s in self._data["daily_snapshots"]
            if s.get("date") != snapshot_date
        ]

        # Add new snapshot
        self._data["daily_snapshots"].append(snapshot)

        # Sort by date descending (newest first)
        self._data["daily_snapshots"].sort(key=lambda x: x.get("date", ""), reverse=True)

        await self.async_save()
        _LOGGER.debug(f"Added daily snapshot for {snapshot_date}")

    def get_average(self, key: str, days: int) -> float:
        """
        Calculate average value over specified number of days.

        Args:
            key: The metric key (e.g., "net_use", "production")
            days: Number of days to average (7, 30, or 90)

        Returns:
            Average value or 0.0 if insufficient data
        """
        if not self._loaded:
            return 0.0

        cutoff_date = (dt_util.now() - timedelta(days=days)).date().isoformat()
        relevant_snapshots = [
            s for s in self._data["daily_snapshots"]
            if s.get("date", "") >= cutoff_date and key in s
        ]

        if not relevant_snapshots:
            return 0.0

        values = [s[key] for s in relevant_snapshots if isinstance(s.get(key), (int, float))]
        return sum(values) / len(values) if values else 0.0

    def get_min(self, key: str, days: int) -> float:
        """
        Get minimum value over specified number of days.

        Args:
            key: The metric key
            days: Number of days to check (typically 30)

        Returns:
            Minimum value or 999999 if no data
        """
        if not self._loaded:
            return 999999

        cutoff_date = (dt_util.now() - timedelta(days=days)).date().isoformat()
        relevant_snapshots = [
            s for s in self._data["daily_snapshots"]
            if s.get("date", "") >= cutoff_date and key in s
        ]

        if not relevant_snapshots:
            return 999999

        values = [s[key] for s in relevant_snapshots if isinstance(s.get(key), (int, float))]
        return min(values) if values else 999999

    def get_max(self, key: str, days: int) -> float:
        """
        Get maximum value over specified number of days.

        Args:
            key: The metric key
            days: Number of days to check (typically 30)

        Returns:
            Maximum value or 0.0 if no data
        """
        if not self._loaded:
            return 0.0

        cutoff_date = (dt_util.now() - timedelta(days=days)).date().isoformat()
        relevant_snapshots = [
            s for s in self._data["daily_snapshots"]
            if s.get("date", "") >= cutoff_date and key in s
        ]

        if not relevant_snapshots:
            return 0.0

        values = [s[key] for s in relevant_snapshots if isinstance(s.get(key), (int, float))]
        return max(values) if values else 0.0

    def get_today_value(self, key: str) -> float:
        """
        Get today's value for a metric.

        Args:
            key: The metric key

        Returns:
            Today's value or 0.0 if not available
        """
        if not self._loaded:
            return 0.0

        today = dt_util.now().date().isoformat()
        for snapshot in self._data["daily_snapshots"]:
            if snapshot.get("date") == today and key in snapshot:
                return snapshot[key]

        return 0.0

    def has_data_gap(self, sensor_states: dict[str, Any]) -> bool:
        """
        Check if any critical sensor has been unavailable for > 1 hour.

        Args:
            sensor_states: Dictionary mapping sensor entity_ids to their state objects

        Returns:
            True if any sensor has a data gap
        """
        critical_sensors = [
            "sensor.ec_production_day",
            "sensor.ec_consumption_day",
            "sensor.ec_import_day",
            "sensor.ec_export_day",
        ]

        for sensor_id in critical_sensors:
            state = sensor_states.get(sensor_id)
            if not state:
                continue

            if state.state in ["unavailable", "unknown"]:
                # Check if last_changed is > 1 hour ago
                if state.last_changed:
                    time_diff = dt_util.now() - state.last_changed
                    if time_diff > timedelta(hours=1):
                        _LOGGER.warning(f"Data gap detected for {sensor_id}")
                        return True

        return False

    def get_notification_data(self, coordinator_data: dict[str, Any], sensor_states: dict[str, Any]) -> dict[str, Any]:
        """
        Build complete notification data dictionary.

        Args:
            coordinator_data: Current data from coordinator
            sensor_states: Current sensor states from hass

        Returns:
            Dictionary with all metrics needed for notifications
        """
        if not self._loaded:
            return {}

        return {
            # Data gap
            "has_data_gap": self.has_data_gap(sensor_states),

            # Today's values
            "ss_today": self.get_today_value("self_sufficiency"),
            "net_use_today": self.get_today_value("net_use"),
            "night_use_today": self.get_today_value("night_use"),
            "emissions_today": self.get_today_value("emissions"),

            # 7-day averages
            "net_use_7d_avg": self.get_average("net_use", 7),
            "night_use_7d_avg": self.get_average("night_use", 7),
            "export_7d_avg": self.get_average("export", 7),
            "production_7d_avg": self.get_average("production", 7),

            # 30-day averages
            "net_use_30d_avg": self.get_average("net_use", 30),

            # 90-day averages
            "net_use_90d_avg": self.get_average("net_use", 90),

            # Min/max last 30 days
            "ss_max_last_30d": self.get_max("self_sufficiency", 30),
            "emissions_min_last_30d": self.get_min("emissions", 30),
            "net_use_min_last_30d": self.get_min("net_use", 30),

            # Weekly trigger (set by coordinator based on day of week)
            "is_weekly_trigger": coordinator_data.get("is_weekly_trigger", False),
        }
