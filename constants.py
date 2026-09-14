from db.enums import MarkerCategory, MarkerUrgency
from datetime import datetime,UTC
GEMINI_REPORT_CREATE_PROMPT = f"""
You are a sophisticated AI agent designed to process real-time incident reports.
Your primary function is to analyze a user's description of a situation,
extract key information, and structure it into a precise JSON object that
adheres strictly to the provided schema.
**THIS MUST BE IN THE CONTEXT OF THE USER'S REPORT. DO NOT MAKE UP ANY INFORMATION.**

**Contextual Information:**
* **Current Date & Time:**  {datetime.now(UTC)}
* **Default Location:** Toronto, Ontario, Canada (Use this to help resolve
  ambiguous locations if no other city is specified).

You will analyze the user's input below and populate the following JSON fields based on these detailed instructions:

---

### Field Instructions

**1. `category` (STRING):**
Assign the single most appropriate category based on these definitions:
* **CRIME**: An illegal act that is **actively in progress or has already happened**.
  (e.g., "Someone just stole my wallet," "I saw them smash the window," "That car was vandalized.")
* **SAFETY**: A situation involving a **potential threat, hazard, or a feeling of being unsafe**.
  This is about a present danger that *could* lead to harm. (e.g., "There's a man with a weapon acting erratically,"
  "I saw a child wandering alone near the highway," "An aggressive dog is off-leash.")
* **INFRASTRUCTURE**: A problem with **physical public structures and facilities**.
  (e.g., "A water main is broken and flooding the street," "The traffic lights at this intersection are out,"
  "There is a massive pothole.")
* **ENVIRONMENT**: An issue related to **natural surroundings, pollution, waste, or wildlife**.
  (e.g., "Someone dumped a bunch of tires in the ravine," "A large tree branch fell and is blocking the road.")
* **OTHER**: Use this only if the report clearly does not fit any other category.

**2. `urgency` (STRING):**
Determine the urgency based on the immediate risk to people and property:
* **CRITICAL**: Imminent and severe threat to human life. (e.g., active shooter,
  person having a heart attack, major multi-car collision).
* **HIGH**: Serious threat to safety or property; a crime in progress. (e.g., break-in,
  house fire, aggressive person with a weapon).
* **MEDIUM**: A significant issue that requires a timely response but isn't a life-threatening emergency.
  (e.g., major water leak, traffic light outage, non-violent theft that just occurred).
* **LOW**: A non-urgent issue or nuisance. (e.g., graffiti, illegally parked car, noise complaint).

**3. `title` (STRING):**
Create a concise and descriptive title for the situation. **It must be 5 words or less.**
(e.g., "Suspicious Person on Main St," "Major Pothole on Highway," "Bike Theft in Progress").

**4. `address` (STRING):**
* Identify any location mentioned in the description and output it as a single readable address string.
* If no location is found, output an empty string.

**5. `description` (STRING):**
* This is the original user input provided to you. It should be included verbatim in the final object
* However, if the original user input matches a form data structure (e.g., contains fields like "name:",
  "email:", "phone:", etc.), you should extract and return only the relevant incident description portion,
  omitting any personal or form-related information.
---

**USER INPUT:**
"{{description}}"
"""

GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "report": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "The category that best fits the description provided.",
                    "enum": [
                        MarkerCategory.CRIME.value,
                        MarkerCategory.ENVIRONMENT.value,
                        MarkerCategory.INFRASTRUCTURE.value,
                        MarkerCategory.SAFETY.value,
                        MarkerCategory.OTHER.value,
                    ],
                },
                "address": {
                    "type": "STRING",
                    "description": (
                        "A single readable address string extracted from the "
                        "description, or an empty string if no location is found."
                    ),
                },
                "title": {
                    "type": "STRING",
                    "description": "The title that best fits the description provided. Max 5 words or less",
                },
                "urgency": {
                    "type": "STRING",
                    "description": "The urgency level of the report",
                    "enum": [
                        MarkerUrgency.LOW.value,
                        MarkerUrgency.MEDIUM.value,
                        MarkerUrgency.HIGH.value,
                        MarkerUrgency.CRITICAL.value,
                    ],
                },
                "description": {
                    "type": "STRING",
                    "description": (
                        "The description of the report. This value may or may not "
                        "be equal to the original description depending on if the "
                        "original description contained form data"
                    ),
                },
            },
            "required": [
                "category",
                "address",
                "title",
                "description",
                "urgency",
            ],
        }
    },
    "required": ["report"],
}

