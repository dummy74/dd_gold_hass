from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, WEIGHT_CODES, WEIGHT_DISPLAY
from .coordinator import DresdenGoldCoordinator
import json

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator: DresdenGoldCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for weight in WEIGHT_CODES:
        entities.append(DresdenGoldCoinsSensor(coordinator, weight))
        entities.append(DresdenGoldMinSensor(coordinator, weight))
        entities.append(DresdenGoldMaxSensor(coordinator, weight))
        entities.append(DresdenGoldAverageSensor(coordinator, weight))
    async_add_entities(entities)

class DresdenGoldBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Dresden Gold."""

    def __init__(self, coordinator: DresdenGoldCoordinator, weight: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._weight = weight
        self._attr_icon = "mdi:gold"
        self._attr_unique_id = f"dresden_gold_{weight}_{self.sensor_type}"
        self._attr_name = f"Dresden Gold {WEIGHT_DISPLAY.get(weight, weight)} {self.sensor_type.capitalize()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"dresden_gold_{weight}")},
            name=f"Dresden Gold {WEIGHT_DISPLAY.get(weight, weight)}",
            manufacturer="Dresden Gold",
            model="Silver Coin Tracker",
            sw_version="1.0",
            entry_type=None,
            configuration_url="https://www.dresden.gold",
        )

    @property
    def data(self):
        return self.coordinator.data.get(self._weight, {})

class DresdenGoldCoinsSensor(DresdenGoldBaseSensor):
    """Sensor for coins list."""

    sensor_type = "coins"

    @property
    def state(self) -> str:
        return str(self.data.get("total_coins", 0))

    @property
    def unit_of_measurement(self) -> str:
        return "coins"

    @property
    def extra_state_attributes(self) -> dict:
        coins = self.data.get("coins", [])
        attrs = {
            #"coins_json": json.dumps(coins),
            "last_update": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
        }
        for i, coin in enumerate(coins, 1):
            attrs[f"coin_{i}_name"] = coin["name"]
            attrs[f"coin_{i}_price"] = coin["price"]
            attrs[f"coin_{i}_mwst_price"] = coin["mwst_price"]
            attrs[f"coin_{i}_tax_rate"] = coin["tax_rate"]
            attrs[f"coin_{i}_weight"] = coin["weight"]
            attrs[f"coin_{i}_qty"] = coin.get("qty", "0")
            attrs[f"coin_{i}_url"] = coin["url"]
        return attrs

class DresdenGoldMinSensor(DresdenGoldBaseSensor):
    """Sensor for min price."""

    sensor_type = "min"

    @property
    def state(self) -> float:
        return self.data.get("min_price", 0.0)

    @property
    def unit_of_measurement(self) -> str:
        return "€"

    @property
    def state_class(self) -> SensorStateClass:
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> dict:
        coins = self.data.get("coins", [])
        if coins:
            cheapest = coins[0]
            return {
                "coin_name": cheapest["name"],
                "url": cheapest["url"],
                "availability": cheapest["availability"],
                "weight": cheapest["weight"],
                "qty": cheapest.get("qty", ""),
                "mwst_price": cheapest.get("mwst_price", ""),
                "tax_rate": cheapest.get("tax_rate"),
                "last_update": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
            }
        return {}

class DresdenGoldMaxSensor(DresdenGoldBaseSensor):
    """Sensor for max price."""

    sensor_type = "max"

    @property
    def state(self) -> float:
        return self.data.get("max_price", 0.0)

    @property
    def unit_of_measurement(self) -> str:
        return "€"

    @property
    def state_class(self) -> SensorStateClass:
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> dict:
        coins = self.data.get("coins", [])
        if coins:
            most_expensive = coins[-1]
            return {
                "coin_name": most_expensive["name"],
                "url": most_expensive["url"],
                "availability": most_expensive["availability"],
                "weight": most_expensive["weight"],
                "qty": most_expensive.get("qty", ""),
                "mwst_price": most_expensive.get("mwst_price", ""),
                "tax_rate": most_expensive.get("tax_rate"),
                "last_update": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
            }
        return {}

class DresdenGoldAverageSensor(DresdenGoldBaseSensor):
    """Sensor for average price."""

    sensor_type = "average"

    @property
    def state(self) -> float:
        return round(self.data.get("average_price", 0.0), 2)

    @property
    def unit_of_measurement(self) -> str:
        return "€"

    @property
    def state_class(self) -> SensorStateClass:
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "sample_size": str(self.data.get("total_coins", 0)),
            "price_range": f"{self.data.get('min_price', 0)}€ - {self.data.get('max_price', 0)}€",
            "last_update": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
        }