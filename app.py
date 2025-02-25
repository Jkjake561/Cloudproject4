import os
import json
from datetime import datetime, timezone, timedelta
from google.cloud import storage
import google.generativeai as genai
from flask import Flask, request, redirect, jsonify, abort, Response
import logging
from google.auth import default
from google.auth.transport import requests as google_requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# ----- CONFIGURATION -----
BUCKET_NAME = "uploaded_images_bucket"
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set.")

auth_request = google_requests.Request()
scopes = ["https://www.googleapis.com/auth/cloud-platform"]
creds, _ = default(scopes=scopes)
creds.refresh(auth_request)
storage_client = storage.Client(credentials=creds)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ----- HELPER FUNCTIONS -----
def generate_signed_url(blob, expiration_minutes=15):
    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=datetime.now(tz=timezone.utc) + timedelta(minutes=expiration_minutes),
            method="GET",
            service_account_email="90203791699-compute@developer.gserviceaccount.com",
            access_token=creds.token
        )
    except Exception as e:
        logging.error(f"Error generating signed URL for {blob.name}: {e}")
        return None

def generate_gemini_caption(image_file):
    try:
        image_bytes = image_file.read()
        image_data = {"mime_type": "image/jpeg", "data": image_bytes}
        response = model.generate_content(
            ["Provide a short description of this image in one sentence:", image_data]
        )
        caption = response.text.strip() or "No caption generated."
        title = " ".join(caption.split()[:5])
        return {"title": title, "description": caption}
    except Exception as e:
        logging.error(f"Gemini AI Error: {e}")
        return {"title": "Error", "description": "Failed to generate caption."}

@app.route("/healthz")
def healthz():
    return jsonify(status="healthy"), 200

@app.route("/images/<filename>")
def serve_image(filename):
    """Serve the raw image data (optional approach)."""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    try:
        image_data = blob.download_as_bytes()
        return Response(image_data, mimetype="image/jpeg")
    except Exception as e:
        logging.error(f"Error serving image {filename}: {e}")
        abort(404)

@app.route("/upload", methods=["POST"])
def upload():
    if "form_file" not in request.files:
        logging.error("No file part in the request")
        return "No file part", 400

    file = request.files["form_file"]
    if file.filename == "":
        logging.error("No file selected")
        return "No file selected", 400

    if file and file.filename.lower().endswith((".jpeg", ".jpg")):
        file_name = file.filename
        logging.info(f"Received: {file_name}")

        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_file(file)
        logging.info(f"Uploaded {file_name} to {BUCKET_NAME}.")

        # Generate caption
        file.seek(0)  # Reset pointer for caption
        caption_data = generate_gemini_caption(file)
        json_blob = bucket.blob(file_name.rsplit(".", 1)[0] + ".json")
        json_blob.upload_from_string(json.dumps(caption_data, indent=4), content_type="application/json")
        logging.info(f"Caption saved for {file_name}.")
        # Redirect back to the homepage to show updated images on the same page
        return redirect("/")
    else:
        logging.error(f"Invalid file type for {file.filename}")
        return "Invalid file type. Only .jpeg and .jpg allowed.", 400

@app.route("/")
def index():
    """
    Displays the upload form at the top and the list of images (with captions) below on the same page.
    """
    # HTML header + Upload form
    html = """
    <h1>Image Upload with Gemini AI Captions</h1>
    <form method="post" enctype="multipart/form-data" action="/upload">
        <input type="file" name="form_file" accept="image/jpeg" required>
        <button type="submit">Upload and Get Caption</button>
    </form>
    <br>
    <h2>Uploaded Images with Captions</h2>
    <ul>
    """

    # List images + captions
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())
    for blob in blobs:
        if blob.name.lower().endswith((".jpeg", ".jpg")):
            # Use direct serving approach or a signed URL
            # Option A: direct serving (if you made a serve_image route):
            image_url = f"/images/{blob.name}"

            # Option B: signed URL
            #image_url = generate_signed_url(blob) or "#"

            # Get caption from JSON
            json_blob = bucket.blob(blob.name.rsplit(".", 1)[0] + ".json")
            caption = "No caption available"
            if json_blob.exists():
                data = json.loads(json_blob.download_as_text())
                caption = (
                    f"<strong>Title:</strong> {data.get('title')}<br>"
                    f"<strong>Description:</strong> {data.get('description')}"
                )
            html += f'<li><img src="{image_url}" alt="{blob.name}" style="max-width:200px;"><br>{caption}</li>'

    html += "</ul>"
    return html

if __name__ == "__main__":
    logging.info("Starting Flask app...")
    app.run(host="0.0.0.0", port=8080, debug=True)
