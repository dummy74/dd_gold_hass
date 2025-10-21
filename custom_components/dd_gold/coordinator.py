import logging
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from urllib.parse import urlparse, urlunparse
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
        self.max_coins = entry.data.get(CONF_MAX_COINS, DEFAULT_MAX_COINS)
        self.require_zero_tax = entry.data.get(CONF_REQUIRE_ZERO_TAX, DEFAULT_REQUIRE_ZERO_TAX)
        self.base_url = "https://www.dresden.gold"
        self.target_url = "https://www.dresden.gold/silber/silbermuenzen.html?___store=deutsch&limit=all"
        self.session = aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    async def _async_update_data(self) -> dict:
        """Fetch data from API."""
        try:
            coins = await self.scrape_silver_coins()
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
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")
        else:
            return data

    def update_config(self, min_price=None, max_price=None, max_coins=None, require_zero_tax=None):
        """Update configuration values."""
        if min_price is not None:
            self.min_price = min_price
        if max_price is not None:
            self.max_price = max_price
        if max_coins is not None:
            self.max_coins = max_coins
        if require_zero_tax is not None:
            self.require_zero_tax = require_zero_tax
        self.async_set_updated_data(self.data)  # Trigger refresh

    async def scrape_silver_coins(self) -> List[Dict[str, str]]:
        soup = await self.fetch_page()
        if not soup:
            return []

        coins: List[Dict[str, str]] = []
        product_links = soup.find_all('a', href=re.compile(r'/silber/.*\.html'))
        _LOGGER.debug(f"Found {len(product_links)} product links")

        potential_coins = []

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

                if not is_available or (qty is not None and qty <= 0):
                    continue

                coin = {
                    "name": name,
                    "price": f"{round(price, 2):.2f}",
                    "weight": WEIGHT_DISPLAY.get(detected_weight, "Unknown"),
                    "weight_code": detected_weight,
                    "tax_rate": "0,00%" if is_zero_tax else "19,00%",
                    "availability": available_label,
                    "qty": "0" if qty is None else str(qty),
                    "url": url,
                }
                potential_coins.append(coin)
            except Exception as e:
                _LOGGER.debug(f"Error processing link: {e}")

        # Sort potential coins by initial price to prioritize cheapest for detail fetching
        potential_coins.sort(key=lambda x: float(x['price']))

        # Fetch details for up to max_coins cheapest potential coins in parallel
        urls_to_fetch = [coin['url'] for coin in potential_coins[:self.max_coins]]
        if urls_to_fetch:
            tasks = [self.fetch_product_details(url) for url in urls_to_fetch]
            details_list = await asyncio.gather(*tasks, return_exceptions=True)
            for i, details in enumerate(details_list):
                if isinstance(details, Exception):
                    _LOGGER.warning(f"Detail fetch error for {urls_to_fetch[i]}: {details}")
                    continue
                is_available, qty, available_label, detailed_zero_tax, detailed_price, detailed_weight = details
                coin = potential_coins[i]
                if detailed_weight:
                    coin['weight_code'] = detailed_weight
                    coin['weight'] = WEIGHT_DISPLAY.get(detailed_weight, "Unknown")
                coin['tax_rate'] = "0,00%" if detailed_zero_tax else "19,00%"
                if detailed_price > 0:
                    coin['price'] = f"{round(detailed_price, 2):.2f}"
                coin['availability'] = available_label
                coin['qty'] = str(qty) if qty is not None else "0"

        # Now filter all potential coins based on (detailed where available) values
        filtered_coins = []
        for coin in potential_coins:
            price_f = float(coin['price'])
            zero_tax = coin['tax_rate'] == "0,00%"
            if self.require_zero_tax and not zero_tax:
                continue
            if not (self.min_price <= price_f <= self.max_price):
                continue
            qty_int = int(coin['qty']) if coin['qty'].isdigit() else None
            is_avail = coin['availability'] != "Nicht verfügbar"
            if not is_avail or (qty_int is not None and qty_int <= 0):
                continue
            filtered_coins.append(coin)

        return filtered_coins

    async def fetch_page(self) -> Optional[BeautifulSoup]:
        try:
            async with self.session.get(self.target_url, timeout=12) as response:
                if response.status != 200:
                    _LOGGER.warning(f"Failed to fetch page: status {response.status}")
                    return None
                text = await response.text()
                return BeautifulSoup(text, 'html.parser')
        except Exception as e:
            _LOGGER.warning(f"Fetch page error: {e}")
            return None

    def extract_price(self, soup: BeautifulSoup, from_detail: bool = False) -> float:
        try:
            if from_detail:
                price_el = soup.select_one('.price, [itemprop="price"], .product-price')
                text = price_el.get_text(strip=True) if price_el else str(soup)
            else:
                text = soup.get_text(strip=True)

            patterns = [
                r'(\d+[.,]\d{2})\s*€', 
                r'€\s*(\d+[.,]\d{2})', 
                r'(\d+[.,]\d{2})', 
                r'(\d+)\s*€'
            ]
            for p in patterns:
                m = re.search(p, text)
                if m:
                    price = float(m.group(1).replace(',', '.'))
                    if self.min_price <= price <= self.max_price:
                        return price
        except Exception as e:
            _LOGGER.debug(f"Price extraction error: {e}")
        return 0.0

    def detect_coin_weight(self, soup: BeautifulSoup, from_detail: bool = False) -> Optional[str]:
        text = soup.get_text(strip=True).lower()
        
        patterns = [
            (r'\b10\s*oz\b|\b10\s*unze\b|\b10\s*troy\s*oz\b|\b311\s*(?:[.,]1)?\s*g\b|\b311\s*gramm\b', "10_oz"),
            (r'\b5\s*oz\b|\b5\s*unze\b|\b5\s*troy\s*oz\b|\b155[.,]5\s*g\b|\b155\s*gramm\b', "5_oz"),
            (r'\b2\s*oz\b|\b2\s*unze\b|\b2\s*troy\s*oz\b|\b62[.,]2\s*g\b|\b62\s*gramm\b', "2_oz"),
            (r'\b(?:0[.,]5|1/2)\s*oz\b|\b(?:0[.,]5|1/2)\s*unze\b|\b(?:0[.,]5|1/2)\s*troy\s*oz\b|\b15[.,]55?\s*g\b|\b15\s*gramm\b', "0.5_oz"),
            (r'\b1(?:\s*[.,]\s*0)?\s*oz\b|\b1(?:\s*[.,]\s*0)?\s*unze\b|\b1\s*troy\s*oz\b|\b31[.,]1(?:03)?\s*g\b|\b31\s*gramm\b', "1_oz")
        ]
        
        for pattern, weight in patterns:
            if re.search(pattern, text):
                return weight
        
        return None

    def is_zero_tax(self, soup: BeautifulSoup, from_detail: bool = False) -> bool:
        text = soup.get_text(strip=True).lower()
        
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
                return True
        
        keywords = [
            'differenzbesteuert', 'mwstfrei', 'mwst-frei', 'steuerbefreit',
            'ohne mwst', 'mwst 0', '0% mwst', 'tax free', 'steuerfrei',
            'differenzbesteuerung', '§25a ustg', 'differenzbesteuerung nach §25a ustg',
            'keine umsatzsteuer', 'umsatzsteuerfrei'
        ]
        
        for keyword in keywords:
            if keyword in text:
                return True
        
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

    def create_coin_key(self, name: str, weight: str, url: str) -> str:
        clean_name = re.sub(r'[^\w\s]', '', name.lower()).strip()
        clean_name = re.sub(r'\s+', ' ', clean_name)
        
        clean_url = self.normalize_url(url)
        
        return f"{clean_name}|{weight}|{clean_url}"

    def parse_availability_text(self, soup: BeautifulSoup) -> Tuple[bool, Optional[int], str]:
        text = soup.get_text(strip=True).lower()

        if any(x in text for x in ['nicht verfügbar', 'ausverkauft', 'out of stock', 'derzeit nicht', 'vorübergehend nicht']):
            return (False, 0, "Nicht verfügbar")

        if any(x in text for x in ['auf lager', 'lagernd', 'verfügbar', 'in stock']):
            m_qty = re.search(r'(\d+)\s*(?:stk|stück|verfügbar|lagernd)', text)
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

        return (True, None, "Verfügbarkeit unbekannt")

    async def fetch_product_details(self, url: str) -> Tuple[bool, Optional[int], str, bool, float, Optional[str]]:
        try:
            async with self.session.get(url, timeout=12) as r:
                if r.status != 200:
                    raise ValueError(f"Status {r.status}")
                text = await r.text()
                soup = BeautifulSoup(text, 'html.parser')

            is_available, qty, available_label = self.parse_availability_text(soup)

            is_zero_tax = self.is_zero_tax(soup, from_detail=True)

            price = self.extract_price(soup, from_detail=True)

            weight = self.detect_coin_weight(soup, from_detail=True)

            return (is_available, qty, available_label, is_zero_tax, price, weight)

        except Exception as e:
            _LOGGER.warning(f"Detail fetch error {url}: {e}")
            return (False, None, "Verfügbarkeit unbekannt", False, 0.0, None)

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        return urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))