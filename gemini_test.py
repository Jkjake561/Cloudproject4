import google.generativeai as genai
import os

# Use API Key from Google AI Studio
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set.")

genai.configure(api_key=API_KEY)

# Initialize the Gemini model
model = genai.GenerativeModel("gemini-pro")

# Send a test prompt using the correct method for the Gemini SDK
try:
    response = model.generate_content(["Describe artificial intelligence in simple terms."])
    if response and hasattr(response, 'text'):
        print("🔹 Gemini AI Response:")
        print(response.text)
    else:
        print("No response received.")
except Exception as e:
    print(f"❌ API Error: {e}")
