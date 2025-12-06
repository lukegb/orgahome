import json
import logging
import os
from typing import Any, TypedDict

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class UFFDUser(TypedDict):
    id: int
    loginname: str
    email: str
    displayname: str
    groups: list[str]


class UFFDClient:
    def __init__(self, api_url: str, username: str, password: str) -> None:
        self.api_url: str = api_url.rstrip("/")
        self.auth: HTTPBasicAuth = HTTPBasicAuth(username, password)

    def get_users(self) -> list[UFFDUser]:
        try:
            response = requests.get(f"{self.api_url}/getusers", auth=self.auth)
            response.raise_for_status()
            data = response.json()
            # In a real app we might validate 'data' matches the schema,
            # here we cast it as we trust the API or let it fail later if malformed.
            return data
        except requests.RequestException as e:
            logger.error(f"Error fetching users from UFFD: {e}")
            return []


MattermostUserProps = TypedDict(
    "MattermostUserProps",
    {
        "idp/userid": str,
        "customStatus": str,
    },
    total=False,
)


class MattermostUser(TypedDict):
    id: str
    username: str
    first_name: str
    last_name: str
    email: str
    position: str
    props: MattermostUserProps


class MattermostClient:
    def __init__(self, api_url: str, token: str) -> None:
        self.api_url: str = api_url.rstrip("/")
        self.headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

    def get_all_active_users(self) -> list[MattermostUser]:
        users: list[MattermostUser] = []
        page = 0
        per_page = 200
        while True:
            try:
                response = requests.get(
                    f"{self.api_url}/users",
                    headers=self.headers,
                    params={"page": page, "per_page": per_page, "active": "true"},
                )
                response.raise_for_status()
                batch = response.json()
                if not batch:
                    break
                users.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1
            except requests.RequestException as e:
                logger.error(f"Error fetching users page {page}: {e}")
                break
        return users

    def get_user_image_url(self, user_id: str) -> str:
        return f"{self.api_url}/users/{user_id}/image"

    def get_emoji_id_by_name(self, emoji_name: str) -> str | None:
        try:
            response = requests.get(f"{self.api_url}/emoji/name/{emoji_name}", headers=self.headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("id")
        except requests.RequestException as e:
            logger.error(f"Error fetching emoji {emoji_name}: {e}")
            return None

    def get_custom_emoji_image_url(self, emoji_id: str) -> str:
        return f"{self.api_url}/emoji/{emoji_id}/image"

    def get_system_emoji_map(self) -> dict[str, str]:
        if hasattr(self, "_system_emoji_map"):
            return self._system_emoji_map

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            emoji_path = os.path.join(base_dir, "emoji.json")
            with open(emoji_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Map short_name/underscores -> unicode codepoint
            mapping = {}
            for item in data:
                unified = item.get("unified")
                if unified:
                    for name in item.get("short_names", []):
                        mapping[name] = unified
                    if "short_name" in item:
                        mapping[item["short_name"]] = unified

            self._system_emoji_map = mapping
            return mapping
        except Exception as e:
            logger.error(f"Failed to fetch system emoji map: {e}")
            return {}
