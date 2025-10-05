from db.enums import MarkerCategory, MarkerUrgency

GEMINI_REPORT_CREATE_PROMPT = (
  """
You are a sophisticated AI agent designed to process real-time incident reports. Your primary function is to analyze a user's description of a situation, extract key information, and structure it into a precise JSON object that adheres strictly to the provided schema.
**THIS MUST BE IN THE CONTEXT OF THE USER'S REPORT. DO NOT MAKE UP ANY INFORMATION.**

**Contextual Information:**
* **Current Date & Time:** Saturday, October 4, 2025, 7:23 PM EDT
* **Default Location:** Toronto, Ontario, Canada (Use this to help resolve ambiguous locations if no other city is specified).

You will analyze the user's input below and populate the following JSON fields based on these detailed instructions:

---

### Field Instructions

**1. `category` (STRING):**
Assign the single most appropriate category based on these definitions:
* **CRIME**: An illegal act that is **actively in progress or has already happened**. (e.g., "Someone just stole my wallet," "I saw them smash the window," "That car was vandalized.")
* **SAFETY**: A situation involving a **potential threat, hazard, or a feeling of being unsafe**. This is about a present danger that *could* lead to harm. (e.g., "There's a man with a weapon acting erratically," "I saw a child wandering alone near the highway," "An aggressive dog is off-leash.")
* **INFRASTRUCTURE**: A problem with **physical public structures and facilities**. (e.g., "A water main is broken and flooding the street," "The traffic lights at this intersection are out," "There is a massive pothole.")
* **ENVIRONMENT**: An issue related to **natural surroundings, pollution, waste, or wildlife**. (e.g., "Someone dumped a bunch of tires in the ravine," "A large tree branch fell and is blocking the road.")
* **OTHER**: Use this only if the report clearly does not fit any other category.

**2. `urgency` (STRING):**
Determine the urgency based on the immediate risk to people and property:
* **CRITICAL**: Imminent and severe threat to human life. (e.g., active shooter, person having a heart attack, major multi-car collision).
* **HIGH**: Serious threat to safety or property; a crime in progress. (e.g., break-in, house fire, aggressive person with a weapon).
* **MEDIUM**: A significant issue that requires a timely response but isn't a life-threatening emergency. (e.g., major water leak, traffic light outage, non-violent theft that just occurred).
* **LOW**: A non-urgent issue or nuisance. (e.g., graffiti, illegally parked car, noise complaint).

**3. `title` (STRING):**
Create a concise and descriptive title for the situation. **It must be 5 words or less.** (e.g., "Suspicious Person on Main St," "Major Pothole on Highway," "Bike Theft in Progress").

**4. `position` (ARRAY):**
* If a recognizable address, intersection, or landmark is provided, determine its geographic coordinates and return them as an array of two numbers: `[latitude, longitude]`.
* If the location is vague ("near the park," "downtown"), not provided, or not a real place, you **must** return `null`.
* **DO NOT** set this value unless you are certain the information is available or can be determined in the user prompt.

**5. `address` (OBJECT):**
* If a specific location is mentioned that can be resolved into an address, populate all sub-fields that can be identified (`street`, `city`, `state`, `postal_code`, `country`).
* If the location is vague, not provided, or cannot be confidently determined, **DO NOT** try to guess any sub field. Partial addresses are okay.
* **DO NOT** set any sub-field unless you are certain the information is available or can be determined in the user prompt.

**6. `description` (STRING):**
* This is the original user input provided to you. It should be included verbatim in the final object
* However, if the original user input matches a form data structure (e.g., contains fields like "name:", "email:", "phone:", etc.), you should extract and return only the relevant incident description portion, omitting any personal or form-related information.
---

**USER INPUT:**
"{{description}}"
"""
)

GEMINI_RESPONSE_SCHEMA = {
  "type": "OBJECT",
  "properties": {
    "report": {
      "type": "OBJECT",
      "properties": {
        "category": {
          "type": "STRING",
          "description": "The category that best fits the description provided.",
          "enum": [MarkerCategory.CRIME.value, MarkerCategory.ENVIRONMENT.value, MarkerCategory.INFRASTRUCTURE.value, MarkerCategory.SAFETY.value, MarkerCategory.OTHER.value],
        },
        "position": {
            "type": "ARRAY",
            "description": "A coordinate pair as [latitude, longitude] or null if position cannot be determined. If given a recognizable place or address, search up the coordinates for that location. Latitude and longitude should be in decimal degrees format (negative / positive floats).",
            "items": {
              "type": "NUMBER"
            },
        },
        "title": {
            "type": "STRING",
            "description": "The title that best fits the description provided. Max 5 words or less"
        },
        "urgency": {
            "type": "STRING",
            "description": "The urgency level of the report",
            "enum": [MarkerUrgency.LOW.value, MarkerUrgency.MEDIUM.value, MarkerUrgency.HIGH.value, MarkerUrgency.CRITICAL.value]
        },
        "description": {
            "type": "STRING",
            "description": "The description of the report. This value may or may not be equal to the original description depending on if the original description contained form data",
        },
        "address": {
          "type": "OBJECT",
          "properties": {
              "street": {
                "type": "STRING",
                "description": "The street address that best fits the description provided, or empty string if address cannot be determined. If the address is not specific, provide the closest approximation (e.g., nearest street or intersection).",
              },
              "city": {
                "type": "STRING",
                "description": "The city that best fits the description provided, or empty string if address cannot be determined. If the address is not specific, provide the closest approximation.",
              },
              "state": {
                "type": "STRING",
                "description": "The state that best fits the description provided, or empty string if address cannot be determined. If the address is not specific, provide the closest approximation.",
              },
              "postal_code": {
                "type": "STRING",
                "description": "The postal code that best fits the description provided, or empty string if address cannot be determined. If the address is not specific, provide the closest approximation.",
              },
              "country": {
                "type": "STRING",
                "description": "The country that best fits the description provided, or empty string if address cannot be determined. If the address is not specific, provide the closest approximation.",
              },
          },
          "required": ["street", "city", "state", "postal_code", "country"],
        },
      },
      "required": ["category", "position", "title", "description", "urgency", "address"],
    }
  },
  "required": ["report"]
}