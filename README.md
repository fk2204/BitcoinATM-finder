# Bitcoin ATM Placement Opportunity Finder

Find the best locations for Bitcoin ATM placement in Miami, FL.

## Features

- **Location Scraping**: Finds smoke shops, convenience stores, gas stations, liquor stores, and bodegas using Google Places API
- **ATM Detection**: Scrapes existing Bitcoin ATM locations from CoinATMRadar
- **Opportunity Scoring**: Rates locations 0-100 based on distance from existing ATMs, Google rating, and business type
- **Interactive Dashboard**: Web-based map with filters and status tracking
- **CSV Export**: Full data export for Excel/Google Sheets

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up API Key
Get a Google Places API key from https://console.cloud.google.com/

Create a `.env` file:
```
GOOGLE_API_KEY=your_api_key_here
```

### 3. Run the App
```bash
python main.py
```

### 4. View Dashboard
Open http://localhost:5000 or run:
```bash
python dashboard.py
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Run full pipeline (scrape + analyze) |
| `python main.py --scrape` | Only scrape data |
| `python main.py --analyze` | Only analyze cached data |
| `python main.py --dashboard` | Launch web dashboard |
| `python export_map.py` | Export standalone HTML map |

## Output

- `bitcoin_atm_opportunities.csv` - Full data with all locations
- `bitcoin_atm_opportunities_map.html` - Shareable interactive map

## CSV Columns

| Column | Description |
|--------|-------------|
| business_name | Name of the business |
| address | Full street address |
| phone | Phone number |
| business_type | Gas Station, Smoke Shop, etc. |
| latitude/longitude | GPS coordinates |
| has_bitcoin_atm | Whether location already has an ATM |
| existing_atm_operator | ATM operator if present |
| distance_to_nearest_atm | Distance in km to nearest ATM |
| google_rating | Google Maps rating (1-5) |
| opportunity_score | 0-100 score (higher = better opportunity) |
| status | not_contacted, contacted, interested, rejected, installed |
| notes | Custom notes |

## Tech Stack

- Python 3
- Flask (web dashboard)
- Folium (interactive maps)
- Pandas (data processing)
- BeautifulSoup (web scraping)
- Google Places API

## License

MIT
