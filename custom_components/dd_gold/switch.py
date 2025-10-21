from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .coordinator import DresdenGoldCoordinator

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch platform."""
    coordinator: DresdenGoldCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DresdenGoldZeroTaxSwitch(coordinator),
    ]
    async_add_entities(entities)

class DresdenGoldZeroTaxSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for require zero tax."""

    def __init__(self, coordinator: DresdenGoldCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_name = "Dresden Gold Require Zero Tax"
        self._attr_unique_id = "dresden_gold_require_zero_tax"
        self._attr_icon = "mdi:percent"
        self._attr_is_on = coordinator.require_zero_tax

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self._attr_is_on = True
        self.coordinator.update_config(require_zero_tax=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        self.coordinator.update_config(require_zero_tax=False)
        await self.coordinator.async_request_refresh()