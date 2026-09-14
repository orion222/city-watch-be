import json
import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlmodel import Session

from constants import (
    GEMINI_MULTIMODAL_PROMPT,
    GEMINI_MULTIMODAL_RESPONSE_SCHEMA,
    GEMINI_REPORT_CREATE_PROMPT,
    GEMINI_RESPONSE_SCHEMA,
)
from db.db import get_session
from db.models import Address, Marker
from utils.geocoding import GeoapifyClient, get_geocoding_client
from utils.image_processing import ALLOWED_MIME_TYPES, process_image
from utils.rate_limit import limiter
from utils.storage import upload_image_to_s3

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.5-flash-lite"
THINKING_BUDGET = 1024  # Adjust this value based on your requirements, -1 for unlimited
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB upload limit for images

load_dotenv()
router = APIRouter()


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")
    return genai.Client(api_key=api_key)


class DescriptionRequest(BaseModel):
    description: str = Field(max_length=4000)  # Character limit, around 800 words


def _raise_structured_422(
    message: str,
    report: dict | None = None,
    missing_fields: list[str] | None = None,
    address_override: str | None = None,
):
    rep = report or {}
    extracted = {
        "description": rep.get("description") or "",
        "urgency": rep.get("urgency") or "",
        "title": rep.get("title") or "",
        "category": rep.get("category") or "",
        "address": address_override if address_override is not None else (rep.get("address") or ""),
    }
    raise HTTPException(
        status_code=422,
        detail={
            "message": message,
            "missing_fields": missing_fields or [],
            "extracted_data": extracted,
        },
    )


@router.post("/submit-report-gemini")
@limiter.limit("5/minute;30/hour")
def submit_report_gemini(
    request: Request,  # Needed for limiter to capture IP address
    body: DescriptionRequest,
    session: Session = Depends(get_session),
    geo_client=Depends(get_geocoding_client),
):
    try:
        prompt = GEMINI_REPORT_CREATE_PROMPT.replace("{{description}}", body.description)
        response = get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
                response_mime_type="application/json",
                response_schema=GEMINI_RESPONSE_SCHEMA,
            ),
        )

        raw = response.text or ""
        res = json.loads(raw)
        report = res["report"]
        error_msg = (
            "We need more context, please give the following required fields additional to what you provided again: "
        )
        errors = []
        for field in ["category", "address", "title", "urgency", "description"]:
            if field not in report or report[field] is None or report[field] == "":
                errors.append(field)

        if errors:
            _raise_structured_422(
                error_msg + ", ".join(errors),
                report=report,
                missing_fields=errors,
            )

        # Geocode the address using Geoapify
        address = report.get("address")
        if not address:
            _raise_structured_422(
                "No address provided for geocoding. Please specify an address.",
                report=report,
                missing_fields=["address"],
                address_override="",
            )

        try:
            geo_result = geo_client.geocode(address)
        except HTTPException as e:
            if e.status_code in (400, 502):
                _raise_structured_422(
                    f"Could not geocode the address '{address}'. Please choose an address from the search bar.",
                    report=report,
                    missing_fields=["address"],
                    address_override=address,
                )
            raise
        address_details = geo_result["address_details"]
        position = geo_result["position"]

        new_address = Address(
            street=address_details["street"],
            city=address_details["city"],
            state=address_details["state"],
            postal_code=address_details["postal_code"],
            country=address_details["country"],
        )
        session.add(new_address)
        session.flush()

        new_marker = Marker(
            latitude=position[0],
            longitude=position[1],
            description=report["description"],
            title=report["title"],
            urgency=report["urgency"],
            category=report["category"],
            address_id=new_address.id,
        )
        session.add(new_marker)
        session.commit()
        session.refresh(new_address)
        session.refresh(new_marker)

        return {
            **res,
            "status": 200,
            "created_marker_id": new_marker.id,
            "created_address_id": new_address.id,
            "message": "Report successfully created in database",
        }
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON returned from AI model: {raw}")
        raise HTTPException(status_code=500, detail="Invalid JSON returned from AI model") from e
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while processing the request.",
        )