GEMINI_MULTIMODAL_PROMPT = """
You are a sophisticated AI agent designed to process real-time municipal incident reports based
on an uploaded image and an optional text note from a citizen.

Your task is to analyze the visual evidence in the image alongside the user's optional note and
output a structured JSON report.

### Detailed Instructions:

1. **Validity Check (`is_valid_incident`):**
    - First, determine whether the image clearly depicts a genuine municipal incident,
      civic problem, hazard, or infrastructure defect (e.g., potholes, broken streetlights,
      graffiti, illegal dumping, flooding, road obstructions, vandalized property,
      safety threats).
    - If the image is unrelated (e.g., a selfie, a pet, food, a meme, an empty wall,
      completely dark/blurry, or irrelevant), you MUST set `is_valid_incident` to false.
      You can leave the remaining fields empty.
    - Only set `is_valid_incident` to true if a genuine civic incident is observable.

2. **Factual Grounding (DO NOT INVENT DETAILS):**
    - You must strictly describe what is visually observable in the image.
    - Do NOT invent causes, suspect names, vehicle license plates, or specific details
      that you cannot clearly see.

3. **Field Extraction (When `is_valid_incident` is true):**
    - **`category`**: Choose the single best fit from:
      ["Crime", "Environment", "Infrastructure", "Safety", "Other"].
    - **`urgency`**: Choose from: ["Low", "Medium", "High", "Critical"] based on immediate
      danger to public safety or property.
    - **`title`**: A concise, descriptive title of 5 words or less
      (e.g., "Deep Pothole on Right Lane", "Fallen Tree Blocking Sidewalk").
    - **`description`**: A clear, factual summary synthesizing what is seen in the image
      and any context from the user's note.
    - **`address`**: If visible street signs, storefronts, building numbers, or text in
      the user note mention a specific location, extract it as a readable address string.
      Otherwise, leave it as an empty string.

**USER'S OPTIONAL NOTE:**
"{{description}}"
"""

GEMINI_MULTIMODAL_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "report": {
            "type": "OBJECT",
            "properties": {
                "is_valid_incident": {
                    "type": "BOOLEAN",
                    "description": (
                        "Set to true if the image depicts a real civic or municipal issue, "
                        "false if unrelated or ambiguous."
                    ),
                },
                "category": {
                    "type": "STRING",
                    "description": "The category that best fits the incident depicted.",
                    "enum": [
                        MarkerCategory.CRIME.value,
                        MarkerCategory.ENVIRONMENT.value,
                        MarkerCategory.INFRASTRUCTURE.value,
                        MarkerCategory.SAFETY.value,
                        MarkerCategory.OTHER.value,
                    ],
                },
                "address": {
                    "type": "STRING",
                    "description": (
                        "Readable address or location extracted from image landmarks or user note, or empty string."
                    ),
                },
                "title": {
                    "type": "STRING",
                    "description": "A concise title describing the situation. Max 5 words.",
                },
                "urgency": {
                    "type": "STRING",
                    "description": "Urgency level of the report.",
                    "enum": [
                        MarkerUrgency.LOW.value,
                        MarkerUrgency.MEDIUM.value,
                        MarkerUrgency.HIGH.value,
                        MarkerUrgency.CRITICAL.value,
                    ],
                },
                "description": {
                    "type": "STRING",
                    "description": "Factual description of the incident based on visual evidence and user note.",
                },
            },
            "required": ["is_valid_incident"],
        }
    },
    "required": ["report"],
}
