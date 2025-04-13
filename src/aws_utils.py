import boto3
import os
import uuid
import logging
import requests  # Make sure requests is importable here
import json     # For JSON decoding
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Initialize clients
try:
    aws_region = os.environ['AWS_REGION']
    s3_client = boto3.client('s3', region_name=aws_region)
    lex_client = boto3.client('lexv2-runtime', region_name=aws_region)
except KeyError as e:
    logger.error(
        f"Missing critical environment variable: {e}. AWS clients cannot be initialized.")
    raise SystemExit(f"Environment variable {e} not set.") from e
except Exception as e:
    logger.error(f"Error initializing AWS clients: {e}")
    raise SystemExit("Could not initialize AWS clients.") from e

# --- Geocoding Data (copied from Lambda example, keep consistent!) ---
LOCATION_COORDS = {
    "uppsala": (59.86, 17.64),
    "stockholm": (59.33, 18.06),
    "malmö": (55.60, 13.00),  # Handle umlauts if needed
    "malmo": (55.60, 13.00),
    "göteborg": (57.71, 11.97),
    "goteborg": (57.71, 11.97),
    "örebro": (59.27, 15.21),
    "orebro": (59.27, 15.21),
    "linköping": (58.41, 15.62),
    "linkoping": (58.41, 15.62),
    "västerås": (59.61, 16.55),
    "vasteras": (59.61, 16.55),
    "lund": (55.70, 13.19)
    # Add more cities as needed
}
DEFAULT_LOCATION = "uppsala"
DEFAULT_COORDS = LOCATION_COORDS[DEFAULT_LOCATION]

# --- Function to get coordinates (similar to Lambda) ---


def get_coordinates(location_name):
    """Gets latitude and longitude for a given location name."""
    if not location_name:
        logger.warning("No location provided, using default.")
        return DEFAULT_COORDS
    location_name_lower = location_name.lower()
    coords = LOCATION_COORDS.get(location_name_lower)
    if coords:
        logger.info(f"Found coordinates for '{location_name}': {coords}")
        return coords
    else:
        logger.warning(
            f"Coordinates not found for '{location_name}'. Using default '{DEFAULT_LOCATION}'.")
        return DEFAULT_COORDS

# --- NEW Function: Get Weather for UI ---


def get_weather_for_location(location_name):
    """Fetches weather from SMHI for the UI based on location name."""
    lat, lon = get_coordinates(location_name)
    smhi_url = f"https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/{lon:.2f}/lat/{lat:.2f}/data.json"
    logger.info(f"UI fetching weather from: {smhi_url}")
    weather_result = {"temp": "N/A", "humidity": "N/A",
                      "precip": "N/A", "error": None}
    try:
        # Identify UI
        headers = {'User-Agent': 'PotatoHealthAppUI/1.0 (YourContactInfoHere)'}
        response = requests.get(smhi_url, headers=headers, timeout=10)
        response.raise_for_status()
        weather_data = response.json()

        if not weather_data.get("timeSeries"):
            logger.error("SMHI API response missing 'timeSeries'.")
            weather_result["error"] = "SMHI API data format error."
            return weather_result

        first_forecast = weather_data["timeSeries"][0]
        parameters = {param["name"]: param["values"][0]
                      for param in first_forecast["parameters"]}

        weather_result["temp"] = parameters.get("t", "N/A")
        weather_result["humidity"] = parameters.get("r", "N/A")
        weather_result["precip"] = parameters.get("pmean", "N/A")

        logger.info(
            f"UI Weather Fetched for {location_name}: {weather_result}")
        return weather_result

    except requests.exceptions.RequestException as e:
        logger.error(f"UI Error fetching weather data from SMHI: {e}")
        weather_result["error"] = "Could not reach weather service."
        return weather_result
    except json.JSONDecodeError as e:
        logger.error(f"UI Error decoding SMHI JSON response: {e}")
        weather_result["error"] = "Error reading weather data."
        return weather_result
    except Exception as e:
        logger.error(
            f"UI An unexpected error occurred fetching weather: {e}", exc_info=True)
        weather_result["error"] = "Unexpected weather error."
        return weather_result

# --- Existing upload_to_s3 function ---


def upload_to_s3(file_obj, bucket_name, object_name=None):
    """ Uploads a file-like object to an S3 bucket. (Keep existing implementation) """
    # ... (keep the code from the previous version) ...
    if object_name is None:
        object_name = getattr(file_obj, 'filename', None)
        if not object_name:
            object_name = f"uploads/{uuid.uuid4()}"
            logger.info("No filename provided, generated UUID name.")
        else:
            object_name = os.path.basename(object_name).replace(
                "..", "_").replace("/", "_")
            # Prefix to avoid collisions
            object_name = f"uploads/{uuid.uuid4()}-{object_name}"

    logger.info(f"Attempting to upload to s3://{bucket_name}/{object_name}")
    try:
        s3_client.upload_fileobj(file_obj, bucket_name, object_name)
        logger.info(
            f"Successfully uploaded to s3://{bucket_name}/{object_name}")
        # Return the final object name (key) used in S3
        return object_name
    except ClientError as e:
        logger.error(f"S3 Upload Error: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during S3 upload: {e}")
        return None


# --- Updated post_text_to_lex to accept session attributes ---
def post_text_to_lex(bot_id, alias_id, session_id, input_text, session_attributes=None):
    """
    Sends text to the Lex bot and returns the bot's response messages.
    Includes optional session attributes.
    """
    if session_attributes is None:
        session_attributes = {}

    logger.info(
        f"Sending to Lex (Session: {session_id}, Attrs: {session_attributes}): {input_text}")
    try:
        response = lex_client.recognize_text(
            botId=bot_id,
            botAliasId=alias_id,
            localeId='en_US',  # Or the locale configured for your bot
            sessionId=session_id,
            text=input_text,
            # Pass attributes here
            sessionState={'sessionAttributes': session_attributes}
        )
        logger.info(f"Lex response: {response}")

        messages = []
        if response and 'messages' in response:
            for msg in response['messages']:
                if msg.get('contentType') == 'PlainText':
                    messages.append(msg['content'])

        if not messages:
            messages.append("Sorry, I didn't get a response. Try again.")

        return messages

    # ... (keep existing error handling from previous version) ...
    except ClientError as e:
        logger.error(f"Lex API Error: {e}")
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == 'AccessDeniedException':
            return ["Error: Access denied when calling Lex. Check UI credentials."]
        elif error_code == 'ResourceNotFoundException':
            return ["Error: Lex bot or alias not found. Check configuration."]
        else:
            return [f"An error occurred communicating with the bot ({error_code})."]
    except Exception as e:
        logger.error(f"An unexpected error occurred calling Lex: {e}")
        return ["An unexpected error occurred."]
