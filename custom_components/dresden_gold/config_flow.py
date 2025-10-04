import voluptuous as vol
from typing import Any
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from .const import (
    DOMAIN,
    CONF_MIN_PRICE,
    CONF_MAX_PRICE,
    CONF_MAX_COINS,
    CONF_REQUIRE_ZERO_TAX,
    DEFAULT_MIN_PRICE,
    DEFAULT_MAX_PRICE,
    DEFAULT_MAX_COINS,
    DEFAULT_REQUIRE_ZERO_TAX,
)

class DresdenGoldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dresden Gold."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Dresden Gold", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_data_schema()
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return DresdenGoldOptionsFlow(config_entry)

    @staticmethod
    def _get_data_schema(defaults: dict | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_MIN_PRICE,
                    default=defaults.get(CONF_MIN_PRICE, DEFAULT_MIN_PRICE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1000, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_MAX_PRICE,
                    default=defaults.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1000, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_MAX_COINS,
                    default=defaults.get(CONF_MAX_COINS, DEFAULT_MAX_COINS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_REQUIRE_ZERO_TAX,
                    default=defaults.get(CONF_REQUIRE_ZERO_TAX, DEFAULT_REQUIRE_ZERO_TAX),
                ): selector.BooleanSelector(),
            }
        )

class DresdenGoldOptionsFlow(config_entries.OptionsFlow):
    """Dresden Gold config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=DresdenGoldConfigFlow._get_data_schema(self.config_entry.data)
        )