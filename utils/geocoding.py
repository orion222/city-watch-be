import urllib.request
import urllib.parse
import json
import os
import logging
from fastapi import HTTPException

def _fetch_geoapify_data(address: str) -> dict:
    """Handles the external API request to Geoapify."""
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Geoapify API key is not set in environment variables.")

    encoded_address = urllib.parse.quote(address)
    url = f"https://api.geoapify.com/v1/geocode/search?text={encoded_address}&apiKey={api_key}"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logging.error(f"Error connecting to Geoapify: {str(e)}")
        raise HTTPException(status_code=502, detail="External geocoding service is currently unavailable.")

def _extract_address_details(feature: dict) -> dict:
    """Parses the Geoapify feature object into our internal format."""
    lat = feature.get("lat")
    lon = feature.get("lon")
    
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Could not determine precise coordinates for the provided address.")
        
    return {
        "position": [lat, lon],
        "address_details": {
            "street": feature.get("street", ""),
            "city": feature.get("city", ""),
            "state": feature.get("state", ""),
            "postal_code": feature.get("postcode", ""),
            "country": feature.get("country", "")
        }
    }

def geocode_address(address: str) -> dict:
    """
    Orchestrates the geocoding process:
    1. Fetches data from Geoapify
    2. Parses and formats the response
    """
    if not address:
        raise HTTPException(status_code=400, detail="Address string is empty.")

    geo_data = _fetch_geoapify_data(address)

    if not geo_data.get("features"):
        raise HTTPException(status_code=400, detail="Could not geocode the provided address.")
        
    feature = geo_data["features"][0]["properties"]
    return _extract_address_details(feature)
