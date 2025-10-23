import logging
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from homeassistant.util.dt import utcnow
from collections import defaultdict
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from .const import DOMAIN, WEIGHT_CODES, WEIGHT_DISPLAY, CONF_MIN_PRICE, CONF_MAX_PRICE, CONF_MAX_COINS, CONF_REQUIRE_ZERO_TAX, DEFAULT_UPDATE_INTERVAL, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_REQUIRE_ZERO_TAX, DEFAULT_MAX_COINS

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
        self.max_coins = int(entry.data.get(CONF_MAX_COINS, DEFAULT_MAX_COINS))
        self.require_zero_tax = entry.data.get(CONF_REQUIRE_ZERO_TAX, DEFAULT_REQUIRE_ZERO_TAX)
        self.base_url = "https://www.dresden.gold"
        self.session = aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        self.last_update_success_time: Optional[datetime] = None

    async def _async_update_data(self) -> dict:
        """Fetch data from API."""
        try:
            weight_slugs = {
                "0.5_oz": "1-2-unze",
                "1_oz": "1-unze",
                #"1.5_oz": "1-5-unzen",
                "2_oz": "2-unzen",
                "5_oz": "5-unzen",
                "10_oz": "10-unzen",
            }

            async def fetch_weight(weight):
                if weight not in weight_slugs:
                    return weight, {}
                slug = weight_slugs[weight]
                category_url = f"{self.base_url}/silber/silbermuenzen/{slug}.html?limit=all"
                _LOGGER.debug(f"Fetch {weight=}: {category_url}")
                coins = await self.scrape_coins_for_weight(weight, category_url)
                group_coins = sorted(coins, key=lambda x: float(x['price']))[:self.max_coins]
                if group_coins:
                    prices = [float(c['price']) for c in group_coins]
                    return weight, {
                        "coins": group_coins,
                        "min_price": min(prices),
                        "max_price": max(prices),
                        "average_price": sum(prices) / len(prices),
                        "total_coins": len(group_coins),
                    }
                return weight, {}

            tasks = [fetch_weight(weight) for weight in WEIGHT_CODES]
            results = await asyncio.gather(*tasks)
            data = {weight: info for weight, info in results if info}
        except Exception as err:
            _LOGGER.error(f"Error fetching data: {repr(err)}")
            raise UpdateFailed(f"Error fetching data: {err}")
        else:
            self.last_update_success_time = utcnow()
            return data

    def update_config(self, min_price=None, max_price=None, max_coins=None, require_zero_tax=None):
        """Update configuration values."""
        if min_price is not None:
            self.min_price = min_price
        if max_price is not None:
            self.max_price = max_price
        if max_coins is not None:
            self.max_coins = int(max_coins)
        if require_zero_tax is not None:
            self.require_zero_tax = require_zero_tax
        self.async_set_updated_data(self.data)  # Trigger refresh

    async def scrape_coins_for_weight(self, weight_code: str, url: str) -> List[Dict[str, str]]:
        soup = await self.fetch_page(url)
        if not soup:
            return []

        coins: List[Dict[str, str]] = []
        product_items = soup.find_all('li', class_='item')  # Assuming common Magento/Shop structure; adjust if needed

        _LOGGER.info(f"Product items ({weight_code=}): {len(product_items)}")

        for item in product_items:
            #_LOGGER.debug(f"{item=}")
            try:
                name_el = item.select_one('h2.product-name a') or item.select_one('a.product-image[title]')
                _LOGGER.debug(f"{name_el=}")
                if not name_el:
                    continue
                name = name_el.text.strip() if name_el.text else name_el.get('title', '').strip()
                _LOGGER.debug(f"{name=}")
                if not name:
                    continue

                item_url = name_el['href']
                _LOGGER.debug(f"{item_url=}")
                if not item_url.startswith('http'):
                    item_url = self.base_url + item_url

                mwst_price_el = item.select_one('span.price')
                _LOGGER.debug(f"{mwst_price_el=}")
                if not mwst_price_el:
                    continue

                mwst_price_str = mwst_price_el.text.strip().replace('€', '').replace(',', '.').replace(' ', '')
                mwst_price = float(re.sub(r'[^\d.]', '', mwst_price_str))
                _LOGGER.debug(f"{mwst_price=}")
                if mwst_price < 0:
                    continue

                price_el = item.select_one('span.regular-price').select_one('span[itemprop="price"]')
                _LOGGER.debug(f"{price_el=}")
                if not price_el:
                    continue

                price_str = price_el.text.strip().replace('€', '').replace(',', '.').replace(' ', '')
                price = float(re.sub(r'[^\d.]', '', price_str))
                _LOGGER.debug(f"{price=}")
                if price <= 0:
                    continue

                is_zero_tax = mwst_price==0.0 or self.is_zero_tax(item)
                _LOGGER.debug(f"{is_zero_tax=}")
                if self.require_zero_tax and not is_zero_tax:
                    continue

                if not (self.min_price <= price <= self.max_price):
                    continue


                avail_el = item.select_one('span.regular-price').select_one('link[itemprop="availability"]')
                _LOGGER.debug(f"{avail_el=}")
                if not avail_el:
                    continue

                is_available, qty, available_label = self.parse_availability_text(item)
                _LOGGER.debug(f"{is_available}, {qty=}, {available_label=}")
                if not is_available or (qty is not None and qty <= 0):
                    continue

                name = self.clean_name(name)
                if not self.is_valid_coin_name(name):
                    continue

                coin = {
                    "name": name,
                    "price": f"{round(price, 2):.2f}",
                    "mwst_price": f"{round(mwst_price, 2):.2f}",
                    "weight": WEIGHT_DISPLAY.get(weight_code, "Unknown"),
                    "weight_code": weight_code,
                    "tax_rate": f"{round(mwst_price/(price-mwst_price) if price else 0.0,2)}",
                    "availability": available_label,
                    "qty": str(qty) if qty is not None else "",
                    "url": item_url,
                }
                coins.append(coin)
            except ValueError as ve:
                _LOGGER.debug(f"Value error parsing item: {ve}")
            except Exception as e:
                _LOGGER.warning(f"Error parsing product item: {e}")

        _LOGGER.debug(f"Scraped {len(coins)} coins for weight {weight_code}")
        return coins

    # async def fetch_page(self) -> Optional[BeautifulSoup]:
    #     try:
    #         async with self.session.get(self.target_url, timeout=12) as response:
    #             if response.status != 200:
    #                 _LOGGER.warning(f"Failed to fetch page: status {response.status}")
    #                 return None
    #             text = await response.text()
    #             return BeautifulSoup(text, 'html.parser')
    #     except Exception as e:
    #         _LOGGER.warning(f"Fetch page error: {e}")
    #         return None
    
    async def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        try:
            async with self.session.get(url, timeout=12) as response:
                if response.status != 200:
                    _LOGGER.warning(f"Failed to fetch {url}: status {response.status}")
                    return None
                text = await response.text()
                return BeautifulSoup(text, 'html.parser')
        except Exception as e:
            _LOGGER.warning(f"Fetch error for {url}: {e}")
            return None

    def extract_price(self, soup: BeautifulSoup, from_detail: bool = False) -> float:
        try:
            if from_detail:
                price_el = soup.select_one('.price-including-tax .price, [itemprop="price"]')
            else:
                price_el = soup.select_one('.price')
            if price_el:
                price_str = price_el.text.strip().replace('€', '').replace(',', '.').replace(' ', '')
                return float(re.sub(r'[^\d.]', '', price_str))
        except:
            pass
        return 0.0

    def is_zero_tax(self, soup: BeautifulSoup) -> bool:
        text = soup.get_text(strip=True).lower()
        
        _LOGGER.debug(f"is_zero_tax? {text=}")
        patterns = [
            r'0[.,]00\s*€?\s*mwst',
            r'mwst[.:]\s*0[.,]00\s*€?',
            r'inkl[.\s]*0[.,]00\s*€?\s*mwst',
            r'zzgl[.\s]*0[.,]00\s*€?\s*mwst',
            r'0[.,]00\s*%\s*mwst',
            r'mwst[.:]\s*0[.,]00\s*%',
            r'keine mwst', r'mwst\s*0'
        ]
        
        for pattern in patterns:
            if re.search(pattern, text):
                _LOGGER.debug(f"is_zero_tax! {pattern=}")
                return True
        
        keywords = [
            'differenzbesteuert', 'mwstfrei', 'mwst-frei', 'steuerbefreit',
            'ohne mwst', 'mwst 0', '0% mwst', 'tax free', 'steuerfrei',
            'differenzbesteuerung', '§25a ustg', 'differenzbesteuerung nach §25a ustg',
            'keine umsatzsteuer', 'umsatzsteuerfrei'
        ]
        
        for keyword in keywords:
            if keyword in text:
                _LOGGER.debug(f"is_zero_tax! {keyword=}")
                return True
        
        _LOGGER.debug("is_zero_tax? -> NO")
        return False

    def is_valid_coin_name(self, name: str) -> bool:
        if not name or len(name) < 5:
            return False
        bad = ['in absteigender reihenfolge', 'sortierung', 'filter', 'seite', 'wunschliste', 'vergleich', 'details', 'bewertung']
        if any(b in name.lower() for b in bad):
            return False
        good = ['münze', 'coin', 'silber', 'silver', 'oz', 'unze', 'eagle', 'maple', 'krugerrand', 'britannia', 'panda', 'kangaroo', 'lunar', 'libertad', 'philharmoniker']
        return any(k in name.lower() for k in good)

    def clean_name(self, name: str) -> str:
        name = re.sub(r'<[^>]+>', '', name or '')
        name = ' '.join(name.split()).strip()
        return name[:60] + "..." if len(name) > 60 else name

    def parse_availability_text(self, soup: BeautifulSoup) -> Tuple[bool, Optional[int], str]:
        text = soup.get_text(strip=True).lower()

        if any(x in text for x in ['nicht verfügbar', 'ausverkauft', 'out of stock', 'derzeit nicht', 'vorübergehend nicht']):
            return (False, 0, "Nicht verfügbar")

        if any(x in text for x in ['auf lager', 'lagernd', 'verfügbar', 'in stock', 'sofort lieferbar']):
            m_qty = re.search(r'(-?\d+)\s*(?:stk|stück|verfügbar|lagernd)', text)
            if m_qty:
                qty = int(m_qty.group(1))
                return (qty > 0, qty, "Auf Lager" if qty > 0 else "Nicht verfügbar")
            return (True, None, "Auf Lager")

        avail_el = soup.find(attrs={"itemprop": "availability"})
        if avail_el:
            href = avail_el.get('href', '').lower()
            if 'instock' in href:
                return (True, None, "Auf Lager")
            if 'outofstock' in href:
                return (False, 0, "Nicht verfügbar")

        m_qty2 = re.search(r'(\d+)\s*(?:stk|stück|verfügbar|lagernd)', text)
        if m_qty2:
            qty = int(m_qty2.group(1))
            return (qty > 0, qty, "Auf Lager" if qty > 0 else "Nicht verfügbar")

        # Default assume available if no info
        return (True, None, "Verfügbarkeit unbekannt")