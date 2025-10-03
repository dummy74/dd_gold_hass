DOMAIN = "dresden_gold"

CONF_MIN_PRICE = "min_price"
CONF_MAX_PRICE = "max_price"
CONF_MAX_COINS = "max_coins"
CONF_REQUIRE_ZERO_TAX = "require_zero_tax"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_MIN_PRICE = 15.0
DEFAULT_MAX_PRICE = 100.0
DEFAULT_MAX_COINS = 50
DEFAULT_REQUIRE_ZERO_TAX = True
DEFAULT_UPDATE_INTERVAL = 300  # seconds

WEIGHT_CODES = ["0.5_oz", "1_oz", "2_oz", "5_oz", "10_oz"]
WEIGHT_DISPLAY = {
    "0.5_oz": "0.5 oz",
    "1_oz": "1 oz",
    "2_oz": "2 oz",
    "5_oz": "5 oz",
    "10_oz": "10 oz"
}