import asyncio
import datetime
import json
import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any

import requests
from flask import (
    Flask,
    Response,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_oidc import OpenIDConnect  # type: ignore
from werkzeug import Response as WerkzeugResponse

from orgahome import gif
from orgahome.config import Config
from orgahome.services import (
    MattermostClient,
    MattermostUser,
    UFFDClient,
    UFFDUser,
)

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config.from_object(Config)

oidc = OpenIDConnect(app)

uffd_client = UFFDClient(app.config["UFFD_API_URL"], app.config["UFFD_USER"], app.config["UFFD_PASSWORD"])

mm_client = MattermostClient(app.config["MATTERMOST_API_URL"], app.config["MATTERMOST_TOKEN"])


def require_login(func):
    """Wraps oidc.require_login in a Flask-async compatible fashion."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        return oidc.require_login(current_app.ensure_sync(func))(*args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class TeamMembership:
    team_name: str
    is_lead: bool


@dataclass(frozen=True)
class EnhancedUser:
    uffd: UFFDUser
    mm: MattermostUser

    @property
    def display_name(self) -> str:
        first = self.mm.get("first_name")
        last = self.mm.get("last_name")
        if first and last:
            return f"{first} {last}"
        if first:
            return first
        if last:
            return last
        return self.uffd.get("displayname") or self.uffd.get("loginname")

    @property
    def image_url(self) -> str:
        return url_for("mm_avatar_proxy", user_id=self.mm["id"])

    @property
    def username(self) -> str:
        return self.uffd.get("loginname")

    @property
    def email(self) -> str:
        return self.uffd.get("email")

    @property
    def groups(self) -> list[str]:
        return self.uffd.get("groups", [])

    @property
    def teams(self) -> list[TeamMembership]:
        teams = []
        user_groups = set(self.groups)
        for group in self.groups:
            if group.startswith("team_"):
                team_name = group[5:]
                is_lead = f"moderation_{team_name}" in user_groups
                teams.append(TeamMembership(team_name=team_name, is_lead=is_lead))
        teams.sort(key=lambda x: x.team_name)
        return teams

    @property
    def position(self) -> str | None:
        return self.mm.get("position")

    @property
    def custom_status(self) -> dict[str, Any] | None:
        props = self.mm.get("props", {})
        cs_str = props.get("customStatus")
        if not cs_str:
            return None

        try:
            cs = json.loads(cs_str)
            expires_at_str = cs.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.datetime.fromisoformat(expires_at_str)
                    if expires_at.year > 2000 and expires_at < datetime.datetime.now(datetime.timezone.utc):
                        return None
                except ValueError:
                    return None
            return cs
        except json.JSONDecodeError:
            return None

    @property
    def custom_status_emoji_url(self) -> str | None:
        cs = self.custom_status
        if not cs or not cs.get("emoji"):
            return None

        emoji_name = cs["emoji"]

        system_map = mm_client.get_system_emoji_map()
        if emoji_name in system_map:
            unified = system_map[emoji_name]
            return f"https://chat.orga.emfcamp.org/static/emoji/{unified.lower()}.png"

        return url_for("mm_emoji_proxy", emoji_name=emoji_name)


async def fetch_directory_data() -> dict[str, EnhancedUser]:
    loop = asyncio.get_running_loop()

    # Run sync calls in threads
    uffd_task = loop.run_in_executor(None, uffd_client.get_users)
    mm_task = loop.run_in_executor(None, mm_client.get_all_active_users)

    uffd_users, mm_users = await asyncio.gather(uffd_task, mm_task)

    mm_map: dict[str, MattermostUser] = {}
    for mm_user in mm_users:
        props = mm_user.get("props", {})
        idp_id = props.get("idp/userid")
        if idp_id:
            mm_map[idp_id] = mm_user

    user_map: dict[str, EnhancedUser] = {}
    for uffd_user in uffd_users:
        uffd_id_str = str(uffd_user.get("id"))
        mm_user = mm_map.get(uffd_id_str)
        if not mm_user:
            continue

        user = EnhancedUser(uffd=uffd_user, mm=mm_user)
        user_map[uffd_user["loginname"]] = user

    return user_map


@app.route("/")
@app.route("/team/<team_name>")
@require_login
async def index(team_name: str | None = None) -> str:
    user_map = await fetch_directory_data()
    enhanced_users = list(user_map.values())
    all_teams: set[str] = set()

    for user in enhanced_users:
        for team in user.teams:
            all_teams.add(team.team_name)

    # Sort users alphabetically by default
    enhanced_users.sort(key=lambda u: u.display_name.lower())

    sorted_teams = sorted(list(all_teams))

    leads: list[EnhancedUser] = []
    members: list[EnhancedUser] = []
    others: list[EnhancedUser] = []

    if team_name:
        for user in enhanced_users:
            # Check if user is in the team
            team_info = next((t for t in user.teams if t.team_name == team_name), None)
            if team_info:
                if team_info.is_lead:
                    leads.append(user)
                else:
                    members.append(user)
            else:
                others.append(user)
    else:
        leads = []
        members = []
        others = enhanced_users

    return render_template(
        "index.html",
        users=enhanced_users,
        leads=leads,
        members=members,
        others=others,
        teams=sorted_teams,
        selected_team=team_name,
    )


@app.route("/user/<username>")
@require_login
async def user_detail(username: str) -> str:
    user_map = await fetch_directory_data()
    user = user_map.get(username)
    if not user:
        abort(404)

    return render_template("user.html", user=user)


def mm_url_proxy(url: str, remove_animation: bool = False) -> Response:
    resp = requests.get(url, headers=mm_client.headers, stream=True)
    resp.raise_for_status()

    excluded_headers = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]
    headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
    content_iter = resp.iter_content(chunk_size=1024)
    if resp.raw.headers["content-type"].startswith("image/gif") and remove_animation:
        content_iter = gif.deanimate(content_iter)

    return Response(content_iter, status=resp.status_code, headers=headers)


@app.route("/mm_emoji/<emoji_name>")
@require_login
def mm_emoji_proxy(emoji_name: str) -> WerkzeugResponse | tuple[str, int]:
    try:
        # Resolve emoji name to ID
        emoji_id = mm_client.get_emoji_id_by_name(emoji_name)
        if not emoji_id:
            return "Not found", 404

        url = mm_client.get_custom_emoji_image_url(emoji_id)
        return mm_url_proxy(url, request.args.get("remove_animation") == "true")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return "Not found", 404
        app.logger.error(f"Failed to proxy emoji {emoji_name}: {e}")
        return "Error", 500
    except Exception as e:
        app.logger.error(f"Failed to proxy emoji {emoji_name}: {e}")
        return "Error", 500


@app.route("/mm_avatar/<user_id>")
@require_login
def mm_avatar_proxy(user_id: str) -> WerkzeugResponse | tuple[str, int]:
    try:
        url = mm_client.get_user_image_url(user_id)
        return mm_url_proxy(url)
    except Exception as e:
        app.logger.error(f"Failed to proxy image for {user_id}: {e}")
        return redirect(url_for("static", filename="default_profile.svg"))


if __name__ == "__main__":
    if not app.config.get("UFFD_USER") or not app.config.get("UFFD_PASSWORD"):
        raise ValueError("UFFD_USER and UFFD_PASSWORD must be set")

    if not app.config.get("MATTERMOST_TOKEN"):
        raise ValueError("MATTERMOST_TOKEN must be set")

    app.run(host="0.0.0.0", port=5000)
