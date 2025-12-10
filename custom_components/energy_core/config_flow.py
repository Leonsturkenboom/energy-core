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


class EnergyCoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_IMPORTED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Required(CONF_EXPORTED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Optional(CONF_PRODUCED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Optional(CONF_BATTERY_CHARGE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Optional(CONF_BATTERY_DISCHARGE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
                vol.Required(CONF_CO2_INTENSITY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False)
                ),
                vol.Optional(CONF_PRESENCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False)
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)