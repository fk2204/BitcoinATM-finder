"""Scraper for potential Bitcoin ATM locations using Google Places API."""

import requests
import time
from typing import Optional
import config


class LocationScraper:
    """Scrapes potential business locations using Google Places API."""

    PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    PLACES_TEXT_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GOOGLE_API_KEY
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY in .env file or pass to constructor."
            )
        self.locations = []

    def search_nearby(self, location: dict, radius: int, place_type: str) -> list:
        """Search for places near a location by type."""
        params = {
            "location": f"{location['lat']},{location['lng']}",
            "radius": radius,
            "type": place_type,
            "key": self.api_key
        }

        all_results = []

        while True:
            response = requests.get(self.PLACES_NEARBY_URL, params=params)
            data = response.json()

            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                print(f"API Error: {data.get('status')} - {data.get('error_message', '')}")
                break

            results = data.get("results", [])
            all_results.extend(results)
            print(f"  Found {len(results)} {place_type} locations")

            # Check for more pages
            next_page_token = data.get("next_page_token")
            if next_page_token:
                time.sleep(2)  # Required delay before using next_page_token
                params = {"pagetoken": next_page_token, "key": self.api_key}
            else:
                break

        return all_results

    def search_text(self, query: str) -> list:
        """Search for places using a text query."""
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
            print(f"  Found {len(results)} results for '{query}'")

            next_page_token = data.get("next_page_token")
            if next_page_token:
                time.sleep(2)
                params = {"pagetoken": next_page_token, "key": self.api_key}
            else:
                break

        return all_results

    def get_place_details(self, place_id: str) -> Optional[dict]:
        """Get detailed information about a place including phone number."""
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,geometry,rating,types,business_status",
            "key": self.api_key
        }

        response = requests.get(self.PLACES_DETAILS_URL, params=params)
        data = response.json()

        if data.get("status") == "OK":
            return data.get("result")
        return None

    def parse_place(self, place: dict, business_type: str) -> dict:
        """Parse a place result into a standardized format."""
        location = place.get("geometry", {}).get("location", {})

        return {
            "place_id": place.get("place_id"),
            "business_name": place.get("name", "Unknown"),
            "address": place.get("formatted_address", place.get("vicinity", "")),
            "phone": place.get("formatted_phone_number", ""),
            "business_type": business_type,
            "latitude": location.get("lat"),
            "longitude": location.get("lng"),
            "google_rating": place.get("rating"),
            "business_status": place.get("business_status", "OPERATIONAL"),
            "types": place.get("types", [])
        }

    def determine_business_type(self, types: list, business_name: str = "") -> str:
        """Determine the primary business type from Google's type list and business name."""
        name_lower = business_name.lower()

        # EXCLUDE places that are clearly not retail (restaurants, hotels, bars, etc.)
        excluded_google_types = [
            "restaurant", "bar", "night_club", "lodging", "hotel", "hospital",
            "school", "university", "church", "courthouse", "lawyer", "doctor",
            "real_estate_agency", "apartment", "gym", "spa", "salon", "bank",
            "insurance_agency", "car_dealer", "car_rental", "parking"
        ]
        if any(t in excluded_google_types for t in types):
            return "Exclude"

        # Exclude by name keywords (restaurants, hotels, bars, courts, etc.)
        exclude_name_keywords = [
            "hotel", "inn ", " inn", "suites", "resort", "motel",
            "restaurant", "grill", "steakhouse", "seafood", "kitchen", "bistro", "cafe", "diner",
            "bar ", " bar", "pub ", " pub", "lounge", "tavern", "brewery",
            "honorable", "judge", "court", "attorney", "law office",
            "college", "university", "school", "academy",
            "hospital", "clinic", "medical", "dental",
            "church", "temple", "mosque",
            "apartment", "condo", "realty", "real estate",
            "yacht", "charter", "cruise",
            "arena", "stadium", "center"
        ]
        if any(kw in name_lower for kw in exclude_name_keywords):
            return "Exclude"

        # Smoke/Vape shops - MUST have keyword in business name
        if any(kw in name_lower for kw in ["smoke", "vape", "tobacco", "cigar", "hookah"]):
            return "Smoke Shop"

        # Bodegas/Corner stores
        if any(kw in name_lower for kw in ["bodega", "deli", "mini mart", "minimart", "corner store"]):
            return "Bodega"

        # Gas stations
        if any(kw in name_lower for kw in ["gas", "fuel", "shell", "chevron", "exxon", "mobil", "bp ", "citgo", "marathon", "sunoco", "speedway", "wawa", "racetrac", "7-eleven", "7 eleven", "circle k"]):
            return "Gas Station"

        # Fall back to Google's type mapping
        type_mapping = {
            "gas_station": "Gas Station",
            "convenience_store": "Convenience Store",
            "grocery_or_supermarket": "Grocery/Bodega",
            "supermarket": "Grocery/Bodega",
            "store": "Convenience Store"
        }

        for t in types:
            if t in type_mapping:
                return type_mapping[t]

        return "Other"

    def scrape_all_locations(self) -> list:
        """Scrape all potential business locations in Miami."""
        print("=" * 50)
        print("Starting location scraping for Miami, FL")
        print("=" * 50)

        seen_place_ids = set()
        all_locations = []

        # Search by type using Nearby Search
        print("\n[1/2] Searching by business type...")
        for place_type in config.BUSINESS_TYPES:
            print(f"\nSearching for: {place_type}")
            results = self.search_nearby(
                config.MIAMI_CENTER,
                config.SEARCH_RADIUS,
                place_type
            )

            for place in results:
                place_id = place.get("place_id")
                if place_id and place_id not in seen_place_ids:
                    seen_place_ids.add(place_id)
                    business_name = place.get("name", "")
                    business_type = self.determine_business_type(place.get("types", []), business_name)
                    if business_type == "Exclude":
                        continue  # Skip restaurants, hotels, bars, etc.
                    if business_type == "Other":
                        business_type = place_type.replace("_", " ").title()
                    parsed = self.parse_place(place, business_type)
                    all_locations.append(parsed)

        # Search by keyword using Text Search
        print("\n[2/2] Searching by keywords...")
        for keyword in config.SEARCH_KEYWORDS:
            print(f"\nSearching for: {keyword}")
            results = self.search_text(keyword)

            for place in results:
                place_id = place.get("place_id")
                if place_id and place_id not in seen_place_ids:
                    seen_place_ids.add(place_id)
                    business_name = place.get("name", "")
                    business_type = self.determine_business_type(place.get("types", []), business_name)
                    if business_type == "Exclude":
                        continue  # Skip restaurants, hotels, bars, etc.
                    if business_type == "Other":
                        # Infer from keyword - but only for valid retail types
                        if "bodega" in keyword.lower() or "corner" in keyword.lower():
                            business_type = "Bodega"
                        elif "gas" in keyword.lower():
                            business_type = "Gas Station"
                        else:
                            business_type = "Convenience Store"
                    parsed = self.parse_place(place, business_type)
                    all_locations.append(parsed)

        print(f"\n{'=' * 50}")
        print(f"Total unique locations found: {len(all_locations)}")
        print("=" * 50)

        # Fetch phone numbers for locations that don't have them
        print("\nFetching phone numbers for locations...")
        locations_with_phones = 0
        for i, loc in enumerate(all_locations):
            if not loc.get("phone") and loc.get("place_id"):
                details = self.get_place_details(loc["place_id"])
                if details:
                    loc["phone"] = details.get("formatted_phone_number", "")
                    if details.get("formatted_address"):
                        loc["address"] = details["formatted_address"]
                    if loc["phone"]:
                        locations_with_phones += 1

                # Rate limiting
                if i % 10 == 0:
                    print(f"  Processed {i+1}/{len(all_locations)} locations...")
                time.sleep(0.1)

        print(f"Found phone numbers for {locations_with_phones} additional locations")

        self.locations = all_locations
        return all_locations


if __name__ == "__main__":
    # Test the scraper
    scraper = LocationScraper()
    locations = scraper.scrape_all_locations()

    print("\nSample locations:")
    for loc in locations[:5]:
        print(f"  - {loc['business_name']} ({loc['business_type']})")
        print(f"    {loc['address']}")
        print(f"    Phone: {loc['phone'] or 'N/A'}")
        print()
