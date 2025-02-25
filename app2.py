import os
import json
from datetime import datetime, timezone, timedelta
from google.cloud import storage
import google.generativeai as genai
from flask import Flask, request, redirect, jsonify, abort
import logging
from google.auth import default
from google.auth.transport import requests as google_requests

# Set up logging
logging.basicConfig(level=logging.INFO)

# Configuration
BUCKET_NAME = "uploaded_images_bucket"
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set.")

# Use default credentials from Cloud Run metadata server with refresh
auth_request = google_requests.Request()
scopes = ["https://www.googleapis.com/auth/cloud-platform"]
creds, _ = default(scopes=scopes)
creds.refresh(auth_request)
storage_client = storage.Client(credentials=creds)

# Configure Gemini AI Client with API Key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__)

def generate_signed_url(blob, expiration_minutes=15):
    try:
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.now(tz=timezone.utc) + timedelta(minutes=expiration_minutes),
            method="GET",
            service_account_email="90203791699-compute@developer.gserviceaccount.com",
            access_token=creds.token
        )
        return signed_url
    except Exception as e:
        logging.error(f"Error generating signed URL for {blob.name}: {e}")
        return None

def generate_gemini_caption(image_file):
    try:
        image_bytes = image_file.read()
        image_data = {"mime_type": "image/jpeg", "data": image_bytes}
        response = model.generate_content(["Provide a short description of this image in one sentence:", image_data])
        caption = response.text.strip() or "No caption generated."
        title = " ".join(caption.split()[:5])
        return {"title": title, "description": caption}
    except Exception as e:
        logging.error(f"Gemini AI Error: {e}")
        return {"title": "Error", "description": "Failed to generate caption."}

@app.route('/healthz')
def healthz():
    return jsonify(status='healthy'), 200

@app.route('/upload', methods=["POST"])
def upload():
    if 'form_file' not in request.files:
        logging.error("No file part in the request")
        return "No file part", 400
    file = request.files.get('form_file')
    if file.filename == '':
        logging.error("No file selected")
        return "No file selected", 400
    if file and file.filename.lower().endswith(('.jpeg', '.jpg')):
        file_name = file.filename
        logging.info(f"Received: {file_name}")
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_file(file)
        logging.info(f"Uploaded {file_name} to {BUCKET_NAME}.")
        file.seek(0)  # Reset file pointer for Gemini
        caption_data = generate_gemini_caption(file)
        json_blob = bucket.blob(file_name.rsplit('.', 1)[0] + '.json')
        json_blob.upload_from_string(json.dumps(caption_data, indent=4), content_type='application/json')
        logging.info(f"Caption saved for {file_name}.")
        return redirect("/files")
    logging.error(f"Invalid file type for {file.filename}")
    return "Invalid file type. Only .jpeg and .jpg allowed.", 400

@app.route('/files')
def list_files():
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())
    logging.info(f"Found {len(blobs)} files in bucket.")
    html = "<h1>Uploaded Files with Captions</h1><ul>"
    for blob in blobs:
        if blob.name.lower().endswith(('.jpeg', '.jpg')):
            signed_url = generate_signed_url(blob)
            if not signed_url:
                logging.error(f"Skipping {blob.name} due to signed URL failure.")
                html += f'<li>Error loading image "{blob.name}"</li>'
                continue
            json_blob = bucket.blob(blob.name.rsplit('.', 1)[0] + '.json')
            caption = "No caption available"
            if json_blob.exists():
                data = json.loads(json_blob.download_as_text())
                caption = f"<strong>Title:</strong> {data.get('title')}<br><strong>Description:</strong> {data.get('description')}"
            html += f'<li><img src="{signed_url}" alt="{blob.name}" style="max-width:200px;"><br>{caption}</li>'
    html += "</ul><br><a href='/'>Go Back</a>"
    return html

@app.route('/')
def index():
    return """
    <h1>Image Upload with Gemini AI Captions</h1>
    <form method="post" enctype="multipart/form-data" action="/upload">
        <input type="file" name="form_file" accept="image/jpeg" required>
        <button type="submit">Upload and Get Caption</button>
    </form>
    <br>
    <a href="/files">View Uploaded Images with Captions</a>
    """

if __name__ == '__main__':
    logging.info("Starting Flask app...")
    app.run(host='0.0.0.0', port=8080, debug=True)