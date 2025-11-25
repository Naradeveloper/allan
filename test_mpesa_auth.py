import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

def test_authentication():
    \"\"\"Test if we can get M-Pesa access token\"\"\"
    consumer_key = os.getenv('MPESA_CONSUMER_KEY')
    consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')
    
    print(f\"Consumer Key: {consumer_key}\")
    print(f\"Consumer Secret: {consumer_secret}\")
    
    if not consumer_key or not consumer_secret:
        print(\"❌ Missing M-Pesa credentials in .env file\")
        return False
    
    url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    auth_string = f\"{consumer_key}:{consumer_secret}\"
    encoded_auth = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_auth}'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f\"Status Code: {response.status_code}\")
        print(f\"Response: {response.text}\")
        
        if response.status_code == 200:
            data = response.json()
            print(f\"✅ Access Token: {data.get('access_token')}\")
            return True
        else:
            print(\"❌ Failed to get access token\")
            return False
            
    except Exception as e:
        print(f\"💥 Error: {e}\")
        return False

if __name__ == \"__main__\":
    test_authentication()
