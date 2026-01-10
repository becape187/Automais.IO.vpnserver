"""
Sincronização de recursos com a API C#
"""
import httpx
import logging
from typing import Dict, Any
from datetime import datetime
from config import VPN_SERVER_NAME, API_C_SHARP_URL, SYNC_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

# Cache de recursos gerenciados por esta instância
managed_resources: Dict[str, Any] = {
    "vpn_networks": [],
    "routers": [],
    "last_sync": None
}


async def sync_resources_from_api():
    """Sincroniza recursos (VpnNetworks e Routers) da API C#"""
    if not VPN_SERVER_NAME:
        logger.warning("VPN_SERVER_NAME não configurado. Não é possível sincronizar recursos.")
        return
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_C_SHARP_URL}/api/vpn-servers/{VPN_SERVER_NAME}/resources",
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 404:
                logger.warning(f"Servidor VPN '{VPN_SERVER_NAME}' não encontrado na API principal")
                return
            
            if response.status_code != 200:
                logger.error(f"Erro ao consultar recursos: {response.status_code} - {response.text}")
                return
            
            data = response.json()
            managed_resources["vpn_networks"] = data.get("vpn_networks", [])
            managed_resources["routers"] = data.get("routers", [])
            managed_resources["last_sync"] = datetime.utcnow().isoformat()
            
            logger.info(
                f"✅ Recursos sincronizados: {len(managed_resources['vpn_networks'])} VPNs, "
                f"{len(managed_resources['routers'])} Routers"
            )
            
    except httpx.TimeoutException:
        logger.error(f"Timeout ao consultar API principal: {API_C_SHARP_URL}")
    except Exception as e:
        logger.error(f"Erro ao sincronizar recursos: {e}")


def is_resource_managed(resource_id: str, resource_type: str = "vpn_network") -> bool:
    """Verifica se um recurso é gerenciado por esta instância"""
    if resource_type == "vpn_network":
        return any(vpn["id"] == resource_id for vpn in managed_resources["vpn_networks"])
    elif resource_type == "router":
        return any(router["id"] == resource_id for router in managed_resources["routers"])
    return False


def get_managed_resources() -> Dict[str, Any]:
    """Retorna recursos gerenciados"""
    return managed_resources

