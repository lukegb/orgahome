from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user = request.session.get("user")
        if not user:
            # Store the current URL to redirect back to after login
            request.session["next"] = str(request.url)
            # Redirect to login
            redirect_uri = request.url_for("authorize")
            return await request.state.oauth.uffd.authorize_redirect(request, redirect_uri)

        return await call_next(request)
