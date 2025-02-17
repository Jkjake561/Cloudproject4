import time
from google.cloud import storage
from flask import Flask, request, redirect

app = Flask(__name__)
BUCKET_NAME = "project1test"

# Initialize the Cloud Storage client
storage_client = storage.Client()

@app.route('/upload', methods=["POST"])
def upload():
    file = request.files['form_file']
    file_name = file.filename

    # Upload the file to GCS
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)
    blob.upload_from_file(file)

    return redirect("/")


@app.route('/files')
def list_files():
    blobs = storage_client.list_blobs(BUCKET_NAME)
    jpegs = [blob.name for blob in blobs if blob.name.lower().endswith((".jpeg", ".jpg"))]

    files_html = "<h1>Uploaded Files</h1><ul>"
    for jpeg in jpegs:
        url = f"https://storage.googleapis.com/{BUCKET_NAME}/{jpeg}"
        files_html += f'<li><img src="{url}" alt="{jpeg}" style="max-width: 200px;"><br>'
        files_html += f'<a href="{url}" target="_blank">{jpeg}</a></li>'
    files_html += "</ul>"

    files_html += '<br><a href="/">Go Back</a>'
    return files_html


@app.route('/files/<filename>')
def get_file(filename):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)

    # Generate and return the public URL for the file
    return blob.public_url



@app.route('/')
def index():
    return """
    <h1>Welcome to the Flask App!</h1>
    <p>Use the form below to upload images (JPEG only):</p>
    <form method="post" enctype="multipart/form-data" action="/upload">
        <div>
            <label for="file">Choose file to upload:</label>
            <input type="file" id="file" name="form_file" accept="image/jpeg"/>
        </div>
        <div>
            <button type="submit">Upload</button>
        </div>
    </form>
    <br>
    <p>View uploaded files: <a href="/files">List Files</a></p>
    """



if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)
