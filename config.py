"""Configuration settings for Bitcoin ATM Finder."""

import os
from dotenv import load_dotenv

load_dotenv()

# Google Places API Key (get from https://console.cloud.google.com/)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# RocketReach API Key (get from https://rocketreach.co/api)
ROCKETREACH_API_KEY = os.getenv("ROCKETREACH_API_KEY", "")

# Miami, FL coordinates
MIAMI_CENTER = {
    "lat": 25.7617,
    "lng": -80.1918
}

# Search radius in meters (50km covers greater Miami area)
SEARCH_RADIUS = 50000

# Business types to search for
BUSINESS_TYPES = [
    "smoke_shop",
    "convenience_store",
    "gas_station",
    "grocery_or_supermarket"  # Covers bodegas
]

# Search keywords for Google Places text search
SEARCH_KEYWORDS = [
    "smoke shop Miami",
    "convenience store Miami",
    "gas station Miami",
    "bodega Miami",
    "corner store Miami"
]

# CoinATMRadar settings
COINATMRADAR_URL = "https://coinatmradar.com/city/52/bitcoin-atm-miami/"

# Distance threshold (in km) - locations closer than this to an ATM are less desirable
MIN_DISTANCE_FROM_ATM = 0.5  # 500 meters

# CSV output file - use absolute path
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(_BASE_DIR, "bitcoin_atm_opportunities.csv")

# Dashboard settings
DASHBOARD_PORT = 5000
