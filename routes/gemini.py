import json
import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlmodel import Session

from constants import GEMINI_REPORT_CREATE_PROMPT, GEMINI_RESPONSE_SCHEMA
from db.db import get_session
from db.models import Address, Marker
from utils.geocoding import geocode_address
from utils.rate_limit import limiter

THINKING_BUDGET = (
    1024  # Adjust this value based on your requirements, -1 for unlimited
)

load_dotenv()
router = APIRouter()


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503, detail="GEMINI_API_KEY is not configured"
        )
    return genai.Client(api_key=api_key)


class DescriptionRequest(BaseModel):
    description: str = Field(
        max_length=4000
    )  # Character limit, around 800 words


@router.post("/submit-report-gemini")
@limiter.limit("5/minute;30/hour")
def submit_report_gemini(
    request: Request,  # Needed for limiter to capture IP address
    body: DescriptionRequest,
    session: Session = Depends(get_session),
):
    try:
        prompt = GEMINI_REPORT_CREATE_PROMPT.replace(
            "{{description}}", body.description
        )
        response = get_client().models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_budget=THINKING_BUDGET
                ),
                response_mime_type="application/json",
                response_schema=GEMINI_RESPONSE_SCHEMA,
            ),
        )

        raw = response.text or ""
        res = json.loads(raw)
        report = res["report"]
        error_msg = "We need more context, please give the following required fields additional to what you provided again: "
        errors = []
        for field in ["category", "address", "title", "urgency", "description"]:
            if (
                field not in report
                or report[field] is None
                or report[field] == ""
            ):
                errors.append(field)

        if errors:
            raise HTTPException(
                status_code=422, detail=error_msg + ", ".join(errors)
            )

        # Geocode the address using Geoapify
        address = report["address"]
        if not address:
            raise HTTPException(
                status_code=400, detail="No address provided for geocoding."
            )

        geo_result = geocode_address(address)
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
        logging.error(f"Invalid JSON returned from AI model: {raw}")
        raise HTTPException(
            status_code=500, detail="Invalid JSON returned from AI model"
        ) from e
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while processing the request.",
        )
