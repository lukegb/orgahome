from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse


async def authorize(request: Request):
    oauth: OAuth = request.state.oauth
    token = await oauth.uffd.authorize_access_token(request)
    request.session["user"] = token["userinfo"]
    request.session["id_token"] = token["id_token"]
    next_url = request.session.pop("next", "/")
    return RedirectResponse(url=next_url)
