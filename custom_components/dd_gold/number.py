from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN
from .coordinator import DresdenGoldCoordinator

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the number platform."""
    coordinator: DresdenGoldCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DresdenGoldMinPriceNumber(coordinator),
        DresdenGoldMaxPriceNumber(coordinator),
        DresdenGoldMaxCoinsNumber(coordinator),
    ]
    async_add_entities(entities)

class DresdenGoldNumber(CoordinatorEntity, NumberEntity):
    """Base number entity for Dresden Gold config."""

    def __init__(self, coordinator: DresdenGoldCoordinator, name: str, unique_id: str, icon: str, min_value: float, max_value: float, step: float, value: float) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_value = value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "dresden_gold_config")},
            name="Dresden Gold Configuration",
            manufacturer="Dresden Gold",
            model="Config",
            sw_version="1.0",
            entry_type=None,
            configuration_url="https://www.dresden.gold",
        )

class DresdenGoldMinPriceNumber(DresdenGoldNumber):
    """Number for min price."""

    def __init__(self, coordinator: DresdenGoldCoordinator) -> None:
        super().__init__(
            coordinator,
            "Dresden Gold Min Price",
            "dresden_gold_min_price",
            "mdi:currency-eur",
            0,
            1000,
            0.1,
            coordinator.min_price
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.coordinator.update_config(min_price=value)
        await self.coordinator.async_request_refresh()

class DresdenGoldMaxPriceNumber(DresdenGoldNumber):
    """Number for max price."""

    def __init__(self, coordinator: DresdenGoldCoordinator) -> None:
        super().__init__(
            coordinator,
            "Dresden Gold Max Price",
            "dresden_gold_max_price",
            "mdi:currency-eur",
            0,
            1000,
            0.1,
            coordinator.max_price
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.coordinator.update_config(max_price=value)
        await self.coordinator.async_request_refresh()

class DresdenGoldMaxCoinsNumber(DresdenGoldNumber):
    """Number for max coins."""

    def __init__(self, coordinator: DresdenGoldCoordinator) -> None:
        super().__init__(
            coordinator,
            "Dresden Gold Max Coins",
            "dresden_gold_max_coins",
            "mdi:counter",
            5,
            50,
            1,
            coordinator.max_coins
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.coordinator.update_config(max_coins=int(value))
        await self.coordinator.async_request_refresh()