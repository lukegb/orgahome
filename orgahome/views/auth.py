from starlette.requests import Request
from starlette.responses import RedirectResponse


async def authorize(request: Request):
    token = await request.state.oauth.uffd.authorize_access_token(request)
    request.session["user"] = token["userinfo"]
    next_url = request.session.pop("next", "/")
    return RedirectResponse(url=next_url)
