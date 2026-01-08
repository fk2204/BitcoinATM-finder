"""
Bitcoin ATM Placement Opportunity Finder for Miami, FL

Main entry point for running the complete pipeline:
1. Scrape potential business locations
2. Scrape existing Bitcoin ATM locations
3. Cross-reference and score opportunities
4. Export results to CSV
5. Launch web dashboard

Usage:
    python main.py              # Run full pipeline
    python main.py --scrape     # Only scrape data
    python main.py --analyze    # Only analyze (requires prior scrape)
    python main.py --dashboard  # Only launch dashboard
"""

import argparse
import os
import json
import sys
from datetime import datetime

import config
from scrapers import LocationScraper, ATMScraper
from analyzer import OpportunityAnalyzer
from dashboard import run_dashboard


# Cache files for intermediate data
LOCATIONS_CACHE = "cache_locations.json"
ATMS_CACHE = "cache_atms.json"


def save_cache(data: list, filename: str):
    """Save data to cache file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Cached {len(data)} items to {filename}")


def load_cache(filename: str) -> list:
    """Load data from cache file."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded {len(data)} items from {filename}")
        return data
    return []


def scrape_locations() -> list:
    """Scrape potential business locations."""
    print("\n" + "=" * 60)
    print("STEP 1: Scraping Potential Business Locations")
    print("=" * 60)

    if not config.GOOGLE_API_KEY:
        print("\nWARNING: No Google API key found!")
        print("Set GOOGLE_API_KEY in .env file to enable location scraping.")
        print("Get an API key from: https://console.cloud.google.com/")

        # Check for cached data
        cached = load_cache(LOCATIONS_CACHE)
        if cached:
            print(f"\nUsing {len(cached)} cached locations")
            return cached

        print("\nNo cached data available. Please add API key and run again.")
        return []

    scraper = LocationScraper()
    locations = scraper.scrape_all_locations()

    # Save to cache
    save_cache(locations, LOCATIONS_CACHE)

    return locations


def scrape_atms() -> list:
    """Scrape existing Bitcoin ATM locations."""
    print("\n" + "=" * 60)
    print("STEP 2: Scraping Existing Bitcoin ATM Locations")
    print("=" * 60)

    scraper = ATMScraper()
    atms = scraper.scrape_miami_atms()

    # Save to cache
    save_cache(atms, ATMS_CACHE)

    return atms


def analyze_opportunities(locations: list, atms: list) -> list:
    """Analyze and score opportunities."""
    print("\n" + "=" * 60)
    print("STEP 3: Analyzing Opportunities")
    print("=" * 60)

    if not locations:
        print("No locations to analyze!")
        return []

    analyzer = OpportunityAnalyzer(locations, atms)
    opportunities = analyzer.analyze()

    # Export to CSV
    analyzer.export_csv()

    return opportunities


def print_top_opportunities(opportunities: list, n: int = 20):
    """Print top N opportunities."""
    print("\n" + "=" * 60)
    print(f"TOP {n} OPPORTUNITIES")
    print("=" * 60)

    count = 0
    for opp in opportunities:
        if opp["has_bitcoin_atm"]:
            continue

        count += 1
        if count > n:
            break

        print(f"\n{count}. {opp['business_name']} (Score: {opp['opportunity_score']})")
        print(f"   Type: {opp['business_type']}")
        print(f"   Address: {opp['address']}")
        print(f"   Phone: {opp['phone'] or 'N/A'}")
        print(f"   Rating: {opp['google_rating'] or 'N/A'}")
        print(f"   Distance to nearest ATM: {opp['distance_to_nearest_atm'] or 'Unknown'} km")


def run_pipeline(skip_scrape: bool = False):
    """Run the complete pipeline."""
    print("\n" + "#" * 60)
    print("# BITCOIN ATM PLACEMENT OPPORTUNITY FINDER")
    print("# Miami, FL")
    print(f"# Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 60)

    if skip_scrape:
        # Load from cache
        locations = load_cache(LOCATIONS_CACHE)
        atms = load_cache(ATMS_CACHE)
    else:
        # Scrape fresh data
        locations = scrape_locations()
        atms = scrape_atms()

    # Analyze
    opportunities = analyze_opportunities(locations, atms)

    if opportunities:
        # Print summary
        print_top_opportunities(opportunities)

        print("\n" + "=" * 60)
        print("COMPLETE!")
        print("=" * 60)
        print(f"\nResults saved to: {config.OUTPUT_CSV}")
        print(f"Total opportunities found: {sum(1 for o in opportunities if not o['has_bitcoin_atm'])}")
        print("\nTo view the interactive dashboard, run:")
        print("  python dashboard.py")
        print(f"\nOr open in browser: http://localhost:{config.DASHBOARD_PORT}")

    return opportunities


def main():
    """Main entry point with command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Bitcoin ATM Placement Opportunity Finder for Miami, FL"
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Only scrape data (no analysis)"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Only analyze cached data"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Only launch the web dashboard"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.DASHBOARD_PORT,
        help=f"Dashboard port (default: {config.DASHBOARD_PORT})"
    )

    args = parser.parse_args()

    if args.dashboard:
        # Just run dashboard
        run_dashboard(args.port)
    elif args.scrape:
        # Only scrape
        scrape_locations()
        scrape_atms()
        print("\nScraping complete. Run with --analyze to process data.")
    elif args.analyze:
        # Only analyze cached data
        run_pipeline(skip_scrape=True)
    else:
        # Run full pipeline
        opportunities = run_pipeline()

        # Ask if user wants to launch dashboard
        if opportunities:
            print("\nWould you like to launch the dashboard? [Y/n] ", end="")
            try:
                response = input().strip().lower()
                if response != "n":
                    run_dashboard(args.port)
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")


if __name__ == "__main__":
    main()
