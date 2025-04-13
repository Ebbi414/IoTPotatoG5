# A STUB version for testing the Streamlit UI without real AWS calls.
import os
import uuid
import time
import logging
from io import BytesIO  # Needed to simulate file reading
from dotenv import load_dotenv

# Load environment variables from .env file FIRST
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("--- USING STUBBED aws_utils FOR UI TESTING ---")

# --- Dummy Geocoding Data (needed for location dropdown) ---
LOCATION_COORDS = {
    "Uppsala": (59.86, 17.64),
    "Stockholm": (59.33, 18.06),
    "Malmö": (55.60, 13.00),
    "Göteborg": (57.71, 11.97),
    "Örebro": (59.27, 15.21),
    "Linköping": (58.41, 15.62),
    "Vasteras": (59.61, 16.55),
    "Lund": (55.70, 13.19)
}
DEFAULT_LOCATION = "Stockholm"  # Default for stub

# --- Stubbed Functions ---


def get_weather_for_location(location_name):
    """STUB: Returns fake weather data."""
    logger.info(f"[STUB] get_weather_for_location called for: {location_name}")
    time.sleep(0.5)  # Simulate network delay
    # Return some plausible fake data
    fake_temp = round(10 + len(location_name) % 15, 1)  # Some variation
    fake_humidity = 60 + len(location_name) % 30
    fake_precip = round((len(location_name) % 5) * 0.1, 1)
    return {
        "temp": fake_temp,
        "humidity": fake_humidity,
        "precip": fake_precip,
        "error": None
    }


def upload_to_s3(file_obj, bucket_name, object_name=None):
    """STUB: Simulates S3 upload."""
    # Try to read filename like the real function for logging
    original_filename = getattr(file_obj, 'filename', 'unknown_file')
    if object_name is None:
        object_name = original_filename
    # Generate a fake S3 key structure like the real one
    final_object_name = f"uploads/{uuid.uuid4()}-{os.path.basename(object_name)}"

    logger.info(f"[STUB] upload_to_s3 called for bucket '{bucket_name}'")
    logger.info(f"[STUB]   Original Filename: {original_filename}")
    logger.info(
        f"[STUB]   Simulating upload as: s3://{bucket_name}/{final_object_name}")

    # Simulate reading the file (optional, checks if file_obj is readable)
    try:
        file_obj.read(1024)  # Try reading a small chunk
        file_obj.seek(0)    # Reset pointer if needed by caller
    except Exception as e:
        logger.warning(f"[STUB] Could not simulate reading file object: {e}")

    time.sleep(1)  # Simulate upload time
    logger.info(f"[STUB]   Upload successful (simulated).")
    # Return the simulated S3 object name (key)
    return final_object_name


def post_text_to_lex(bot_id, alias_id, session_id, input_text, session_attributes=None):
    """STUB: Simulates calling Lex and returns canned responses."""
    logger.info(
        f"[STUB] post_text_to_lex called for bot '{bot_id}', alias '{alias_id}'")
    logger.info(f"[STUB]   Session ID: {session_id}")
    logger.info(f"[STUB]   Input Text: {input_text}")
    logger.info(f"[STUB]   Session Attributes: {session_attributes}")
    time.sleep(0.7)  # Simulate Lex processing time

    # Simple echo response for testing
    response_message = f"Okay, you asked about '{input_text}'."
    if session_attributes and 'currentLocation' in session_attributes:
        response_message += f" Location context is '{session_attributes['currentLocation']}'."

    # Simulate eliciting image_name sometimes
    if "risk" in input_text.lower() or "high" in input_text.lower():
        return [
            "Weather indicates high risk based on your query.",
            "Please provide the filename of the uploaded image for analysis."
        ]
    elif "filename" in input_text.lower() or ".jpg" in input_text.lower() or ".png" in input_text.lower():
        return [
            f"Okay, analyzing image '{input_text}' (simulated).",
            "Diagnosis: Healthy (Confidence: 95.0%) - This is a stub result."
        ]
    else:
        return [response_message]

# --- End of Stub Functions ---
