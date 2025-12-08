import datetime
import logging
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import aiohttp
from authlib.integrations.starlette_client import OAuth
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount, Route, Router
from starlette.templating import Jinja2Templates

from orgahome import puppetdb, staticfiles
from orgahome.config import Config
from orgahome.middleware import AuthMiddleware
from orgahome.services import MattermostClient, UFFDClient
from orgahome.views import auth, directory, machines, proxy

logger = logging.getLogger(__name__)


class State(TypedDict):
    client_session: aiohttp.ClientSession
    uffd_client: UFFDClient
    mm_client: MattermostClient
    oauth: OAuth
    templates: Jinja2Templates
    puppetdb: puppetdb.BasePuppetDBClient


def _friendly_date(x: datetime.datetime) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    ago = now - x
    if ago.days < 1:
        return x.strftime("%H:%M")
    else:
        return x.strftime("%Y-%m-%d %H:%M")


def lifespan_factory(static_files: staticfiles.StaticFilesBase):
    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[State]:
        if not Config.MATTERMOST_API_URL or not Config.MATTERMOST_TOKEN:
            raise ValueError("MATTERMOST_API_URL and MATTERMOST_TOKEN must be set")

        if not Config.UFFD_URL or not Config.UFFD_API_URL or not Config.UFFD_USER or not Config.UFFD_PASSWORD:
            raise ValueError("UFFD_URL, UFFD_API_URL, UFFD_USER, and UFFD_PASSWORD must be set")

        if not Config.OIDC_CLIENT_ID or not Config.OIDC_CLIENT_SECRET:
            raise ValueError("OIDC_CLIENT_ID and OIDC_CLIENT_SECRET must be set")

        templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / "templates")
        static_files.register_template_functions(templates)
        templates.env.filters["from_iso"] = lambda x: datetime.datetime.fromisoformat(x)
        templates.env.filters["friendly_date"] = _friendly_date

        async with (
            aiohttp.ClientSession() as session,
            puppetdb.make_puppetdb_client(
                api_url=Config.PUPPETDB_API_URL,
                cacert_path=Config.PUPPETDB_CA_FILE,
                cert_path=Config.PUPPETDB_CERT_FILE,
                privkey_path=Config.PUPPETDB_KEY_FILE,
                ssl_verify_hostname=Config.PUPPETDB_SSL_VERIFY_HOSTNAME,
            ) as puppetdb_client,
        ):
            uffd_client = UFFDClient(session, Config.UFFD_API_URL, Config.UFFD_USER, Config.UFFD_PASSWORD)
            mm_client = MattermostClient(session, Config.MATTERMOST_API_URL, Config.MATTERMOST_TOKEN)

            oauth = OAuth()
            oauth.register(
                name="uffd",
                client_id=Config.OIDC_CLIENT_ID,
                client_secret=Config.OIDC_CLIENT_SECRET,
                client_kwargs={"scope": Config.OIDC_SCOPES},
                server_metadata_url=f"{Config.UFFD_URL}/.well-known/openid-configuration",
            )

            yield {
                "client_session": session,
                "uffd_client": uffd_client,
                "puppetdb_client": puppetdb_client,
                "mm_client": mm_client,
                "oauth": oauth,
                "templates": templates,
            }

    return lifespan


def create_app(debug: bool = False) -> Starlette:
    protected_routes = [
        Route("/", endpoint=directory.index),
        Route("/team/{team_name}", endpoint=directory.index),
        Route("/user/{username}", endpoint=directory.user_detail),
        Route("/mm_emoji/{emoji_name}", endpoint=proxy.mm_emoji_proxy),
        Route("/mm_avatar/{user_id}", endpoint=proxy.mm_avatar_proxy),
        Route("/machines", endpoint=machines.machines),
    ]

    protected_router = Router(routes=protected_routes, middleware=[Middleware(AuthMiddleware)])  # ty: ignore[invalid-argument-type]

    static_files: staticfiles.StaticFilesBase
    if debug:
        static_files = staticfiles.DevelopmentStaticFiles()
    else:
        serving_dir = pathlib.Path(Config.ORGAHOME_DIST_ROOT or staticfiles.STATIC_COMPILED_PATH)
        if not serving_dir.exists():
            raise ValueError(f"Static files directory {serving_dir} does not exist")
        static_files = staticfiles.ManifestStaticFiles(serving_dir=serving_dir)

    routes = [
        Route("/authorize", endpoint=auth.authorize),
        Mount("/static", app=staticfiles.StaticFilesServer(static_files), name="static"),
        Mount("/", app=protected_router),
    ]

    middleware = [
        Middleware(SessionMiddleware, secret_key=Config.SECRET_KEY),  # ty: ignore[invalid-argument-type]
    ]

    return Starlette(debug=debug, routes=routes, middleware=middleware, lifespan=lifespan_factory(static_files))


app = create_app(debug=False)
debug_app = create_app(debug=True)
