"""Web dashboard for Bitcoin ATM opportunity finder."""

import os
import json
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from collections import Counter
import config
from rocketreach_api import RocketReachAPI

app = Flask(__name__)

# Data storage
DATA_FILE = config.OUTPUT_CSV
ATM_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_atms.json")


def load_data() -> pd.DataFrame:
    """Load opportunity data from CSV."""
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame()


def load_atm_data() -> list:
    """Load Bitcoin ATM data from cache."""
    if os.path.exists(ATM_CACHE_FILE):
        with open(ATM_CACHE_FILE, 'r') as f:
            return json.load(f)
    return []


def get_competitor_stats() -> dict:
    """Calculate competitor statistics."""
    atms = load_atm_data()
    if not atms:
        return {"operators": [], "total": 0, "atm_list": []}

    # Count by operator
    operators = Counter(atm.get('operator', 'Unknown') for atm in atms)
    total = len(atms)

    # Build operator list with percentages
    operator_list = []
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#7C4DFF', '#00BCD4', '#8BC34A']
    for i, (op, count) in enumerate(operators.most_common()):
        operator_list.append({
            "name": op,
            "count": count,
            "percentage": round(count / total * 100, 1),
            "color": colors[i % len(colors)]
        })

    # Get ATM locations grouped by operator
    atm_by_operator = {}
    for atm in atms:
        op = atm.get('operator', 'Unknown')
        if op not in atm_by_operator:
            atm_by_operator[op] = []
        atm_by_operator[op].append(atm)

    return {
        "operators": operator_list,
        "total": total,
        "atm_list": atms,
        "atm_by_operator": atm_by_operator
    }


