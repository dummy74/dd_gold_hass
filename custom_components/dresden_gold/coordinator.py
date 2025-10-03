import logging
import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from urllib.parse import urlparse, urlunparse
from collections import defaultdict
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from .const import DOMAIN, WEIGHT_CODES, WEIGHT_DISPLAY, CONF_MIN_PRICE, CONF_MAX_PRICE, CONF_MAX_COINS, CONF_REQUIRE_ZERO_TAX, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

class DresdenGoldCoordinator(DataUpdateCoordinator):
    """Dresden Gold data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.entry = entry
        self.min_price = entry.data.get(CONF_MIN_PRICE, DEFAULT_MIN_PRICE)
        self.max_price = entry.data.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE)
        self.max_coins = entry.data.get(CONF_MAX_COINS, DEFAULT_MAX_COINS)
        self.require_zero_tax = entry.data.get(CONF_REQUIRE_ZERO_TAX, DEFAULT_REQUIRE_ZERO_TAX)
        self.base_url = "https://www.dresden.gold"
        self.target_url = "https://www.dresden.gold/silber/silbermuenzen.html?___store=deutsch&limit=all"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    async def _async_update_data(self) -> dict:
        """Fetch data from API."""
        try:
            coins = await self.hass.async_add_executor_job(self.scrape_silver_coins)
            coins_by_weight = defaultdict(list)
            for c in coins:
                coins_by_weight[c['weight_code']].append(c)

            data = {}
            for weight in WEIGHT_CODES:
                group_coins = sorted(coins_by_weight[weight], key=lambda x: float(x['price']))[:self.max_coins]
                if group_coins:
                    prices = [float(c['price']) for c in group_coins]
                    data[weight] = {
                        "coins": group_coins,
                        "min_price": min(prices),
                        "max_price": max(prices),
                        "average_price": sum(prices) / len(prices),
                        "total_coins": len(group_coins),
                    }
            return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")

    def scrape_silver_coins(self) -> List[Dict[str, str]]:
        soup = self.fetch_page()
        if not soup:
            return []

        coins: List[Dict[str, str]] = []
        product_links = soup.find_all('a', href=re.compile(r'/silber/.*\.html'))
        _LOGGER.debug(f"Found {len(product_links)} product links")

        detail_count = 0

        for link in product_links:
            try:
                item = link
                while item and item.name not in ['li', 'div']:
                    item = item.parent
                if not item:
                    continue

                name = self.clean_name(link.get('title') or link.get_text(strip=True))
                if not self.is_valid_coin_name(name):
                    continue

                url = self.base_url + link['href'] if not link['href'].startswith('http') else link['href']

                detected_weight = self.detect_coin_weight(item)
                if not detected_weight:
                    continue

                is_zero_tax = self.is_zero_tax(item)
                if self.require_zero_tax and not is_zero_tax:
                    continue

                price = self.extract_price(item)
                if price <= 0:
                    continue

                is_available, qty, available_label = self.parse_availability_text(item)

                detailed_weight = detected_weight
                detailed_price = price
                detailed_zero_tax = is_zero_tax
                if detail_count < self.max_coins:  # Assuming max_detail = max_coins
                    is_available, qty, available_label, detailed_zero_tax, detailed_price, detailed_weight_temp = self.fetch_product_details(url)
                    if detailed_weight_temp:
                        detailed_weight = detailed_weight_temp
                    detail_count += 1

                if not detailed_weight:
                    continue

                if self.require_zero_tax and not detailed_zero_tax:
                    continue

                if detailed_price <= 0 or not (self.min_price <= detailed_price <= self.max_price):
                    continue

                if not is_available or (qty is not None and qty <= 0):
                    continue

                coin = {
                    "name": name,
                    "price": f"{round(detailed_price, 2):.2f}",
                    "weight": WEIGHT_DISPLAY.get(detailed_weight, "Unknown"),
                    "weight_code": detailed_weight,
                    "tax_rate": "0,00%" if detailed_zero_tax else "19,00%",
                    "availability": available_label,
                    "qty": "0" if qty is None else str(qty),
                    "url": url,
                    "last_updated": datetime.now().isoformat()
                }
                coins.append(coin)
            except Exception as e:
                _LOGGER.debug(f"Error processing product link: {e}")
                continue

        best_by_key = {}
        for c in coins:
            norm_url = self.normalize_url(c['url'])
            c['url'] = norm_url
            coin_key = self.create_coin_key(c['name'], c['weight_code'], norm_url)
            
            if coin_key in best_by_key:
                best_by_key[coin_key] = self.choose_better_coin(best_by_key[coin_key], c)
            else:
                best_by_key[coin_key] = c

        coins = list(best_by_key.values())
        coins = [c for c in coins if c.get('qty','0') != '0']
        coins = sorted(coins, key=lambda x: float(x['price']))
        _LOGGER.debug(f"Final coins: {len(coins)} (details fetched: {detail_count})")
        return coins

    # Rest of the methods (fetch_page, extract_price, etc.) similar to previous dresden_gold_scraper.py
    # I'll omit them here for brevity, but copy them from the previous version, replacing self.log with _LOGGER.debug or .error

    def fetch_page(self) -> Optional[BeautifulSoup]:
        try:
            r = self.session.get(self.target_url, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.content, 'html.parser')
        except Exception as e:
            _LOGGER.error(f"Error fetching list page: {e}")
            return None

    # ... (include all other methods like extract_price, detect_coin_weight, etc.)
