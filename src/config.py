import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    CHROME_DEBUG_PORT = os.getenv('CHROME_DEBUG_PORT', '9222')
    CHROME_PROFILE_PATH = os.getenv('CHROME_PROFILE_PATH')
    # Add other config variables