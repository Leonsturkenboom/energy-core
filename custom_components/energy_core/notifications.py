"""Notification logic for Energy Core."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@dataclass
class NotificationRule:
    """Represents a notification rule."""
    key: str
    name: str
    message_nl: str
    message_en: str
    severity: str  # "warning", "info", "alarm"
    check_fn: Callable[[dict], bool]
    suppressed_on_holiday: bool = False
    max_per_period: Optional[tuple[int, timedelta]] = None  # (max_count, period)


def _check_data_gap(data: dict) -> bool:
    """Check if any input sensor has been unavailable for > 1 hour."""
    # This would need to be tracked in the coordinator
    return data.get("has_data_gap", False)


def _check_self_sufficiency_record(data: dict) -> bool:
    """Check if today's self-sufficiency is a record."""
    ss_today = data.get("ss_today", 0)
    ss_max_last_30d = data.get("ss_max_last_30d", 0)
    return ss_today > ss_max_last_30d and ss_today > 0.7


def _check_high_export_ratio(data: dict) -> bool:
    """Check if export ratio > 40% over last 7 days."""
    export_7d_avg = data.get("export_7d_avg", 0)
    production_7d_avg = data.get("production_7d_avg", 0)
    if production_7d_avg > 0:
        ratio = export_7d_avg / production_7d_avg
        return ratio > 0.40
    return False


def _check_2x_daily_consumption(data: dict) -> bool:
    """Check if today's consumption > 2x 7-day average."""
    net_use_today = data.get("net_use_today", 0)
    net_use_7d_avg = data.get("net_use_7d_avg", 0)
    return net_use_today > (2 * net_use_7d_avg) if net_use_7d_avg > 0 else False


def _check_4x_daily_consumption(data: dict) -> bool:
    """Check if today's consumption > 4x 7-day average."""
    net_use_today = data.get("net_use_today", 0)
    net_use_7d_avg = data.get("net_use_7d_avg", 0)
    return net_use_today > (4 * net_use_7d_avg) if net_use_7d_avg > 0 else False


def _check_high_night_consumption(data: dict) -> bool:
    """Check if night consumption (24:00-07:00) > 4x 7-day average."""
    night_use_today = data.get("night_use_today", 0)
    night_use_7d_avg = data.get("night_use_7d_avg", 0)
    return night_use_today > (4 * night_use_7d_avg) if night_use_7d_avg > 0 else False


def _check_baseload_trend_up_monthly(data: dict) -> bool:
    """Check if 7-day average > 15% higher than 30-day average."""
    net_use_7d_avg = data.get("net_use_7d_avg", 0)
    net_use_30d_avg = data.get("net_use_30d_avg", 0)
    return net_use_7d_avg > (net_use_30d_avg * 1.15) if net_use_30d_avg > 0 else False


def _check_baseload_trend_up_quarterly(data: dict) -> bool:
    """Check if 30-day average > 15% higher than 90-day average."""
    net_use_30d_avg = data.get("net_use_30d_avg", 0)
    net_use_90d_avg = data.get("net_use_90d_avg", 0)
    return net_use_30d_avg > (net_use_90d_avg * 1.15) if net_use_90d_avg > 0 else False


def _check_co2_emissions_record(data: dict) -> bool:
    """Check if today's emissions are a record low."""
    emissions_today = data.get("emissions_today", 999999)
    emissions_min_last_30d = data.get("emissions_min_last_30d", 999999)
    return emissions_today < emissions_min_last_30d


def _check_net_energy_use_record(data: dict) -> bool:
    """Check if today's net energy use is a record low."""
    net_use_today = data.get("net_use_today", 999999)
    net_use_min_last_30d = data.get("net_use_min_last_30d", 999999)
    return net_use_today < net_use_min_last_30d


def _check_weekly_improvement_goal(data: dict) -> bool:
    """Weekly coaching tip trigger."""
    # This always triggers weekly, logic determines the tip content
    return data.get("is_weekly_trigger", False)


