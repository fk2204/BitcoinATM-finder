"""Scraper for existing Bitcoin ATM locations using Google Places API."""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from typing import Optional
import config


class ATMScraper:
    """Scrapes Bitcoin ATM locations using Google Places API."""

    PLACES_TEXT_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    # Known Bitcoin ATM operators
    OPERATORS = [
        "Bitcoin Depot", "CoinFlip", "Coinhub", "Coinme", "DigitalMint",
        "Bitstop", "Athena Bitcoin", "RockItCoin", "Bitcoin of America",
        "Hippo Kiosk", "Coin Cloud", "Byte Federal", "LibertyX", "Pelicoin"
    ]

    def __init__(self):
        self.api_key = config.GOOGLE_API_KEY
        self.atm_locations = []

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_atm_list_from_page(self, soup: BeautifulSoup) -> list:
        """Extract ATM information from a listing page."""
        atms = []

        # Look for ATM listing cards/items
        atm_items = soup.find_all("div", class_=re.compile(r"atm-item|machine-item|location-item"))

        if not atm_items:
            # Try alternative selectors
            atm_items = soup.find_all("a", href=re.compile(r"/bitcoin_atm/\d+/"))

        for item in atm_items:
            atm_data = self.parse_atm_item(item)
            if atm_data:
                atms.append(atm_data)

        return atms

    def parse_atm_item(self, item) -> Optional[dict]:
        """Parse an individual ATM listing item."""
        try:
            # Extract link to detail page
            link = item.get("href") if item.name == "a" else None
            if not link:
                link_elem = item.find("a", href=re.compile(r"/bitcoin_atm/\d+/"))
                link = link_elem.get("href") if link_elem else None

            # Extract operator name
            operator = ""
            operator_elem = item.find(class_=re.compile(r"operator|brand"))
            if operator_elem:
                operator = operator_elem.get_text(strip=True)

            # Extract location name
            location_name = ""
            name_elem = item.find(class_=re.compile(r"name|title|location-name"))
            if name_elem:
                location_name = name_elem.get_text(strip=True)

            # Extract address
            address = ""
            addr_elem = item.find(class_=re.compile(r"address|location"))
            if addr_elem:
                address = addr_elem.get_text(strip=True)

            return {
                "detail_url": f"{self.BASE_URL}{link}" if link and not link.startswith("http") else link,
                "operator": operator,
                "location_name": location_name,
                "address": address
            }
        except Exception as e:
            print(f"Error parsing ATM item: {e}")
            return None

    def get_atm_details(self, url: str) -> Optional[dict]:
        """Get detailed information from an ATM's detail page."""
        soup = self.get_page(url)
        if not soup:
            return None

        details = {}

        # Extract operator
        operator_elem = soup.find(class_=re.compile(r"operator-name|brand-name"))
        if operator_elem:
            details["operator"] = operator_elem.get_text(strip=True)

        # Extract address
        addr_elem = soup.find(class_=re.compile(r"address|location-address"))
        if addr_elem:
            details["address"] = addr_elem.get_text(strip=True)

        # Extract coordinates from map or data attributes
        map_elem = soup.find(id=re.compile(r"map")) or soup.find(class_=re.compile(r"map"))
        if map_elem:
            lat = map_elem.get("data-lat") or map_elem.get("data-latitude")
            lng = map_elem.get("data-lng") or map_elem.get("data-longitude")
            if lat and lng:
                details["latitude"] = float(lat)
                details["longitude"] = float(lng)

        # Try to find coords in script tags
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string:
                lat_match = re.search(r'["\']?lat["\']?\s*[:=]\s*(-?\d+\.?\d*)', script.string)
                lng_match = re.search(r'["\']?(?:lng|lon)["\']?\s*[:=]\s*(-?\d+\.?\d*)', script.string)
                if lat_match and lng_match:
                    details["latitude"] = float(lat_match.group(1))
                    details["longitude"] = float(lng_match.group(1))
                    break

        return details

    def search_text(self, query: str) -> list:
        """Search for places using a text query via Google Places API."""
        if not self.api_key:
            print("No Google API key configured")
            return []

        params = {
            "query": query,
            "key": self.api_key
        }

        all_results = []

        while True:
            response = requests.get(self.PLACES_TEXT_URL, params=params)
            data = response.json()

            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                print(f"API Error: {data.get('status')} - {data.get('error_message', '')}")
                break

            results = data.get("results", [])
            all_results.extend(results)

            next_page_token = data.get("next_page_token")
            if next_page_token:
                time.sleep(2)
                params = {"pagetoken": next_page_token, "key": self.api_key}
            else:
                break

        return all_results

    def scrape_miami_atms(self) -> list:
        """Scrape all Bitcoin ATM locations in Miami using Google Places API."""
        print("=" * 50)
        print("Scraping Bitcoin ATM locations via Google Places API")
        print("=" * 50)

        all_atms = []
        seen_place_ids = set()

        # Search queries for Bitcoin ATMs
        search_queries = [
            "bitcoin atm Miami",
            "crypto atm Miami",
            "Bitcoin Depot Miami",
            "CoinFlip Miami",
            "Coinhub Miami",
            "Athena Bitcoin Miami",
            "bitcoin kiosk Miami"
        ]

        for query in search_queries:
            print(f"\nSearching: {query}")
            results = self.search_text(query)
            print(f"  Found {len(results)} results")

            for place in results:
                place_id = place.get("place_id")
                if place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                name = place.get("name", "").lower()
                # Only include actual Bitcoin ATMs
                if any(kw in name for kw in ["bitcoin", "crypto", "btc", "atm", "coinflip", "coinhub", "bitcoin depot", "athena"]):
                    location = place.get("geometry", {}).get("location", {})
                    atm_info = {
                        "location_name": place.get("name", ""),
                        "address": place.get("formatted_address", place.get("vicinity", "")),
                        "operator": self._detect_operator(place.get("name", "")),
                        "latitude": location.get("lat"),
                        "longitude": location.get("lng"),
                        "place_id": place_id
                    }
                    all_atms.append(atm_info)

        print(f"\n{'=' * 50}")
        print(f"Total unique Bitcoin ATMs found: {len(all_atms)}")
        print("=" * 50)

        self.atm_locations = all_atms
        return all_atms

    def _detect_operator(self, name: str) -> str:
        """Detect the ATM operator from the location name."""
        name_lower = name.lower()
        for operator in self.OPERATORS:
            if operator.lower() in name_lower:
                return operator
        return "Unknown"

    def get_known_operators(self) -> list:
        """Return list of known Bitcoin ATM operators."""
        return [
            "Bitcoin Depot",
            "CoinFlip",
            "Coinhub",
            "Coinme",
            "DigitalMint",
            "Bitstop",
            "Athena Bitcoin",
            "RockItCoin",
            "Bitcoin of America",
            "Hippo Kiosk",
            "Coin Cloud",
            "Byte Federal",
            "LibertyX",
            "Pelicoin",
            "Just Cash"
        ]


if __name__ == "__main__":
    # Test the scraper
    scraper = ATMScraper()
    atms = scraper.scrape_miami_atms()

    print("\nSample ATM locations:")
    for atm in atms[:5]:
        print(f"  - {atm.get('location_name', 'Unknown')}")
        print(f"    Operator: {atm.get('operator', 'Unknown')}")
        print(f"    Address: {atm.get('address', 'N/A')}")
        print()