def create_competitor_map(atms: list, selected_operator: str = "all") -> str:
    """Create a map showing competitor ATM locations."""
    m = folium.Map(
        location=[config.MIAMI_CENTER["lat"], config.MIAMI_CENTER["lng"]],
        zoom_start=11,
        tiles="cartodbpositron"
    )

    # Color mapping for operators
    operator_colors = {
        "Athena Bitcoin": "red",
        "Bitcoin Depot": "blue",
        "Coinhub": "green",
        "CoinFlip": "orange",
        "Coinme": "purple",
        "RockItCoin": "darkred",
        "LibertyX": "darkblue",
        "Bitstop": "darkgreen",
        "Unknown": "gray"
    }

    marker_cluster = MarkerCluster(name="ATMs").add_to(m)

    for atm in atms:
        lat = atm.get("latitude")
        lon = atm.get("longitude")
        operator = atm.get("operator", "Unknown")

        if not lat or not lon:
            continue

        if selected_operator != "all" and operator != selected_operator:
            continue

        color = operator_colors.get(operator, "gray")

        popup_html = f"""
        <div style="width: 200px;">
            <h5 style="margin: 0 0 10px 0; color: {color};">{operator}</h5>
            <p style="margin: 5px 0;"><strong>Location:</strong> {atm.get('location_name', 'N/A')}</p>
            <p style="margin: 5px 0;"><strong>Address:</strong> {atm.get('address', 'N/A')}</p>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=color, icon="bitcoin", prefix="fa"),
            tooltip=f"{operator}: {atm.get('location_name', 'ATM')}"
        ).add_to(marker_cluster)

    return m._repr_html_()


def save_data(df: pd.DataFrame):
    """Save data back to CSV."""
    df.to_csv(DATA_FILE, index=False)


def create_map(df: pd.DataFrame, filter_type: str = None, min_score: int = 0) -> str:
    """Create a Folium map with all locations."""
    # Filter data
    filtered_df = df.copy()

    if filter_type and filter_type != "all":
        filtered_df = filtered_df[
            filtered_df["business_type"].str.lower().str.contains(filter_type.lower(), na=False)
        ]

    if min_score > 0:
        filtered_df = filtered_df[filtered_df["opportunity_score"] >= min_score]

    # Create base map centered on Miami
    m = folium.Map(
        location=[config.MIAMI_CENTER["lat"], config.MIAMI_CENTER["lng"]],
        zoom_start=11,
        tiles="cartodbpositron"
    )

    # Add marker cluster for better performance
    marker_cluster = MarkerCluster(name="Locations").add_to(m)

    # Add markers for each location
    for _, row in filtered_df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")

        if pd.isna(lat) or pd.isna(lon):
            continue

        # Determine color based on ATM status
        has_atm = row.get("has_bitcoin_atm", False)
        if has_atm:
            color = "red"
            icon = "times"
        else:
            score = row.get("opportunity_score", 0)
            if score >= 70:
                color = "green"
            elif score >= 50:
                color = "orange"
            else:
                color = "gray"
            icon = "check"

        # Create popup content with RocketReach button
        business_name_escaped = str(row.get('business_name', 'Unknown')).replace("'", "\\'").replace('"', '&quot;')
        address_escaped = str(row.get('address', 'N/A')).replace("'", "\\'").replace('"', '&quot;')

        popup_html = f"""
        <div style="width: 280px;">
            <h4 style="margin: 0 0 10px 0;">{row.get('business_name', 'Unknown')}</h4>
            <p style="margin: 5px 0;"><strong>Type:</strong> {row.get('business_type', 'N/A')}</p>
            <p style="margin: 5px 0;"><strong>Address:</strong> {row.get('address', 'N/A')}</p>
            <p style="margin: 5px 0;"><strong>Phone:</strong> {row.get('phone', 'N/A')}</p>
            <p style="margin: 5px 0;"><strong>Rating:</strong> {row.get('google_rating', 'N/A')}</p>
            <hr style="margin: 10px 0;">
            <p style="margin: 5px 0;"><strong>Has ATM:</strong> {'Yes' if has_atm else 'No'}</p>
            <p style="margin: 5px 0;"><strong>Nearest ATM:</strong> {row.get('distance_to_nearest_atm', 'N/A')} km</p>
            <p style="margin: 5px 0;"><strong>Score:</strong> {row.get('opportunity_score', 0)}</p>
            <hr style="margin: 10px 0;">
            <button onclick="parent.lookupContact('{business_name_escaped}', '{address_escaped}')"
                    style="background-color: #28a745; color: white; border: none; padding: 8px 16px;
                           border-radius: 5px; cursor: pointer; width: 100%; font-size: 14px;">
                <i class="fas fa-user-search"></i> Find Contact Info
            </button>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            tooltip=row.get("business_name", "Unknown")
        ).add_to(marker_cluster)

    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 14px;">
        <p style="margin: 5px 0;"><span style="color: green;">&#9679;</span> High Opportunity (70+)</p>
        <p style="margin: 5px 0;"><span style="color: orange;">&#9679;</span> Medium Opportunity (50-69)</p>
        <p style="margin: 5px 0;"><span style="color: gray;">&#9679;</span> Low Opportunity (&lt;50)</p>
        <p style="margin: 5px 0;"><span style="color: red;">&#9679;</span> Has Bitcoin ATM</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m._repr_html_()


