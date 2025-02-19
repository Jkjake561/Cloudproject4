import os
import json
import time
from google.cloud import storage
from google import generativeai as genai
from flask import Flask, request, redirect

# Configuration
BUCKET_NAME = "uploaded_images_bucket"  # Cloud Storage bucket name
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set.")

# Configure Gemini AI Client with API Key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Initialize Google Cloud Storage client
storage_client = storage.Client()
app = Flask(__name__)

# **Upload Route:** Handles image uploads and caption generation
@app.route('/upload', methods=["POST"])
def upload():
    file = request.files.get('form_file')
    if not file or not file.filename:
        return "Invalid file.", 400

    file_name = file.filename
    print(f"📤 Received: {file_name}")

    # Upload image to Cloud Storage
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)
    blob.upload_from_file(file)
    print(f"✅ Uploaded {file_name} to {BUCKET_NAME}.")

    # Generate caption using Gemini AI
    file.seek(0)  # Reset file pointer before passing to Gemini
    caption_data = generate_gemini_caption(file)
    json_blob = bucket.blob(file_name.rsplit('.', 1)[0] + '.json')
    json_blob.upload_from_string(json.dumps(caption_data, indent=4), content_type='application/json')
    print(f"✅ Caption saved for {file_name}.")

    return redirect("/files")

# **Caption Generator Function:** Calls Gemini AI to describe the image
def generate_gemini_caption(image_file):
    try:
        # Convert the image file to bytes
        image_bytes = image_file.read()
        print(f"📄 Image size: {len(image_bytes)} bytes")

        # Format the image data for Gemini
        image_data = {
            "mime_type": "image/jpeg",  # Specify the MIME type
            "data": image_bytes  # Pass the image bytes
        }

        # Pass the image data and a more specific prompt to Gemini
        response = model.generate_content(
            ["Provide a short and concise description of this image in one sentence:", image_data]
        )
        caption = response.text.strip() if response.text else "No caption generated."
        print(f"📝 Gemini Response: {caption}")

        # Generate a shorter title (first 5 words of the caption)
        title = " ".join(caption.split()[:5])  # Take the first 5 words
        return {"title": title, "description": caption}
    except Exception as e:
        print(f"❌ Gemini AI Error: {str(e)}")  # Log the full error message
        return {"title": "Error", "description": "Failed to generate caption."}

# **Display Files Route:** Shows uploaded images and their captions
@app.route('/files')
def list_files():
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())
    print(f"📂 Found {len(blobs)} files in bucket.")

    html = "<h1>Uploaded Files with Captions</h1><ul>"
    for blob in blobs:
        if blob.name.lower().endswith(('.jpeg', '.jpg')):
            image_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob.name}"
            json_blob = bucket.blob(blob.name.rsplit('.', 1)[0] + '.json')
            caption = "No caption available"
            if json_blob.exists():
                data = json.loads(json_blob.download_as_text())
                caption = f"<strong>Title:</strong> {data.get('title')}<br><strong>Description:</strong> {data.get('description')}"
            html += f'<li><img src="{image_url}" alt="{blob.name}" style="max-width:200px;"><br>{caption}</li>'
    html += "</ul><br><a href='/'>Go Back</a>"
    return html

# **Homepage:** Displays upload form
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

# **Run Flask App Locally**
if __name__ == '__main__':
    print("🚀 Starting Flask app with Gemini AI integration...")
    app.run(host='0.0.0.0', port=8080, debug=True)