@router.post("/submit-report-gemini-multimodal")
@limiter.limit("5/minute;30/hour")
def submit_report_gemini_multimodal(
    request: Request,
    image: UploadFile = File(...),
    description: str = Form(""),
    session: Session = Depends(get_session),
    geo_client: GeoapifyClient = Depends(get_geocoding_client),
):
    """
    Multimodal incident report endpoint.
    Accepts an uploaded image and an optional note.
    Processes EXIF GPS, strips metadata, queries Gemini,
    persists image to S3, resolves address with GeoapifyClient, and creates a Marker.
    """

    # Validate MIME type
    if image.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{image.content_type}'. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    file_bytes = image.file.read(MAX_FILE_SIZE + 1)  # Read up to 5MB + 1 byte to check size
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({len(file_bytes)} bytes) exceeds the 5MB limit.",
        )

    # Sanitize image, extract EXIF GPS, rotate, downscale, and convert to clean JPEG
    clean_bytes, output_mime, exif_lat, exif_lon = process_image(file_bytes)

    try:
        user_note = description.strip() if description else "None provided."
        prompt_text = GEMINI_MULTIMODAL_PROMPT.replace("{{description}}", user_note)
        image_part = types.Part.from_bytes(data=clean_bytes, mime_type=output_mime)

        response = get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=[image_part, prompt_text],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GEMINI_MULTIMODAL_RESPONSE_SCHEMA,
            ),
        )

        raw = response.text or "{}"
        res = json.loads(raw)
        report = res.get("report") or {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON returned from AI model: {raw}")
        raise HTTPException(status_code=500, detail="Invalid JSON returned from AI model.") from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini multimodal inference error: {e}")
        raise HTTPException(status_code=500, detail="AI report generation failed.") from e

    # Check incident validity (Confidence gate for ambiguous/unrelated images)
    if not report.get("is_valid_incident", False):
        raise HTTPException(
            status_code=422,
            detail=(
                "The uploaded image does not appear to depict a civic or municipal incident. "
                "Please provide a clear photo of the issue."
            ),
        )

    # Validate mandatory fields
    missing_fields = []
    for field in ["title", "category", "urgency", "description"]:
        if not report.get(field):
            missing_fields.append(field)
    if missing_fields:
        _raise_structured_422(
            f"AI could not determine '{', '.join(missing_fields)}' from the photo. Please provide more context.",
            report=report,
            missing_fields=missing_fields,
        )

    # 8. Geolocation resolution hierarchy
    marker_lat: float
    marker_lon: float
    address_id: int | None = None
    new_address: Address | None = None

    if exif_lat is not None and exif_lon is not None:
        # Priority 1: Hardware EXIF GPS coordinates
        marker_lat, marker_lon = exif_lat, exif_lon
        try:
            rev_addr = geo_client.reverse_geocode(exif_lat, exif_lon)
            if rev_addr and any(rev_addr.values()):
                new_address = Address(
                    street=rev_addr.get("street") or "Unknown Street",
                    city=rev_addr.get("city") or "Unknown City",
                    state=rev_addr.get("state") or "",
                    postal_code=rev_addr.get("postal_code") or None,
                    country=rev_addr.get("country") or "",
                )
                session.add(new_address)
                session.flush()
                address_id = new_address.id
        except Exception as e:
            logger.warning(f"Reverse geocoding failed for EXIF coordinates ({exif_lat}, {exif_lon}): {e}")
    else:
        # Priority 2: Inferred address from Gemini
        extracted_address = report.get("address")
        if not extracted_address:
            _raise_structured_422(
                "No EXIF GPS coordinates were found in the photo, and no location could be identified. "
                "Please specify the address in the location field.",
                report=report,
                missing_fields=["location"],
                address_override="",
            )

        try:
            geo_result = geo_client.geocode(extracted_address)
        except HTTPException as e:
            if e.status_code in (400, 502):
                _raise_structured_422(
                    f"AI identified location '{extracted_address}', but it could not be geocoded. "
                    "Please select a recognized address from the search bar.",
                    report=report,
                    missing_fields=["location"],
                    address_override=extracted_address,
                )
            raise

        address_details = geo_result["address_details"]
        marker_lat, marker_lon = geo_result["position"]

        new_address = Address(
            street=address_details.get("street") or "Unknown Street",
            city=address_details.get("city") or "Unknown City",
            state=address_details.get("state") or "",
            postal_code=address_details.get("postal_code") or None,
            country=address_details.get("country") or "",
        )
        session.add(new_address)
        session.flush()
        address_id = new_address.id

    image_url = upload_image_to_s3(clean_bytes, content_type=output_mime)

    # 9. Create and persist Marker
    new_marker = Marker(
        latitude=marker_lat,
        longitude=marker_lon,
        description=report["description"],
        title=report["title"],
        urgency=report["urgency"],
        category=report["category"],
        address_id=address_id,
        image_url=image_url,
    )
    session.add(new_marker)
    session.commit()
    session.refresh(new_marker)
    if new_address:
        session.refresh(new_address)

    return {
        "status": 200,
        "message": "Report successfully created from photo",
        "created_marker_id": new_marker.id,
        "created_address_id": address_id,
        "image_url": image_url,
        "report": report,
    }
