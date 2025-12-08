import asyncio
import dataclasses

from starlette.requests import Request
from starlette.responses import Response

from orgahome import puppetdb


@dataclasses.dataclass(frozen=True)
class CombinedInfo:
    inventory: puppetdb.PuppetInventoryHost
    emf_info: puppetdb.EMFPuppetInfo | None


async def machines(request: Request) -> Response:
    puppetdb_client: puppetdb.BasePuppetDBClient = request.state.puppetdb_client
    inventory_task = puppetdb_client.query_inventory()
    emf_info_task = puppetdb_client.query_emf_info()
    inventory, emf_info = await asyncio.gather(inventory_task, emf_info_task)

    inventory.sort(key=lambda host: host["certname"])
    combined_info = [CombinedInfo(host, emf_info.get(host["certname"])) for host in inventory]

    return request.state.templates.TemplateResponse(
        request,
        "machines.html",
        {
            "combined_info": combined_info,
        },
    )
