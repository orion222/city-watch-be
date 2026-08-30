import urllib.request
import urllib.parse
import json
import os
import logging
from fastapi import HTTPException

def geocode_address(address: str) -> dict:
    """
    Calls the Geoapify API to geocode an address string.
    Returns a dictionary with 'position' and 'address_details'.
    Raises HTTPException if the geocoding fails or no results are found.
    """
    if not address:
        raise HTTPException(status_code=400, detail="Address string is empty.")

    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Geoapify API key is not set in environment variables.")

    encoded_address = urllib.parse.quote(address)
    url = f"https://api.geoapify.com/v1/geocode/search?text={encoded_address}&apiKey={api_key}"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            geo_data = json.loads(response.read().decode())
    except Exception as e:
        logging.error(f"Error connecting to Geoapify: {str(e)}")
        raise HTTPException(status_code=502, detail="External geocoding service is currently unavailable.")

    if not geo_data.get("features"):
        raise HTTPException(status_code=400, detail="Could not geocode the provided address.")
        
    feature = geo_data["features"][0]["properties"]
    
    lat = feature.get("lat")
    lon = feature.get("lon")
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Could not determine precise coordinates for the provided address.")
    position = [lat, lon]
    
    address_details = {
        "street": feature.get("street", ""),
        "city": feature.get("city", ""),
        "state": feature.get("state", ""),
        "postal_code": feature.get("postcode", ""),
        "country": feature.get("country", "")
    }
    
    return {
        "position": position,
        "address_details": address_details
    }
