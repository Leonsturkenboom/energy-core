from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_IMPORTED_ENTITIES,
    CONF_EXPORTED_ENTITIES,
    CONF_PRODUCED_ENTITIES,
    CONF_BATTERY_CHARGE_ENTITIES,
    CONF_BATTERY_DISCHARGE_ENTITIES,
    CONF_CO2_INTENSITY_ENTITY,
    CONF_PRESENCE_ENTITY,
)


ALLOWED_ENERGY_UNITS = {"kwh", "wh"}
REQUIRED_STATE_CLASSES = {"total_increasing", "total"}  # Some integrations still use "total"


def _dedupe(items: list[str]) -> list[str]:
    """Preserve order while deduping."""
    return list(dict.fromkeys(items or []))


class EnergyCoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def _validate_energy_list(self, entity_ids: list[str]) -> dict[str, str]:
        """
        Validate energy total entities.
        Returns: dict(entity_id -> error_key)
        Soft-fail when entity state is unavailable during setup/startup.
        """
        invalid: dict[str, str] = {}

        for eid in entity_ids or []:
            st = self.hass.states.get(eid)
            if st is None:
                # Don't hard fail if entity isn't available right now
                continue

            unit = (st.attributes.get("unit_of_measurement") or "").lower().strip()
            if unit not in ALLOWED_ENERGY_UNITS:
                invalid[eid] = "invalid_unit"
                continue

            state_class = (st.attributes.get("state_class") or "").lower().strip()
            # If state_class is missing, we allow it (some integrations omit it),
            # but if present, it must be total/total_increasing.
            if state_class and state_class not in REQUIRED_STATE_CLASSES:
                invalid[eid] = "invalid_state_class"
                continue

            device_class = (st.attributes.get("device_class") or "").lower().strip()
            # device_class may be missing; if present and wrong, flag it (still a config error)
            if device_class and device_class != "energy":
                invalid[eid] = "invalid_device_class"

        return invalid

    def _validate_co2_entity(self, entity_id: str) -> bool:
        """
        Soft validation for CO2 intensity sensor.
        We don't enforce exact unit strings to avoid breaking setups,
        but we do basic sanity checks.
        """
        if not entity_id:
            return False

        st = self.hass.states.get(entity_id)
        if st is None:
            return True  # don't hard fail during startup

        unit = (st.attributes.get("unit_of_measurement") or "").lower().strip()
        if not unit:
            return False

        # Very light heuristic:
        # must relate to kWh and CO2 (or g)
        if "kwh" not in unit:
            return False

        if ("co2" not in unit) and ("g" not in unit):
            return False

        return True

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        placeholders: dict[str, dict[str, str]] = {}

        if user_input is not None:
            # Dedupe lists (prevents double counting)
            imported = _dedupe(user_input.get(CONF_IMPORTED_ENTITIES, []))
            exported = _dedupe(user_input.get(CONF_EXPORTED_ENTITIES, []))
            produced = _dedupe(user_input.get(CONF_PRODUCED_ENTITIES, []))
            charge = _dedupe(user_input.get(CONF_BATTERY_CHARGE_ENTITIES, []))
            discharge = _dedupe(user_input.get(CONF_BATTERY_DISCHARGE_ENTITIES, []))

            user_input[CONF_IMPORTED_ENTITIES] = imported
            user_input[CONF_EXPORTED_ENTITIES] = exported
            user_input[CONF_PRODUCED_ENTITIES] = produced
            user_input[CONF_BATTERY_CHARGE_ENTITIES] = charge
            user_input[CONF_BATTERY_DISCHARGE_ENTITIES] = discharge

            # Validate energy lists independently (field-level errors)
            invalid_imported = self._validate_energy_list(imported)
            invalid_exported = self._validate_energy_list(exported)
            invalid_produced = self._validate_energy_list(produced)
            invalid_charge = self._validate_energy_list(charge)
            invalid_discharge = self._validate_energy_list(discharge)

            def _set_field_error(field: str, invalid_map: dict[str, str]) -> None:
                if not invalid_map:
                    return
                # Single key for UI; list entities in placeholders
                errors[field] = "invalid_energy_entities"
                placeholders[field] = {"entities": ", ".join(invalid_map.keys())}

            _set_field_error(CONF_IMPORTED_ENTITIES, invalid_imported)
            _set_field_error(CONF_EXPORTED_ENTITIES, invalid_exported)
            _set_field_error(CONF_PRODUCED_ENTITIES, invalid_produced)
            _set_field_error(CONF_BATTERY_CHARGE_ENTITIES, invalid_charge)
            _set_field_error(CONF_BATTERY_DISCHARGE_ENTITIES, invalid_discharge)

            # Validate CO2 entity (hard fail if clearly wrong)
            co2_eid = user_input.get(CONF_CO2_INTENSITY_ENTITY)
            if not self._validate_co2_entity(co2_eid):
                errors[CONF_CO2_INTENSITY_ENTITY] = "invalid_co2_unit"

            # Fallback base error (older UI behavior)
            if errors:
                errors["base"] = "invalid_config"

            if not errors:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                # Energy totals (only sensors; user may select multiple)
                vol.Required(CONF_IMPORTED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Required(CONF_EXPORTED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Optional(CONF_PRODUCED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_CHARGE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_DISCHARGE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),

                # CO2 intensity (single sensor)
                vol.Required(CONF_CO2_INTENSITY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False, domain="sensor")
                ),

                # Presence can be a person, input_select, sensor, etc.
                vol.Optional(CONF_PRESENCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )
