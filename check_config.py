import os
from dotenv import load_dotenv

load_dotenv()

print(\"🔍 Checking M-Pesa Configuration:\")
print(f\"MPESA_CONSUMER_KEY: {os.getenv('MPESA_CONSUMER_KEY')}\")
print(f\"MPESA_CONSUMER_SECRET: {os.getenv('MPESA_CONSUMER_SECRET')}\")
print(f\"MPESA_SHORTCODE: {os.getenv('MPESA_SHORTCODE')}\")
print(f\"MPESA_PASSKEY: {os.getenv('MPESA_PASSKEY')}\")
print(f\"MPESA_CALLBACK_URL: {os.getenv('MPESA_CALLBACK_URL')}\")
print(f\"MPESA_ENVIRONMENT: {os.getenv('MPESA_ENVIRONMENT')}\")
