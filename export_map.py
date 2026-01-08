"""Export interactive map as standalone HTML file."""

import pandas as pd
import folium
from folium.plugins import MarkerCluster
import config

def export_map():
    """Export the opportunity map as a standalone HTML file."""

    print("Loading data...")
    df = pd.read_csv(config.OUTPUT_CSV)

    print(f"Creating map with {len(df)} locations...")

    # Create base map
    m = folium.Map(
        location=[config.MIAMI_CENTER["lat"], config.MIAMI_CENTER["lng"]],
        zoom_start=11,
        tiles="cartodbpositron"
    )

    # Add marker cluster
    marker_cluster = MarkerCluster(name="Locations").add_to(m)

    # Add markers
    for _, row in df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")

        if pd.isna(lat) or pd.isna(lon):
            continue

        # Color based on score
        has_atm = row.get("has_bitcoin_atm", False)
        if has_atm:
            color = "red"
        else:
            score = row.get("opportunity_score", 0)
            if score >= 70:
                color = "green"
            elif score >= 50:
                color = "orange"
            else:
                color = "gray"

        # Popup content
        phone = row.get('phone', 'N/A')
        if pd.isna(phone):
            phone = 'N/A'

        rating = row.get('google_rating', 'N/A')
        if pd.isna(rating):
            rating = 'N/A'

        popup_html = f"""
        <div style="width: 280px; font-family: Arial, sans-serif;">
            <h4 style="margin: 0 0 10px 0; color: #333;">{row.get('business_name', 'Unknown')}</h4>
            <p style="margin: 5px 0;"><b>Type:</b> {row.get('business_type', 'N/A')}</p>
            <p style="margin: 5px 0;"><b>Address:</b> {row.get('address', 'N/A')}</p>
            <p style="margin: 5px 0;"><b>Phone:</b> {phone}</p>
            <p style="margin: 5px 0;"><b>Google Rating:</b> {rating}</p>
            <hr style="margin: 10px 0; border: 1px solid #eee;">
            <p style="margin: 5px 0;"><b>Opportunity Score:</b> <span style="color: {'green' if row.get('opportunity_score', 0) >= 70 else 'orange'}; font-weight: bold;">{row.get('opportunity_score', 0)}/100</span></p>
            <p style="margin: 5px 0;"><b>Has Bitcoin ATM:</b> {'Yes' if has_atm else 'No'}</p>
            <a href="https://www.google.com/maps/search/?api=1&query={lat},{lon}" target="_blank" style="display: inline-block; margin-top: 10px; padding: 5px 10px; background: #4285f4; color: white; text-decoration: none; border-radius: 4px;">Open in Google Maps</a>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color, icon="info-sign"),
            tooltip=f"{row.get('business_name', 'Unknown')} (Score: {row.get('opportunity_score', 0)})"
        ).add_to(marker_cluster)

    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background-color: white; padding: 15px; border-radius: 8px;
                border: 2px solid #ccc; font-family: Arial, sans-serif; font-size: 14px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);">
        <h4 style="margin: 0 0 10px 0;">Bitcoin ATM Opportunities - Miami</h4>
        <p style="margin: 5px 0;"><span style="color: green; font-size: 18px;">●</span> High Opportunity (Score 70+)</p>
        <p style="margin: 5px 0;"><span style="color: orange; font-size: 18px;">●</span> Medium Opportunity (50-69)</p>
        <p style="margin: 5px 0;"><span style="color: gray; font-size: 18px;">●</span> Low Opportunity (&lt;50)</p>
        <p style="margin: 5px 0;"><span style="color: red; font-size: 18px;">●</span> Already Has ATM</p>
        <hr style="margin: 10px 0;">
        <p style="margin: 0; font-size: 12px; color: #666;">Click markers for details</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Add title
    title_html = """
    <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%); z-index: 1000;
                background-color: #333; color: white; padding: 10px 20px; border-radius: 8px;
                font-family: Arial, sans-serif; font-size: 18px; font-weight: bold;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);">
        🪙 Bitcoin ATM Placement Opportunities - Miami, FL
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # Save to HTML
    output_file = "bitcoin_atm_opportunities_map.html"
    m.save(output_file)

    print(f"\nMap exported to: {output_file}")
    print(f"Total locations: {len(df)}")
    print(f"High opportunity (70+): {len(df[df['opportunity_score'] >= 70])}")
    print(f"\nShare this HTML file with anyone - they can open it in any browser!")

    return output_file


if __name__ == "__main__":
    export_map()
