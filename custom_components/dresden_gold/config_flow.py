from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MIN_PRICE, default=DEFAULT_MIN_PRICE): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=1000, step=0.1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(CONF_MAX_PRICE, default=DEFAULT_MAX_PRICE): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=1000, step=0.1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(CONF_MAX_COINS, default=DEFAULT_MAX_COINS): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(CONF_REQUIRE_ZERO_TAX, default=DEFAULT_REQUIRE_ZERO_TAX): bool,
                }
            ),
        )

    @staticmethod
    def async_get_options_schema() -> vol.Schema:
        """Return the options schema."""
        return vol.Schema(
            {
                vol.Required(CONF_MIN_PRICE, default=DEFAULT_MIN_PRICE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1000, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_MAX_PRICE, default=DEFAULT_MAX_PRICE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1000, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_MAX_COINS, default=DEFAULT_MAX_COINS): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_REQUIRE_ZERO_TAX, default=DEFAULT_REQUIRE_ZERO_TAX): bool,
            }
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration."""
        if user_input is not None:
            return self.async_update_entry(self.hass.config_entries.async_get_entry(self.context["entry_id"]), data=user_input)

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.async_get_options_schema().extend(entry.data)
        )