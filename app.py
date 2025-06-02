import streamlit as st
from newspaper import Article
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut
import pandas as pd
from fuzzywuzzy import fuzz
import os
import pgeocode
import re


# === File Path to Shared CSV ===
SHARED_PATH = r"C:\Users\unc\OneDrive - University of North Carolina at Chapel Hill\irmii\hurricane_helene_news.csv"

# defining
geolocator = Nominatim(user_agent="helene_news_app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
reverse_geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)

# Initialize pgeocode for US postal codes
nomi = pgeocode.Nominatim('us')

# Load the town-to-county mapping Excel file
county_df = pd.read_excel(
    "C:/Users/unc/OneDrive - University of North Carolina at Chapel Hill/irmii/townsandcounties.xlsx"
)

# Normalize town names for easier matching
county_df['Town'] = county_df['Town'].str.lower().str.strip()
county_df['County'] = county_df['County'].str.strip()

# === Load or create data file ===
def load_data():
    if os.path.exists(SHARED_PATH):
        return pd.read_csv(SHARED_PATH)
    else:
        return pd.DataFrame(columns=[
            "ID", "Link", "Project", "Address", "Name", "Town", "Keywords",
            "Citation", "Latitude", "Longitude", "County"
        ])

# === Generate next ID ===
def get_next_id(df):
    return len(df) + 1

# === Extract AMA citation from article URL ===
def get_ama_citation(url):
    article = Article(url)
    try:
        article.download()
        article.parse()
        author = article.authors[0] if article.authors else "Unknown"
        date = article.publish_date.strftime("%Y") if article.publish_date else "n.d."
        return f"{author}. {article.title}. {article.source_url}; {date}."
    except Exception as e:
        return f"Could not extract citation: {e}"

# === Address to coordinates ===
def geocode_address(address):
    try:
        location = geocode(address)
        if location:
            latitude = location.latitude
            longitude = location.longitude
            return latitude, longitude, location
    except GeocoderTimedOut:
        pass
    return None, None, None 

# zip code from address
def extract_zip_from_location(location):
    if location and location.raw and "address" in location.raw:
        zip_code = location.raw["address"].get("postcode")
        return zip_code
    return None

# pull county from zip or city
def get_county_from_location(location, city_input=None, zip_input=None):
    # Try from location zip first
    zip_code = extract_zip_from_location(location)
    if zip_code:
        result = nomi.query_postal_code(zip_code)
        if isinstance(result, pd.Series) and pd.notna(result.county_name):
            return result.county_name
    
    # fallback to city input if zip code fails or not found
    if city_input:
        city_norm = city_input.lower().strip()
        match = county_df[county_df['Town'] == city_norm]
        if not match.empty:
            return match.iloc[0]['County']
    
    # fallback to manual zip input if provided
    if zip_input:
        result = nomi.query_postal_code(zip_input)
        if isinstance(result, pd.Series) and pd.notna(result.county_name):
            return result.county_name

    return "Unknown"


# === Streamlit UI ===
st.title("🌀 Hurricane Helene News Submission Form")

with st.form("news_form"):
    link = st.text_input("🔗 Link to Article (required)")
    project = st.multiselect("📁 Project (select one or both)", ["Coastal", "Healthcare"])
    st.markdown("📍 **Address Details (optional)**")
    street_number = st.text_input("Street Number")
    street_name = st.text_input("Street Name")
    city = st.text_input("City (capitalize first letter of each word)")
    state = st.text_input("State", value="North Carolina")  # default to NC
    zip_code_input = st.text_input("Zip Code (optional, used if geocode fails)")
    lat_input = st.text_input("Latitude (optional, used if geocode fails)")
    lon_input = st.text_input("Longitude (optional, used if geocode fails)")
    name = st.text_input("👤 Name (optional)")
    town = st.text_input("🏘️ Place/district (optional)")
    keywords = st.text_input("🔑 Keywords ie flooding, illness, etc (optional)")
    submitted = st.form_submit_button("Submit Article")

address = f"{street_number} {street_name}, {city}, {state}"

if submitted:
    if not link or not project:
        st.error("Please fill out the required fields: Link and Project.")
    else:
        df = load_data()
        new_id = get_next_id(df)
        citation = get_ama_citation(link)

        lat, lon, location = geocode_address(address)

        # Fallback latitude/longitude if geocode failed
        if not lat and lat_input:
            try:
                lat = float(lat_input)
            except ValueError:
                lat = None
        if not lon and lon_input:
            try:
                lon = float(lon_input)
            except ValueError:
                lon = None

        # Get county from geocode location, city, or zip code input
        county = get_county_from_location(location, city_input=city, zip_input=zip_code_input)

        new_row = {
            "ID": new_id,
            "Link": link,
            "Project": ", ".join(project),
            "Address": address,
            "Name": name,
            "Town": town,
            "Keywords": keywords,
            "Citation": citation,
            "Latitude": lat,
            "Longitude": lon,
            "County": county
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_csv(SHARED_PATH, index=False)

        st.success(f"✅ Article submitted and saved with ID #{new_id}")
        st.write(new_row)

# === View Table ===
st.subheader("📋 Submitted Articles")
df = load_data()
st.dataframe(df)
