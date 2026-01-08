"""Scraper for existing Bitcoin ATM locations from CoinATMRadar."""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
from typing import Optional
import config


class ATMScraper:
    """Scrapes Bitcoin ATM locations from CoinATMRadar.com."""

    BASE_URL = "https://coinatmradar.com"
    MIAMI_URL = "https://coinatmradar.com/city/52/bitcoin-atm-miami/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
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

    def scrape_miami_atms_api(self) -> list:
        """Try to scrape ATMs using the API endpoint if available."""
        api_urls = [
            "https://coinatmradar.com/api/v1/atms/?city=miami",
            "https://coinatmradar.com/api/atms?city=52",
        ]

        for url in api_urls:
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "atms" in data:
                        return data["atms"]
            except Exception:
                continue

        return []

    def scrape_miami_atms(self) -> list:
        """Scrape all Bitcoin ATM locations in Miami."""
        print("=" * 50)
        print("Scraping Bitcoin ATM locations from CoinATMRadar")
        print("=" * 50)

        all_atms = []

        # Try API first
        print("\nTrying API endpoint...")
        api_atms = self.scrape_miami_atms_api()
        if api_atms:
            print(f"Found {len(api_atms)} ATMs via API")
            for atm in api_atms:
                all_atms.append({
                    "location_name": atm.get("name", atm.get("location_name", "")),
                    "address": atm.get("address", ""),
                    "operator": atm.get("operator", atm.get("brand", "")),
                    "latitude": atm.get("lat", atm.get("latitude")),
                    "longitude": atm.get("lng", atm.get("longitude")),
                })
            self.atm_locations = all_atms
            return all_atms

        # Fallback to web scraping
        print("\nScraping website...")
        page_num = 1
        base_url = self.MIAMI_URL

        while True:
            url = base_url if page_num == 1 else f"{base_url}?page={page_num}"
            print(f"Fetching page {page_num}: {url}")

            soup = self.get_page(url)
            if not soup:
                break

            # Find all ATM links on the page
            atm_links = soup.find_all("a", href=re.compile(r"/bitcoin_atm/\d+/"))

            if not atm_links:
                print(f"No more ATMs found on page {page_num}")
                break

            seen_urls = set()
            for link in atm_links:
                href = link.get("href", "")
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                full_url = f"{self.BASE_URL}{href}" if not href.startswith("http") else href

                # Extract basic info from the link
                atm_info = {
                    "detail_url": full_url,
                    "location_name": "",
                    "address": "",
                    "operator": "",
                    "latitude": None,
                    "longitude": None
                }

                # Try to get info from parent elements
                parent = link.find_parent("div", class_=re.compile(r"atm|machine|location|item"))
                if parent:
                    name_elem = parent.find(class_=re.compile(r"name|title"))
                    if name_elem:
                        atm_info["location_name"] = name_elem.get_text(strip=True)

                    addr_elem = parent.find(class_=re.compile(r"address"))
                    if addr_elem:
                        atm_info["address"] = addr_elem.get_text(strip=True)

                    op_elem = parent.find(class_=re.compile(r"operator|brand"))
                    if op_elem:
                        atm_info["operator"] = op_elem.get_text(strip=True)

                # If we don't have the name, use link text
                if not atm_info["location_name"]:
                    atm_info["location_name"] = link.get_text(strip=True)

                all_atms.append(atm_info)

            print(f"  Found {len(seen_urls)} ATM links on this page")

            # Check for next page
            next_page = soup.find("a", text=re.compile(r"next|›|>>")) or \
                        soup.find("a", class_=re.compile(r"next"))
            if not next_page:
                break

            page_num += 1
            time.sleep(1)  # Be polite

            # Safety limit
            if page_num > 50:
                print("Reached page limit, stopping")
                break

        # Deduplicate by URL
        seen = set()
        unique_atms = []
        for atm in all_atms:
            url = atm.get("detail_url", "")
            if url not in seen:
                seen.add(url)
                unique_atms.append(atm)

        print(f"\n{'=' * 50}")
        print(f"Total unique ATMs found: {len(unique_atms)}")
        print("=" * 50)

        # Get detailed info for ATMs missing coordinates
        print("\nFetching detailed ATM information...")
        for i, atm in enumerate(unique_atms):
            if not atm.get("latitude") and atm.get("detail_url"):
                details = self.get_atm_details(atm["detail_url"])
                if details:
                    atm.update(details)

                if (i + 1) % 10 == 0:
                    print(f"  Processed {i + 1}/{len(unique_atms)} ATMs...")

                time.sleep(0.5)  # Rate limiting

        self.atm_locations = unique_atms
        return unique_atms

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
