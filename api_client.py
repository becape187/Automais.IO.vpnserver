"""
Cliente HTTP para comunicação com a API C#
"""
import httpx
import logging
from typing import Optional, Dict, Any
from config import API_C_SHARP_URL

logger = logging.getLogger(__name__)


async def get_vpn_network_from_api(vpn_network_id: str) -> Optional[Dict[str, Any]]:
    """Busca dados completos de uma VpnNetwork da API C#"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_C_SHARP_URL}/api/vpn/networks/{vpn_network_id}",
                headers={"Accept": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar VpnNetwork {vpn_network_id}: {e}")
    return None


async def get_router_from_api(router_id: str) -> Optional[Dict[str, Any]]:
    """Busca dados completos de um Router da API C#"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_C_SHARP_URL}/api/routers/{router_id}",
                headers={"Accept": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar Router {router_id}: {e}")
    return None


async def update_peer_in_api(peer_data: Dict[str, Any]) -> bool:
    """Atualiza peer no banco via API C#"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Buscar peer existente ou criar novo
            # TODO: Implementar endpoint na API C# para atualizar peer
            logger.info(f"Atualizando peer no banco: {peer_data}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar peer no banco: {e}")
        return False

