import json
import os
import logging
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from constants import GEMINI_REPORT_CREATE_PROMPT, GEMINI_RESPONSE_SCHEMA
from db.db import get_session
from google import genai
from google.genai import types
from db.models import Marker, Address
from utils.geocoding import geocode_address

load_dotenv()
router = APIRouter()
client = genai.Client(
   api_key=os.getenv('GEMINI_API_KEY'),
)

class DescriptionRequest(BaseModel):
    description: str

@router.post("/submit-report-gemini")
def submit_report_gemini(request: DescriptionRequest, session: Session = Depends(get_session)):
  try:
    prompt = GEMINI_REPORT_CREATE_PROMPT.replace("{{description}}", request.description)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
          # -1 thinking budget means that the model will decide how much to think on its own
          thinking_config=types.ThinkingConfig(thinking_budget=-1),
          response_mime_type='application/json',
          response_schema=GEMINI_RESPONSE_SCHEMA
        ),
      )

    raw = response.text or ''
    res = json.loads(raw)
    report = res['report']
    error_msg = "We need more context, please give the following required fields additional to what you provided again: "
    errors = []
    for field in ["category", "address", "title", "urgency", "description"]:
      if field not in report or report[field] is None or report[field] == "":
        errors.append(field)

    if errors:
      raise HTTPException(status_code=422, detail=error_msg + ", ".join(errors))

    # Geocode the address using Geoapify
    address = report["address"]
    if not address:
        raise HTTPException(status_code=400, detail="No address provided for geocoding.")

    geo_result = geocode_address(address)
    address_details = geo_result["address_details"]
    position = geo_result["position"]
    
    new_address = Address(
        street=address_details["street"],
        city=address_details["city"],
        state=address_details["state"],
        postal_code=address_details["postal_code"],
        country=address_details["country"]
    )
    session.add(new_address)
    session.flush()

    new_marker = Marker(
        latitude=position[0],
        longitude=position[1],
        description=report['description'],
        title=report['title'],
        urgency=report['urgency'],
        category=report['category'],
        address_id=new_address.id
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
        "message": "Report successfully created in database"
    }
  except HTTPException:
      raise
  except json.JSONDecodeError as e:
      logging.error(f"Invalid JSON returned from AI model: {raw}")
      raise HTTPException(status_code=500, detail="Invalid JSON returned from AI model") from e
  except Exception as e:
      logging.error(f"Error processing request: {str(e)}")
      raise HTTPException(status_code=500, detail="An internal server error occurred while processing the request.")