# Define all notification rules
NOTIFICATION_RULES: list[NotificationRule] = [
    NotificationRule(
        key="ec_warning_data_gap",
        name="Warning Data Gap",
        message_nl="Waarschuwing: 1 of meerdere data input is onbeschikbaar.",
        message_en="Warning: One or more data inputs are unavailable.",
        severity="warning",
        check_fn=_check_data_gap,
        suppressed_on_holiday=False,
    ),
    NotificationRule(
        key="ec_info_self_sufficiency_record",
        name="Info Self Sufficiency Record",
        message_nl="Award! Record in zelfvoorzienendheid.",
        message_en="Award! Record in self-sufficiency.",
        severity="info",
        check_fn=_check_self_sufficiency_record,
        suppressed_on_holiday=True,
    ),
    NotificationRule(
        key="ec_tip_reduce_export_increase_self_use",
        name="Tip Reduce Export",
        message_nl="Tip! Je levert veel terug aan het net (>40%). Probeer eigenverbruik te verhogen.",
        message_en="Tip! You export a lot to the grid (>40%). Try to increase self-consumption.",
        severity="info",
        check_fn=_check_high_export_ratio,
        suppressed_on_holiday=True,
        max_per_period=(1, timedelta(days=30)),
    ),
    NotificationRule(
        key="ec_warning_2x_daily_consumption",
        name="Warning 2x Daily Consumption",
        message_nl="Let op! Je hebt een 2x zo hoog verbruik vandaag dan gemiddeld.",
        message_en="Warning! Your consumption today is 2x higher than average.",
        severity="warning",
        check_fn=_check_2x_daily_consumption,
        suppressed_on_holiday=False,
    ),
    NotificationRule(
        key="ec_warning_4x_daily_consumption",
        name="Warning 4x Daily Consumption",
        message_nl="Let op! Je hebt een 4x zo hoog verbruik vandaag dan gemiddeld.",
        message_en="Warning! Your consumption today is 4x higher than average.",
        severity="warning",
        check_fn=_check_4x_daily_consumption,
        suppressed_on_holiday=False,
    ),
    NotificationRule(
        key="ec_warning_high_night_consumption",
        name="Warning High Night Consumption",
        message_nl="Let op! Je hebt een 2x zo hoog verbruik in de nacht dan gemiddeld.",
        message_en="Warning! Your night consumption is 2x higher than average.",
        severity="warning",
        check_fn=_check_high_night_consumption,
        suppressed_on_holiday=False,
    ),
    NotificationRule(
        key="ec_warning_baseload_trend_up",
        name="Warning Baseload Trend Up (Monthly)",
        message_nl="Let op! Je gemiddeld energie verbruik over de laatste maand neemt toe.",
        message_en="Warning! Your average energy consumption over the last month is increasing.",
        severity="warning",
        check_fn=_check_baseload_trend_up_monthly,
        suppressed_on_holiday=False,
    ),
    NotificationRule(
        key="ec_warning_baseload_trend_up_quarterly",
        name="Warning Baseload Trend Up (Quarterly)",
        message_nl="Let op! Je gemiddeld energie verbruik over de laatste 3 maanden neemt toe.",
        message_en="Warning! Your average energy consumption over the last 3 months is increasing.",
        severity="warning",
        check_fn=_check_baseload_trend_up_quarterly,
        suppressed_on_holiday=False,
    ),
    NotificationRule(
        key="ec_info_self_co2_emissions_record",
        name="Info CO2 Emissions Record",
        message_nl="Award! Record in lage CO2 emissies vandaag.",
        message_en="Award! Record low CO2 emissions today.",
        severity="info",
        check_fn=_check_co2_emissions_record,
        suppressed_on_holiday=True,
    ),
    NotificationRule(
        key="ec_info_self_net_energy_use_record",
        name="Info Net Energy Use Record",
        message_nl="Award! Record in laag energieverbruik vandaag.",
        message_en="Award! Record low energy consumption today.",
        severity="info",
        check_fn=_check_net_energy_use_record,
        suppressed_on_holiday=True,
    ),
    NotificationRule(
        key="ec_tip_weekly_improvement_goal",
        name="Weekly Improvement Goal",
        message_nl="Weekly Tip! - ...",  # Dynamic content
        message_en="Weekly Tip! - ...",  # Dynamic content
        severity="info",
        check_fn=_check_weekly_improvement_goal,
        suppressed_on_holiday=False,
    ),
]


def get_active_notifications(
    data: dict,
    presence_mode: str | None,
    language: str = "en",
) -> dict[str, str]:
    """
    Evaluate all notification rules and return active notifications.

    Args:
        data: Dictionary with all required metrics
        presence_mode: Current presence mode (e.g., "Holiday", "Home", etc.)
        language: Language for messages ("nl" or "en")

    Returns:
        Dictionary mapping notification keys to their messages
    """
    active = {}

    is_holiday = presence_mode and presence_mode.lower() == "holiday"

    for rule in NOTIFICATION_RULES:
        # Skip if suppressed on holiday
        if rule.suppressed_on_holiday and is_holiday:
            continue

        # Check if condition is met
        try:
            if rule.check_fn(data):
                message = rule.message_nl if language == "nl" else rule.message_en
                active[rule.key] = message
        except Exception:
            # Silently skip if check fails
            pass

    return active
