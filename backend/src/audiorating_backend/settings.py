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
        """Allowed origins for CORS, as a list of strings. Expects a JSON array in the environment variable."""
        origins = json.loads(os.getenv("AR_ALLOWED_ORIGINS", "[]"))
        if not origins:
            raise ValueError("AR_ALLOWED_ORIGINS environment variable is not set. Please set a JSON array of allowed origins.")
        return origins

    @property
    def frontend_url(self):
        """Frontend URL, used only for constructing invitation links in admin interface. Expects a string like 'https://yourserver.de/path_to_audiorating/' including terminating slash where we can append 'study.html...' to get a valid path to study.html page."""
        url = os.getenv("AR_FRONTEND_URL")
        if not url:
            raise ValueError("AR_FRONTEND_URL environment variable is not set.")
        if not url.endswith("/"):
            url += "/"
        return url

    @property
    def rootpath(self):
        """The FastAPI root path, used for mounting the backend API under a subpath, e.g., if you nginx exposes the backend at https://yourserver.com/ar_backend, this is '/ar_backend', without a terminating slash. Defaults to '' if not set."""
        url = os.getenv("AR_ROOTPATH", "")
        if url.endswith("/"):
            url = url[:-1]  # Remove trailing slash if present
        return url

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