# HTML template
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin ATM Opportunity Finder - Miami</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .map-container { height: 600px; border-radius: 10px; overflow: hidden; }
        .stats-card { border-radius: 10px; padding: 20px; margin-bottom: 20px; }
        .stats-card h3 { font-size: 2em; margin: 0; }
        .opportunity-badge { font-size: 0.9em; }
        .table-container { max-height: 500px; overflow-y: auto; }
        .status-select { width: 140px; }
        .nav-tabs .nav-link.active { background-color: #198754; color: white; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">
                <i class="fab fa-bitcoin"></i> Bitcoin ATM Opportunity Finder - Miami, FL
            </span>
        </div>
    </nav>

    <div class="container-fluid py-4">
        <!-- Stats Row -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stats-card bg-primary text-white">
                    <h3>{{ total_locations }}</h3>
                    <p class="mb-0">Total Locations</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card bg-success text-white">
                    <h3>{{ opportunities }}</h3>
                    <p class="mb-0">Opportunities (No ATM)</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card bg-warning text-dark">
                    <h3>{{ high_score }}</h3>
                    <p class="mb-0">High Score (70+)</p>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stats-card bg-danger text-white">
                    <h3>{{ has_atm }}</h3>
                    <p class="mb-0">Already Has ATM</p>
                </div>
            </div>
        </div>

        <!-- Filters -->
        <div class="card mb-4">
            <div class="card-body">
                <form method="GET" class="row g-3 align-items-end">
                    <div class="col-md-3">
                        <label class="form-label">Business Type</label>
                        <select name="filter_type" class="form-select">
                            <option value="all" {{ 'selected' if filter_type == 'all' else '' }}>All Types</option>
                            <option value="convenience" {{ 'selected' if filter_type == 'convenience' else '' }}>Convenience Stores</option>
                            <option value="smoke" {{ 'selected' if filter_type == 'smoke' else '' }}>Smoke Shops</option>
                            <option value="bodega" {{ 'selected' if filter_type == 'bodega' else '' }}>Bodegas</option>
                            <option value="grocery" {{ 'selected' if filter_type == 'grocery' else '' }}>Grocery Stores</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">Minimum Score</label>
                        <select name="min_score" class="form-select">
                            <option value="0" {{ 'selected' if min_score == 0 else '' }}>All Scores</option>
                            <option value="50" {{ 'selected' if min_score == 50 else '' }}>50+</option>
                            <option value="70" {{ 'selected' if min_score == 70 else '' }}>70+</option>
                            <option value="80" {{ 'selected' if min_score == 80 else '' }}>80+</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">Show</label>
                        <select name="show_atm" class="form-select">
                            <option value="all" {{ 'selected' if show_atm == 'all' else '' }}>All Locations</option>
                            <option value="no" {{ 'selected' if show_atm == 'no' else '' }}>Opportunities Only</option>
                            <option value="yes" {{ 'selected' if show_atm == 'yes' else '' }}>Has ATM Only</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <button type="submit" class="btn btn-primary w-100">
                            <i class="fas fa-filter"></i> Apply Filters
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Tabs -->
        <ul class="nav nav-tabs mb-4" role="tablist">
            <li class="nav-item">
                <a class="nav-link active" data-bs-toggle="tab" href="#map-tab">
                    <i class="fas fa-map-marker-alt"></i> Map View
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-bs-toggle="tab" href="#table-tab">
                    <i class="fas fa-table"></i> Table View
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-bs-toggle="tab" href="#competitors-tab">
                    <i class="fas fa-chess"></i> Competitors
                </a>
            </li>
        </ul>

        <div class="tab-content">
            <!-- Map Tab -->
            <div class="tab-pane fade show active" id="map-tab">
                <div class="card">
                    <div class="card-body p-0 map-container">
                        {{ map_html | safe }}
                    </div>
                </div>
            </div>

            <!-- Table Tab -->
            <div class="tab-pane fade" id="table-tab">
                <div class="card">
                    <div class="card-body">
                        <div class="table-container">
                            <table class="table table-striped table-hover">
                                <thead class="table-dark sticky-top">
                                    <tr>
                                        <th>Business Name</th>
                                        <th>Type</th>
                                        <th>Address</th>
                                        <th>Phone</th>
                                        <th>Rating</th>
                                        <th>Score</th>
                                        <th>Distance to ATM</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for row in table_data %}
                                    <tr class="{{ 'table-danger' if row.has_bitcoin_atm else '' }}">
                                        <td>{{ row.business_name }}</td>
                                        <td>{{ row.business_type }}</td>
                                        <td>{{ row.address }}</td>
                                        <td>{{ row.phone or 'N/A' }}</td>
                                        <td>{{ row.google_rating or 'N/A' }}</td>
                                        <td>
                                            <span class="badge {{ 'bg-success' if row.opportunity_score >= 70 else 'bg-warning' if row.opportunity_score >= 50 else 'bg-secondary' }}">
                                                {{ row.opportunity_score }}
                                            </span>
                                        </td>
                                        <td>{{ row.distance_to_nearest_atm or 'N/A' }} km</td>
                                        <td>
                                            <select class="form-select form-select-sm status-select"
                                                    onchange="updateStatus({{ loop.index0 }}, this.value)">
                                                <option value="not_contacted" {{ 'selected' if row.status == 'not_contacted' else '' }}>Not Contacted</option>
                                                <option value="contacted" {{ 'selected' if row.status == 'contacted' else '' }}>Contacted</option>
                                                <option value="interested" {{ 'selected' if row.status == 'interested' else '' }}>Interested</option>
                                                <option value="rejected" {{ 'selected' if row.status == 'rejected' else '' }}>Rejected</option>
                                                <option value="installed" {{ 'selected' if row.status == 'installed' else '' }}>Installed</option>
                                            </select>
                                        </td>
                                        <td>
                                            <a href="https://www.google.com/maps/search/?api=1&query={{ row.latitude }},{{ row.longitude }}"
                                               target="_blank" class="btn btn-sm btn-outline-primary" title="View on Map">
                                                <i class="fas fa-map"></i>
                                            </a>
                                            <button class="btn btn-sm btn-outline-success ms-1"
                                                    onclick="lookupContact('{{ row.business_name | e }}', '{{ row.address | e }}')"
                                                    title="Find Contact Info">
                                                <i class="fas fa-user-search"></i>
                                            </button>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Competitors Tab -->
            <div class="tab-pane fade" id="competitors-tab">
                <div class="row">
                    <!-- Market Share -->
                    <div class="col-md-4">
                        <div class="card mb-4">
                            <div class="card-header bg-dark text-white">
                                <i class="fas fa-chart-pie"></i> Market Share
                            </div>
                            <div class="card-body">
                                <h4 class="text-center mb-3">{{ competitor_stats.total }} Total ATMs</h4>
                                {% for op in competitor_stats.operators %}
                                <div class="mb-3">
                                    <div class="d-flex justify-content-between mb-1">
                                        <span><strong>{{ op.name }}</strong></span>
                                        <span>{{ op.count }} ({{ op.percentage }}%)</span>
                                    </div>
                                    <div class="progress" style="height: 25px;">
                                        <div class="progress-bar" role="progressbar"
                                             style="width: {{ op.percentage }}%; background-color: {{ op.color }};"
                                             aria-valuenow="{{ op.percentage }}" aria-valuemin="0" aria-valuemax="100">
                                        </div>
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>

                    <!-- Competitor Map -->
                    <div class="col-md-8">
                        <div class="card mb-4">
                            <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                                <span><i class="fas fa-map"></i> Competitor Locations</span>
                                <select id="operatorFilter" class="form-select form-select-sm" style="width: auto;" onchange="filterCompetitorMap(this.value)">
                                    <option value="all">All Operators</option>
                                    {% for op in competitor_stats.operators %}
                                    <option value="{{ op.name }}">{{ op.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="card-body p-0" style="height: 500px;">
                                {{ competitor_map_html | safe }}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Competitor Details -->
                <div class="card">
                    <div class="card-header bg-dark text-white">
                        <i class="fas fa-list"></i> Competitor ATM Locations
                    </div>
                    <div class="card-body">
                        <div class="accordion" id="competitorAccordion">
                            {% for op in competitor_stats.operators %}
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
                                            data-bs-target="#collapse{{ loop.index }}" aria-expanded="false">
                                        <span class="badge me-2" style="background-color: {{ op.color }};">{{ op.count }}</span>
                                        {{ op.name }}
                                    </button>
                                </h2>
                                <div id="collapse{{ loop.index }}" class="accordion-collapse collapse" data-bs-parent="#competitorAccordion">
                                    <div class="accordion-body">
                                        <div class="table-container" style="max-height: 300px;">
                                            <table class="table table-sm table-striped">
                                                <thead>
                                                    <tr>
                                                        <th>Location</th>
                                                        <th>Address</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {% for atm in competitor_stats.atm_by_operator.get(op.name, [])[:20] %}
                                                    <tr>
                                                        <td>{{ atm.location_name or 'N/A' }}</td>
                                                        <td>{{ atm.address or 'N/A' }}</td>
                                                    </tr>
                                                    {% endfor %}
                                                    {% if competitor_stats.atm_by_operator.get(op.name, [])|length > 20 %}
                                                    <tr>
                                                        <td colspan="2" class="text-muted text-center">
                                                            ... and {{ competitor_stats.atm_by_operator.get(op.name, [])|length - 20 }} more locations
                                                        </td>
                                                    </tr>
                                                    {% endif %}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Contact Info Modal -->
    <div class="modal fade" id="contactModal" tabindex="-1" aria-labelledby="contactModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header bg-success text-white">
                    <h5 class="modal-title" id="contactModalLabel">
                        <i class="fas fa-address-card"></i> Contact Information
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" id="contactModalBody">
                    <div class="text-center py-4">
                        <div class="spinner-border text-success" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-2">Searching RocketReach...</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <span class="text-muted me-auto" id="creditInfo"></span>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function updateStatus(index, status) {
            fetch('/update_status', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: index, status: status})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Status updated');
                }
            });
        }

        function lookupContact(businessName, address) {
            // Show modal with loading state
            const modal = new bootstrap.Modal(document.getElementById('contactModal'));
            document.getElementById('contactModalLabel').innerHTML =
                '<i class="fas fa-address-card"></i> ' + businessName;
            document.getElementById('contactModalBody').innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-success" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2">Searching RocketReach for contacts...</p>
                </div>
            `;
            modal.show();

            // Call API
            fetch('/lookup_contact', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({business_name: businessName, address: address})
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('contactModalBody').innerHTML = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle"></i> ${data.error}
                        </div>
                    `;
                    return;
                }

                if (!data.contacts || data.contacts.length === 0) {
                    document.getElementById('contactModalBody').innerHTML = `
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i> No contacts found for this business.
                            <p class="mb-0 mt-2">Try searching manually on <a href="https://rocketreach.co/search?keyword=${encodeURIComponent(businessName)}" target="_blank">RocketReach</a></p>
                        </div>
                    `;
                    return;
                }

                let html = '<div class="list-group">';
                data.contacts.forEach(contact => {
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex w-100 justify-content-between">
                                <h5 class="mb-1">${contact.name || 'Unknown'}</h5>
                                <small class="text-muted">${contact.title || ''}</small>
                            </div>
                            <div class="mt-2">
                                ${contact.email ? `<p class="mb-1"><i class="fas fa-envelope text-primary"></i> <a href="mailto:${contact.email}">${contact.email}</a></p>` : ''}
                                ${contact.phone ? `<p class="mb-1"><i class="fas fa-phone text-success"></i> <a href="tel:${contact.phone}">${contact.phone}</a></p>` : ''}
                                ${contact.linkedin ? `<p class="mb-1"><i class="fab fa-linkedin text-info"></i> <a href="${contact.linkedin}" target="_blank">LinkedIn Profile</a></p>` : ''}
                                ${!contact.email && !contact.phone && !contact.linkedin ? '<p class="text-muted mb-0">No contact details available</p>' : ''}
                            </div>
                        </div>
                    `;
                });
                html += '</div>';

                document.getElementById('contactModalBody').innerHTML = html;
            })
            .catch(error => {
                document.getElementById('contactModalBody').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-times-circle"></i> Error: ${error.message}
                    </div>
                `;
            });
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Main dashboard page."""
    # Debug logging
    with open('C:/Users/fkozi/BitcoinATM-finder/debug_request.log', 'w') as dbg:
        dbg.write(f'DATA_FILE: {DATA_FILE}\n')
        dbg.write(f'File exists: {os.path.exists(DATA_FILE)}\n')
        dbg.write(f'CWD: {os.getcwd()}\n')

    df = load_data()

    with open('C:/Users/fkozi/BitcoinATM-finder/debug_request.log', 'a') as dbg:
        dbg.write(f'DataFrame empty: {df.empty}\n')
        dbg.write(f'DataFrame len: {len(df)}\n')

    if df.empty:
        return """
        <h1>No Data Available</h1>
        <p>Please run main.py first to scrape and analyze locations.</p>
        <pre>python main.py</pre>
        """

    # Get filter parameters
    filter_type = request.args.get("filter_type", "all")
    min_score = int(request.args.get("min_score", 0))
    show_atm = request.args.get("show_atm", "all")

    # Apply filters for table view
    filtered_df = df.copy()

    if filter_type and filter_type != "all":
        filtered_df = filtered_df[
            filtered_df["business_type"].str.lower().str.contains(filter_type.lower(), na=False)
        ]

    if min_score > 0:
        filtered_df = filtered_df[filtered_df["opportunity_score"] >= min_score]

    if show_atm == "no":
        filtered_df = filtered_df[filtered_df["has_bitcoin_atm"] == False]
    elif show_atm == "yes":
        filtered_df = filtered_df[filtered_df["has_bitcoin_atm"] == True]

    # Sort by opportunity score
    filtered_df = filtered_df.sort_values("opportunity_score", ascending=False)

    # Generate map
    map_html = create_map(filtered_df)

    # Calculate stats
    total_locations = len(df)
    opportunities = len(df[df["has_bitcoin_atm"] == False])
    high_score = len(df[df["opportunity_score"] >= 70])
    has_atm = len(df[df["has_bitcoin_atm"] == True])

    # Convert to records for template
    table_data = filtered_df.head(500).to_dict("records")

    # Get competitor stats
    competitor_stats = get_competitor_stats()
    competitor_map_html = create_competitor_map(competitor_stats.get("atm_list", []))

    return render_template_string(
        DASHBOARD_TEMPLATE,
        map_html=map_html,
        table_data=table_data,
        total_locations=total_locations,
        opportunities=opportunities,
        high_score=high_score,
        has_atm=has_atm,
        filter_type=filter_type,
        min_score=min_score,
        show_atm=show_atm,
        competitor_stats=competitor_stats,
        competitor_map_html=competitor_map_html
    )


@app.route("/update_status", methods=["POST"])
def update_status():
    """Update the status of a location."""
    data = request.json
    index = data.get("index")
    status = data.get("status")

    df = load_data()

    if 0 <= index < len(df):
        df.iloc[index, df.columns.get_loc("status")] = status
        save_data(df)
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "Invalid index"})


@app.route("/export")
def export_csv():
    """Export current data to CSV download."""
    df = load_data()
    csv_data = df.to_csv(index=False)

    return app.response_class(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=bitcoin_atm_opportunities.csv"}
    )


@app.route("/lookup_contact", methods=["POST"])
def lookup_contact():
    """Look up contact information for a business using RocketReach."""
    data = request.json
    business_name = data.get("business_name", "")
    address = data.get("address", "")

    if not business_name:
        return jsonify({"error": "Business name required"})

    try:
        api = RocketReachAPI()
        result = api.get_contact_info(business_name, address)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api_status")
def api_status():
    """Check RocketReach API status and remaining credits."""
    try:
        api = RocketReachAPI()
        status = api.check_api_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)})


def run_dashboard(port: int = None):
    """Run the dashboard server."""
    port = port or config.DASHBOARD_PORT
    print(f"\nStarting dashboard at http://localhost:{port}")
    print("Press Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_dashboard()
