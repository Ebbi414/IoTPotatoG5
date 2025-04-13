'''
Run pip install streamlit boto3 python-dotenv requests Pillow
To test UI with AWS connection replace aws_utils_stub with aws_utils
# Run the app with: streamlit run 5_streamlit_app.py
'''

import streamlit as st
import os
import uuid
import datetime
from PIL import Image
import aws_utils_stub  # Your helper module

# --- Page Configuration ---
st.set_page_config(page_title="Potato Health Monitor", layout="wide")
st.title("🥔 Monitoring Potato Plant Health")

# --- Load Configuration from Environment Variables ---
try:
    S3_BUCKET = os.environ['S3_BUCKET_NAME']
    LEX_BOT_ID = os.environ['LEX_BOT_ID']
    LEX_BOT_ALIAS_ID = os.environ['LEX_BOT_ALIAS_ID']
    # Define available locations based on aws_utils dictionary keys
    AVAILABLE_LOCATIONS = list(aws_utils_stub.LOCATION_COORDS.keys())
except KeyError as e:
    st.error(
        f"Missing environment variable: {e}. Please set it in .env or system environment.")
    st.stop()
except AttributeError:
    st.error("LOCATION_COORDS not found in aws_utils.py. Ensure it's defined.")
    st.stop()


# --- Session State Initialization ---
if "lex_session_id" not in st.session_state:
    st.session_state.lex_session_id = f"st-session-{uuid.uuid4()}"
    st.info(f"New session started: {st.session_state.lex_session_id}")

if "messages" not in st.session_state:
    # Store chat history {role: "user/assistant", content: "message"}
    st.session_state.messages = []

if "current_location" not in st.session_state:
    # Set default location from aws_utils
    st.session_state.current_location = aws_utils_stub.DEFAULT_LOCATION

if "current_weather" not in st.session_state:
    st.session_state.current_weather = {
        "temp": "N/A", "humidity": "N/A", "precip": "N/A", "error": None}

if "uploaded_image" not in st.session_state:  # Store Image object for display
    st.session_state.uploaded_image = None
if "uploaded_image_key" not in st.session_state:  # Store S3 key/filename
    st.session_state.uploaded_image_key = None


# --- Function to Update Weather ---
def update_weather(location):
    st.session_state.current_weather = aws_utils_stub.get_weather_for_location(
        location)


# --- Header Area ---
header_cols = st.columns([3, 1])
with header_cols[0]:
    st.markdown("##")  # Spacer
    st.markdown(f"**Date:** {datetime.date.today().strftime('%Y-%m-%d')}")
with header_cols[1]:
    # Location Selector
    selected_location = st.selectbox(
        "Location",
        options=AVAILABLE_LOCATIONS,
        index=AVAILABLE_LOCATIONS.index(
            st.session_state.current_location)  # Set default index
    )
    # Update weather if location changes
    if selected_location != st.session_state.current_location:
        st.session_state.current_location = selected_location
        with st.spinner(f"Fetching weather for {selected_location}..."):
            update_weather(selected_location)
        st.rerun()  # Rerun script to update weather display immediately

# --- Main Layout Area ---
col1, col2 = st.columns([2, 1])  # Chat/Input | Weather/Upload/Image

# Column 1: Chat Interface
with col1:
    st.subheader("Chat Assistant")
    # Chat History Box
    chat_container = st.container(height=400, border=True)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Chat Input Box
    if prompt := st.chat_input(f"Ask about your plant in {st.session_state.current_location}..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Prepare session attributes to send location context
        lex_attributes = {"currentLocation": st.session_state.current_location}

        # Get assistant response from Lex
        with st.spinner("Assistant is thinking..."):
            bot_responses = aws_utils_stub.post_text_to_lex(
                bot_id=LEX_BOT_ID,
                alias_id=LEX_BOT_ALIAS_ID,
                session_id=st.session_state.lex_session_id,
                input_text=prompt,
                session_attributes=lex_attributes  # Pass selected location
            )

        # Combine and add bot response(s) to history
        full_response = "\n\n".join(bot_responses)
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response})

        # Rerun to display the new messages immediately
        st.rerun()


# Column 2: Weather, Upload, Image Display
with col2:
    # Weather Status Box
    st.subheader("Weather Status")
    with st.container(border=True):
        weather = st.session_state.current_weather
        if weather["error"]:
            st.error(weather["error"])
        st.markdown(f"**Temperature (°C):** {weather['temp']}")
        st.markdown(f"**Relative Humidity (%):** {weather['humidity']}")
        st.markdown(f"**Precipitation (mm/h):** {weather['precip']}")

    st.divider()

    # Image Upload Button/Area
    st.subheader("Upload Image")
    uploaded_file = st.file_uploader(
        "Upload your image here",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed"  # Hide the default label
    )

    # Image Rendering Area
    st.subheader("Uploaded Image")
    image_placeholder = st.container(height=250, border=True)

    # Handle Upload and Display
    if uploaded_file is not None:
        # Process and display the new upload
        try:
            img_bytes = uploaded_file.getvalue()  # Read bytes for potential reuse
            image = Image.open(uploaded_file)
            with image_placeholder:
                # *** UPDATED LINE BELOW ***
                st.image(
                    image, caption=f"Uploaded: {uploaded_file.name}", use_container_width=True)

            # Perform upload to S3
            with st.spinner("Uploading to S3..."):
                # Use the bytes we read earlier
                from io import BytesIO
                s3_object_name = aws_utils_stub.upload_to_s3(
                    BytesIO(img_bytes), S3_BUCKET, object_name=uploaded_file.name)

            if s3_object_name:
                st.success(f"Upload successful!")
                base_filename = os.path.basename(s3_object_name)
                st.info(f"Filename for chat: `{base_filename}`")
                # Store key info in session state ONLY after successful upload
                st.session_state.uploaded_image = image  # Keep image obj for redisplay
                st.session_state.uploaded_image_key = base_filename
            else:
                st.error("⚠️ S3 Upload Failed.")
                st.session_state.uploaded_image = None  # Clear on failure
                st.session_state.uploaded_image_key = None

        except Exception as e:
            st.error(f"Error processing/uploading image: {e}")
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_key = None

    elif st.session_state.uploaded_image:
        # If no new file uploaded, but an image exists in session state, display it
        with image_placeholder:
            # *** UPDATED LINE BELOW ***
            st.image(st.session_state.uploaded_image,
                     caption=f"Current: {st.session_state.uploaded_image_key}", use_container_width=True)


# --- Initial Weather Fetch on Load ---
if "current_weather" not in st.session_state or st.session_state.current_weather["temp"] == "N/A":
    with st.spinner(f"Fetching initial weather for {st.session_state.current_location}..."):
        update_weather(st.session_state.current_location)
    st.rerun()  # Rerun to display fetched weather
