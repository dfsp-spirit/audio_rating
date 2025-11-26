import os
from dotenv import load_dotenv
import json

load_dotenv()   # load .env file in working directory if it exists



class ARBackendSettings:
    def __init__(self):
        # Backend-specific settings
        self.debug = True if os.getenv("AR_DEBUG", "false").lower() == "true" else False
        self.studies_config_path: str = os.getenv("AR_STUDIES_CONFIG_PATH", "studies_config.json")


    # Environment-dependent settings as properties
    @property
    def database_url(self):
        db_url = os.getenv("AR_DATABASE_URL")
        if not db_url:
            raise ValueError("AR_DATABASE_URL environment variable is not set.")
        return db_url

    @property
    def allowed_origins(self):
        origins = json.loads(os.getenv("AR_ALLOWED_ORIGINS", "[]"))
        if not origins:
            raise ValueError("AR_ALLOWED_ORIGINS environment variable is not set. Please set a JSON array of allowed origins.")
        return origins

    @property
    def admin_username(self):
        username = os.getenv("AR_API_ADMIN_USERNAME")
        if not username:
            raise ValueError("AR_API_ADMIN_USERNAME environment variable is not set.")
        return username

    @property
    def admin_password(self):
        password = os.getenv("AR_API_ADMIN_PASSWORD")
        if not password:
            raise ValueError("AR_API_ADMIN_PASSWORD environment variable is not set.")
        return password

settings = ARBackendSettings()

