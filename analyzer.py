"""Analyzer module for cross-referencing locations and scoring opportunities."""

import pandas as pd
from geopy.distance import geodesic
from typing import Optional
import config


class OpportunityAnalyzer:
    """Analyzes potential locations and scores opportunities."""

    def __init__(self, locations: list, atm_locations: list):
        self.locations = locations
        self.atm_locations = atm_locations
        self.opportunities = []

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers."""
        if None in (lat1, lon1, lat2, lon2):
            return float('inf')
        try:
            return geodesic((lat1, lon1), (lat2, lon2)).kilometers
        except Exception:
            return float('inf')

    def find_nearest_atm(self, lat: float, lon: float) -> tuple:
        """Find the nearest ATM to a given location."""
        min_distance = float('inf')
        nearest_operator = None

        for atm in self.atm_locations:
            atm_lat = atm.get("latitude")
            atm_lon = atm.get("longitude")

            if atm_lat and atm_lon:
                distance = self.calculate_distance(lat, lon, atm_lat, atm_lon)
                if distance < min_distance:
                    min_distance = distance
                    nearest_operator = atm.get("operator", "Unknown")

        return min_distance, nearest_operator

    def check_has_bitcoin_atm(self, location: dict) -> tuple:
        """Check if a location already has a Bitcoin ATM."""
        loc_name = location.get("business_name", "").lower()
        loc_addr = location.get("address", "").lower()
        loc_lat = location.get("latitude")
        loc_lon = location.get("longitude")

        for atm in self.atm_locations:
            atm_name = atm.get("location_name", "").lower()
            atm_addr = atm.get("address", "").lower()
            atm_lat = atm.get("latitude")
            atm_lon = atm.get("longitude")

            # Check by name similarity
            if loc_name and atm_name:
                # Simple name matching
                if loc_name in atm_name or atm_name in loc_name:
                    return True, atm.get("operator", "Unknown")

                # Check for common words (excluding generic ones)
                loc_words = set(loc_name.split()) - {"the", "a", "of", "and", "&", "store", "shop"}
                atm_words = set(atm_name.split()) - {"the", "a", "of", "and", "&", "store", "shop"}
                if loc_words and atm_words and len(loc_words & atm_words) >= 2:
                    return True, atm.get("operator", "Unknown")

            # Check by address similarity
            if loc_addr and atm_addr:
                # Extract street number and name
                loc_parts = loc_addr.split(",")[0].strip().lower()
                atm_parts = atm_addr.split(",")[0].strip().lower()
                if loc_parts and atm_parts and loc_parts == atm_parts:
                    return True, atm.get("operator", "Unknown")

            # Check by proximity (within 50 meters likely same location)
            if loc_lat and loc_lon and atm_lat and atm_lon:
                distance = self.calculate_distance(loc_lat, loc_lon, atm_lat, atm_lon)
                if distance < 0.05:  # 50 meters
                    return True, atm.get("operator", "Unknown")

        return False, None

    def calculate_opportunity_score(self, location: dict, has_atm: bool,
                                     distance_to_nearest: float) -> int:
        """
        Calculate an opportunity score from 0-100.

        Factors:
        - Distance from nearest ATM (more distance = higher score)
        - Google rating (higher rating = higher score)
        - Business type (some types are better suited)
        - Already has ATM (score = 0 if has ATM)
        """
        if has_atm:
            return 0

        score = 0

        # Distance score (0-40 points)
        # Ideal distance is 1-3 km from nearest ATM
        if distance_to_nearest == float('inf'):
            score += 30  # Unknown distance, moderate score
        elif distance_to_nearest >= 3:
            score += 40  # Far from any ATM
        elif distance_to_nearest >= 1:
            score += 35  # Good distance
        elif distance_to_nearest >= 0.5:
            score += 25  # Acceptable distance
        elif distance_to_nearest >= 0.2:
            score += 10  # Close to another ATM
        else:
            score += 0  # Very close, oversaturated

        # Google rating score (0-25 points)
        rating = location.get("google_rating")
        if rating:
            if rating >= 4.5:
                score += 25
            elif rating >= 4.0:
                score += 20
            elif rating >= 3.5:
                score += 15
            elif rating >= 3.0:
                score += 10
            else:
                score += 5
        else:
            score += 10  # Unknown rating, neutral score

        # Business type score (0-25 points)
        business_type = location.get("business_type", "").lower()
        type_scores = {
            "gas station": 25,  # High traffic, long hours
            "convenience store": 23,
            "smoke shop": 20,
            "liquor store": 18,
            "bodega": 18,
            "grocery": 15,
        }
        for type_key, type_score in type_scores.items():
            if type_key in business_type:
                score += type_score
                break
        else:
            score += 12  # Default score for other types

        # Phone available bonus (0-10 points)
        if location.get("phone"):
            score += 10

        return min(score, 100)

    def analyze(self) -> list:
        """Analyze all locations and identify opportunities."""
        print("=" * 50)
        print("Analyzing locations for opportunities")
        print("=" * 50)

        self.opportunities = []

        for i, location in enumerate(self.locations):
            lat = location.get("latitude")
            lon = location.get("longitude")

            # Check if location already has an ATM
            has_atm, existing_operator = self.check_has_bitcoin_atm(location)

            # Find nearest ATM
            distance_to_nearest, nearest_operator = self.find_nearest_atm(lat, lon)

            # Calculate opportunity score
            score = self.calculate_opportunity_score(
                location, has_atm, distance_to_nearest
            )

            opportunity = {
                "business_name": location.get("business_name", ""),
                "address": location.get("address", ""),
                "phone": location.get("phone", ""),
                "business_type": location.get("business_type", ""),
                "latitude": lat,
                "longitude": lon,
                "has_bitcoin_atm": has_atm,
                "existing_atm_operator": existing_operator or "",
                "distance_to_nearest_atm": round(distance_to_nearest, 2) if distance_to_nearest != float('inf') else None,
                "nearest_atm_operator": nearest_operator or "",
                "google_rating": location.get("google_rating"),
                "opportunity_score": score,
                "status": "not_contacted",
                "notes": ""
            }

            self.opportunities.append(opportunity)

            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(self.locations)} locations...")

        # Sort by opportunity score (descending)
        self.opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)

        # Print summary
        has_atm_count = sum(1 for o in self.opportunities if o["has_bitcoin_atm"])
        no_atm_count = len(self.opportunities) - has_atm_count
        high_score_count = sum(1 for o in self.opportunities if o["opportunity_score"] >= 70)

        print(f"\n{'=' * 50}")
        print("Analysis Complete!")
        print("=" * 50)
        print(f"Total locations analyzed: {len(self.opportunities)}")
        print(f"Locations WITH Bitcoin ATM: {has_atm_count}")
        print(f"Locations WITHOUT Bitcoin ATM: {no_atm_count}")
        print(f"High-opportunity locations (score >= 70): {high_score_count}")

        return self.opportunities

    def to_dataframe(self) -> pd.DataFrame:
        """Convert opportunities to a pandas DataFrame."""
        return pd.DataFrame(self.opportunities)

    def export_csv(self, filepath: str = None) -> str:
        """Export opportunities to CSV."""
        if not filepath:
            filepath = config.OUTPUT_CSV

        df = self.to_dataframe()

        # Reorder columns
        columns = [
            "business_name", "address", "phone", "business_type",
            "latitude", "longitude", "has_bitcoin_atm", "existing_atm_operator",
            "distance_to_nearest_atm", "nearest_atm_operator", "google_rating",
            "opportunity_score", "status", "notes"
        ]

        # Only include columns that exist
        columns = [c for c in columns if c in df.columns]
        df = df[columns]

        df.to_csv(filepath, index=False)
        print(f"\nExported {len(df)} records to {filepath}")

        return filepath


if __name__ == "__main__":
    # Test with sample data
    sample_locations = [
        {
            "business_name": "Test Gas Station",
            "address": "123 Main St, Miami, FL",
            "phone": "305-555-1234",
            "business_type": "Gas Station",
            "latitude": 25.7617,
            "longitude": -80.1918,
            "google_rating": 4.2
        }
    ]

    sample_atms = [
        {
            "location_name": "Some Store",
            "address": "456 Other St, Miami, FL",
            "operator": "Bitcoin Depot",
            "latitude": 25.7700,
            "longitude": -80.2000
        }
    ]

    analyzer = OpportunityAnalyzer(sample_locations, sample_atms)
    opportunities = analyzer.analyze()

    for opp in opportunities:
        print(f"\n{opp['business_name']}")
        print(f"  Score: {opp['opportunity_score']}")
        print(f"  Has ATM: {opp['has_bitcoin_atm']}")
        print(f"  Distance to nearest: {opp['distance_to_nearest_atm']} km")
