import asyncio
import dataclasses

from starlette.requests import Request
from starlette.responses import Response

from orgahome import puppetdb


@dataclasses.dataclass(frozen=True)
class CombinedInfo:
    inventory: puppetdb.PuppetInventoryHost
    emf_info: puppetdb.EMFPuppetInfo | None
    node: puppetdb.PuppetNode | None
    catalog: puppetdb.PuppetCatalog | None
    websites: list[str]

    @property
    def catalog_commit_hash(self) -> str | None:
        if not self.catalog:
            return None
        return self.catalog["version"].split("-")[-1]


async def machines(request: Request) -> Response:
    puppetdb_client: puppetdb.BasePuppetDBClient = request.state.puppetdb_client
    inventory_task = puppetdb_client.query_inventory()
    emf_info_task = puppetdb_client.query_emf_info()
    nodes_task = puppetdb_client.query_nodes()
    catalogs_task = puppetdb_client.query_catalogs()
    websites_task = puppetdb_client.query_websites()
    inventory, emf_info, nodes_list, catalogs_list, websites = await asyncio.gather(
        inventory_task, emf_info_task, nodes_task, catalogs_task, websites_task
    )
    nodes = {node["certname"]: node for node in nodes_list}
    catalogs = {catalog["certname"]: catalog for catalog in catalogs_list}

    inventory.sort(key=lambda host: host["certname"])
    combined_info = [
        CombinedInfo(
            inventory=host,
            emf_info=emf_info.get(host["certname"]),
            node=nodes.get(host["certname"]),
            catalog=catalogs.get(host["certname"]),
            websites=websites.get(host["certname"], []),
        )
        for host in inventory
    ]

    return request.state.templates.TemplateResponse(
        request,
        "machines.html",
        {
            "combined_info": combined_info,
        },
    )
