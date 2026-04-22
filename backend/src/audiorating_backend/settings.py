import os
from dotenv import load_dotenv
import json
from .parsers.settings_parser import parse_admin_credentials

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
        return self.admin_usernames[0]

    @property
    def admin_password(self):
        return self.admin_passwords[0]

    @property
    def admin_usernames(self):
        return [username for username, _ in self.admin_credentials]

    @property
    def admin_passwords(self):
        return [password for _, password in self.admin_credentials]

    @property
    def admin_credentials(self):
        return parse_admin_credentials(
            os.getenv("AR_API_ADMIN_USERNAME"),
            os.getenv("AR_API_ADMIN_PASSWORD"),
        )

    @property
    def admin_audit_log_file(self):
        """Path to persistent admin action audit log file."""
        return os.getenv("AR_ADMIN_AUDIT_LOG_FILE", "admin_actions.log")

    @property
    def admin_audit_log_max_bytes(self):
        """Maximum size (bytes) before rotating the admin audit log file."""
        value = os.getenv("AR_ADMIN_AUDIT_LOG_MAX_BYTES", str(5 * 1024 * 1024))
        return int(value)

    @property
    def admin_audit_log_backup_count(self):
        """Number of rotated admin audit log backup files to keep."""
        value = os.getenv("AR_ADMIN_AUDIT_LOG_BACKUP_COUNT", "10")
        return int(value)

settings = ARBackendSettings()

