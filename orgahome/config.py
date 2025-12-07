import os

import dotenv

dotenv.load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_key")

    # OIDC Configuration
    OIDC_CLIENT_SECRETS = os.environ.get("OIDC_CLIENT_SECRETS", "client_secrets.json")
    OIDC_SCOPES = "openid email profile groups"

    # UFFD API Configuration
    UFFD_API_URL = os.environ.get("UFFD_API_URL", "https://identity.emfcamp.org/api/v1")
    UFFD_USER = os.environ.get("UFFD_USER")
    UFFD_PASSWORD = os.environ.get("UFFD_PASSWORD")

    # Mattermost API Configuration
    MATTERMOST_API_URL = os.environ.get("MATTERMOST_API_URL", "https://chat.orga.emfcamp.org/api/v4")
    MATTERMOST_TOKEN = os.environ.get("MATTERMOST_TOKEN")
