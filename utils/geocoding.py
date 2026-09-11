import logging
import os
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

logger = logging.getLogger(__name__)

GEOAPIFY_BASE_URL = "https://api.geoapify.com/v1/geocode"
REQUEST_TIMEOUT_SECONDS = 10.0


def _valid_coords(lat, lon) -> bool:
    """Geoapify has returned numbers we can store as a lat/lng pair."""
    if not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in (lat, lon)):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


class GeoapifyClient:
    """
    Dedicated client for Geoapify API.
    Maintains a persistent HTTP connection pool for low-latency geocoding.
    """

    def __init__(self, api_key: str, base_url: str = GEOAPIFY_BASE_URL, timeout: float = REQUEST_TIMEOUT_SECONDS):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": "CityWatch/1.0"},
        )

    def _fetch(self, endpoint: str, params: dict) -> dict:
        query_params = {**params, "apiKey": self.api_key}
        endpoint = endpoint.lstrip("/")
        try:
            response = self._http.get(endpoint, params=query_params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Geoapify HTTP error {e.response.status_code}: {e.response.text}")
            raise HTTPException(
                status_code=502,
                detail="External geocoding service returned an error.",
            ) from e
        except Exception as e:
            logger.error(f"Failed to connect to Geoapify endpoint '{endpoint}': {e}")
            raise HTTPException(
                status_code=502,
                detail="External geocoding service is currently unavailable.",
            ) from e

    @staticmethod
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

    def geocode(self, address: str) -> dict:
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

        geo_data = self._fetch("search", {"text": address.strip()})
        features = geo_data.get("features", [])

        if not features:
            raise HTTPException(status_code=400, detail="Could not geocode the provided address.")

        props = features[0].get("properties", {})
        lat = props.get("lat")
        lon = props.get("lon")

        if not _valid_coords(lat, lon):
            raise HTTPException(status_code=400, detail="Geocoder returned unusable coordinates.")

        return {"position": [lat, lon], "address_details": self._parse_address_properties(props)}

    def reverse_geocode(self, lat: float, lon: float) -> dict | None:
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
            geo_data = self._fetch("reverse", {"lat": lat, "lon": lon})
            features = geo_data.get("features", [])
            if not features:
                logger.info(f"No address found for coordinates: lat={lat}, lon={lon}")
                return None

            props = features[0].get("properties", {})
            return self._parse_address_properties(props)
        except Exception as e:
            logger.warning(f"Reverse geocoding failed for ({lat}, {lon}): {e}")
            return None


@lru_cache(maxsize=1)
def get_geocoding_client() -> GeoapifyClient:
    """
    Returns the singleton GeoapifyClient instance.
    Cached via lru_cache so initialization and environment validation happen only once.
    """
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Geoapify API key is not set in environment variables.",
        )
    return GeoapifyClient(api_key=api_key)


# --- Module-level convenience wrappers ---
def geocode_address(address: str) -> dict:
    """
    Forward geocodes an address string to coordinates and structured address details using Geoapify client.

    Returns:
        dict: {
            "position": [lat, lon],
            "address_details": {"street": ..., "city": ..., "state": ..., "postal_code": ..., "country": ...}
        }
    """
    return get_geocoding_client().geocode(address)


def reverse_geocode(lat: float, lon: float) -> dict | None:
    """
    Converts (latitude, longitude) coordinates to an address dictionary using Geoapify client.

    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.

    Returns:
        dict: Parsed address dictionary, or None if no address is found or service is unavailable.
    """
    return get_geocoding_client().reverse_geocode(lat, lon)
