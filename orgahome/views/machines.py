from starlette.requests import Request
from starlette.responses import Response


async def machines(request: Request) -> Response:
    inventory = await request.state.puppetdb_client.query_inventory()
    inventory.sort(key=lambda host: host["certname"])

    return request.state.templates.TemplateResponse(
        request,
        "machines.html",
        {
            "inventory": inventory,
        },
    )
