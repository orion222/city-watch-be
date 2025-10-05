import json
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from constants import GEMINI_REPORT_CREATE_PROMPT, GEMINI_RESPONSE_SCHEMA
from db.db import get_session
from google import genai
from google.genai import types
from db.models import Marker, Address


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
    print(request.description)
    prompt = GEMINI_REPORT_CREATE_PROMPT.replace("{{description}}", request.description)
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
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
    error_msg = "We need more context, please give the following required fields: "
    errors = []
    for field in ["category", "position", "title", "urgency", "address", "description"]:
      if field not in report or report[field] is None:
        errors.append(field)
    
    address = report['address']
    for addr_field in ["street", "city", "state", "postal_code", "country"]:
      if addr_field not in address or address[addr_field] is None:
        errors.append(f"address.{addr_field}")

    if errors:
      return {"status_code": 500, "detail": error_msg + ", ".join(errors), "res": res['report']}
        
    new_address = Address(
        street=address['street'],
        city=address['city'],
        state=address['state'],
        postal_code=address['postal_code'],
        country=address['country']
    )
    session.add(new_address)
    session.commit()
    session.refresh(new_address)
    
    new_marker = Marker(
        position=report['position'],
        description=report['description'],
        title=report['title'],
        urgency=report['urgency'],
        category=report['category'],
        address_id=new_address.id
    )
    session.add(new_marker)
    session.commit()
    session.refresh(new_marker)
    
    return {
        **res, 
        "status": 200, 
        "created_marker_id": new_marker.id,
        "created_address_id": new_address.id,
        "message": "Report successfully created in database"
    }
  except json.JSONDecodeError as e:
      raise HTTPException(status_code=500, detail=f"Invalid JSON returned from AI model: {raw}") from e
  except Exception as e:
      raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}") from e

