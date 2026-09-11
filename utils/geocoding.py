import json
import logging
import os
import urllib.parse
import urllib.request

from fastapi import HTTPException, logger

GEOAPIFY_BASE_URL = "https://api.geoapify.com/v1/geocode"
REQUEST_TIMEOUT_SECONDS = 10


def _fetch_geoapify_data(endpoint: str, params: dict) -> dict:
    """
    Generic HTTP transport for Geoapify API requests.

    Args:
        endpoint (str): The API sub-path (e.g. 'search' or 'reverse').
        params (dict): Query parameters to encode.

    Returns:
        dict: Parsed JSON response from Geoapify.
    """

    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        logger.error("Geoapify API key is not configured.")
        raise HTTPException(
            status_code=500,
            detail="Service unavailable",
        )

    query_params = {**params, "apiKey": api_key}

    encoded_query = urllib.parse.urlencode(query_params)
    url = f"{GEOAPIFY_BASE_URL}/{endpoint}?{encoded_query}"

    req = urllib.request.Request(url, headers={"User-Agent": "CityWatch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logging.error(f"Error connecting to Geoapify: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail="External geocoding service is currently unavailable.",
        )


def _valid_coords(lat, lon) -> bool:
    """Geoapify has returned numbers we can store as a lat/lng pair."""
    if not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in (lat, lon)):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _extract_address_details(feature: dict) -> dict:
    """Parses the Geoapify feature object into our internal format."""
    lat = feature.get("lat")
    lon = feature.get("lon")

    if lat is None or lon is None:
        raise HTTPException(
            status_code=400,
            detail="Could not determine precise coordinates for the provided address.",
        )

    if not _valid_coords(lat, lon):
        raise HTTPException(status_code=400, detail="Geocoder returned unusable coordinates.")

    return {
        "position": [lat, lon],
        "address_details": {
            "street": feature.get("street", ""),
            "city": feature.get("city", ""),
            "state": feature.get("state", ""),
            "postal_code": feature.get("postcode", ""),
            "country": feature.get("country", ""),
        },
    }


def _parse_address_properties(properties: dict) -> dict:
    """
    Extracts address fields from Geoapify feature's properties.

    Args:
        properties (dict): The properties dictionary from a Geoapify feature.

    Returns:
        dict: A dictionary containing the extracted address fields.
    """

    return {
        "street": properties.get("street", ""),
        "city": properties.get("city", ""),
        "state": properties.get("state", ""),
        "postal_code": properties.get("postcode", ""),
        "country": properties.get("country", ""),
    }


def geocode_address(address: str) -> dict:
    """
    Forward geocodes an address string to coordinates and structured address details.

    Returns:
        dict: {
            "position": [lat, lon],
            "address_details": {"street": ..., "city": ..., "state": ..., "postal_code": ..., "country": ...}
        }
    """

    if not address or not address.strip():
        raise HTTPException(status_code=400, detail="Address string is empty.")

    geo_data = _fetch_geoapify_data("search", {"text": address.strip()})
    features = geo_data.get("features", [])

    if not features:
        raise HTTPException(status_code=400, detail="Could not geocode the provided address.")

    props = features[0].get("properties", {})
    lat = props.get("lat")
    lon = props.get("lon")

    if not _valid_coords(lat, lon):
        raise HTTPException(status_code=400, detail="Geocoder returned unusable coordinates.")

    return {"position": [lat, lon], "address_details": _extract_address_details(features[0])}


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Converts (latitude, longitude) coordinates to an address dictionary using Geoapify.

    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.

    Returns:
        dict: Parsed address dictionary, or None if no address is found or service is unavailable.
    """
    if not _valid_coords(lat, lon):
        logger.warning(f"Invalid coordinates passed to reverse_geocode: lat={lat}, lon={lon}")
        return None

    try:
        geo_data = _fetch_geoapify_data("reverse", {"lat": lat, "lon": lon})
        features = geo_data.get("features", [])
        if not features:
            logger.info(f"No address found for coordinates: lat={lat}, lon={lon}")
            return None

        props = features[0].get("properties", {})
        return _parse_address_properties(props)
    except Exception as e:
        logger.warning(f"Reverse geocoding failed for ({lat}, {lon}): {e}")
        return None
