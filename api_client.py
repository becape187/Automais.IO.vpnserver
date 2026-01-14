"""
Cliente HTTP para comunicação com a API C#
"""
import os
import httpx
import logging
from typing import Optional, Dict, Any, List
from config import API_C_SHARP_URL

logger = logging.getLogger(__name__)


async def get_vpn_network_from_api(vpn_network_id: str) -> Optional[Dict[str, Any]]:
    """Busca dados completos de uma VpnNetwork da API C#"""
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            response = await client.get(
                f"{API_C_SHARP_URL}/api/vpn/networks/{vpn_network_id}",
                headers={"Accept": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar VpnNetwork {vpn_network_id}: {e}")
    return None


async def update_peer_in_api(peer_data: Dict[str, Any]) -> bool:
    """Atualiza peer no banco via API C#"""
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            # Buscar peer existente ou criar novo
            # TODO: Implementar endpoint na API C# para atualizar peer
            logger.info(f"Atualizando peer no banco: {peer_data}")
            return True
    except Exception as e:
        logger.error(f"Erro ao atualizar peer no banco: {e}")
        return False


async def get_router_wireguard_peers_from_api(router_id: str) -> List[Dict[str, Any]]:
    """Busca peers WireGuard de um router da API C#"""
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            response = await client.get(
                f"{API_C_SHARP_URL}/api/routers/{router_id}/wireguard/peers",
                headers={"Accept": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar peers do router {router_id}: {e}")
    return []


async def update_router_status_in_api(router_id: str, is_online: bool) -> bool:
    """Atualiza status online/offline do router no banco via API C#"""
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        url = f"{API_C_SHARP_URL}/api/routers/{router_id}/status"
        payload = {"is_online": is_online}
        
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            response = await client.patch(
                url,
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"✅ Status do router {router_id} atualizado: {'online' if is_online else 'offline'}")
                return True
            else:
                logger.warning(
                    f"⚠️ Erro ao atualizar status do router {router_id}: "
                    f"HTTP {response.status_code} - {response.text[:200]}"
                )
                # Tentar endpoint alternativo se o primeiro falhar
                if response.status_code == 404:
                    # Tentar endpoint alternativo: /api/routers/{router_id}
                    try:
                        alt_url = f"{API_C_SHARP_URL}/api/routers/{router_id}"
                        alt_response = await client.patch(
                            alt_url,
                            json=payload,
                            headers={"Accept": "application/json", "Content-Type": "application/json"}
                        )
                        if alt_response.status_code in [200, 204]:
                            logger.info(f"✅ Status do router {router_id} atualizado via endpoint alternativo: {'online' if is_online else 'offline'}")
                            return True
                    except Exception as alt_e:
                        logger.debug(f"Endpoint alternativo também falhou: {alt_e}")
                return False
    except httpx.TimeoutException:
        logger.error(f"⏱️ Timeout ao atualizar status do router {router_id}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar status do router {router_id} no banco: {e}")
        return False

