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


async def update_router_data_in_api(router_id: str, data: Dict[str, Any]) -> bool:
    """
    Atualiza dados do router no banco via API C#
    
    Campos suportados:
    - status: RouterStatus (1=Online, 2=Offline)
    - lastSeenAt: DateTime (quando foi visto online pela última vez)
    - latency: int (latência do ping em ms)
    - hardwareInfo: string (JSON com informações de hardware)
    - firmwareVersion: string
    - model: string
    """
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        url = f"{API_C_SHARP_URL}/api/routers/{router_id}"
        
        # Log detalhado do payload antes de enviar
        import json as json_lib
        logger.info(f"📤 [VPNSERVER] Enviando atualização do router {router_id}")
        logger.info(f"   URL: {url}")
        logger.info(f"   Campos: {list(data.keys())}")
        # Log completo do JSON
        try:
            json_payload = json_lib.dumps(data, indent=2, ensure_ascii=False)
            logger.info(f"   📋 Payload completo (JSON):\n{json_payload}")
        except Exception as e:
            logger.warning(f"   ⚠️ Erro ao serializar payload para log: {e}")
            # Fallback: log campo por campo
            for key, value in data.items():
                if key == "hardwareInfo" and isinstance(value, str) and len(value) > 200:
                    logger.info(f"   {key}: {value[:200]}... (truncado, tamanho total: {len(value)} chars)")
                else:
                    logger.info(f"   {key}: {value}")
        
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            response = await client.put(
                url,
                json=data,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Dados do router {router_id} atualizados com sucesso: {list(data.keys())}")
                return True
            elif response.status_code == 404:
                logger.warning(f"⚠️ Router {router_id} não encontrado (404)")
                return False
            else:
                logger.error(
                    f"❌ Erro ao atualizar dados do router {router_id}: "
                    f"HTTP {response.status_code} - {response.text[:500]}"
                )
                logger.error(f"   Payload enviado: {data}")
                return False
    except httpx.TimeoutException:
        logger.error(f"⏱️ Timeout ao atualizar dados do router {router_id}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar dados do router {router_id} no banco: {e}")
        return False


async def update_router_status_in_api(router_id: str, is_online: bool) -> bool:
    """
    Atualiza status online/offline do router no banco via API C#
    
    Usa PUT /api/routers/{id} com UpdateRouterDto contendo Status:
    - RouterStatus.Online = 1 (online)
    - RouterStatus.Offline = 2 (offline)
    """
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        # RouterStatus enum: Online = 1, Offline = 2
        status_value = 1 if is_online else 2
        payload = {"status": status_value}
        
        url = f"{API_C_SHARP_URL}/api/routers/{router_id}"
        
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            response = await client.put(
                url,
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Status do router {router_id} atualizado: {'online' if is_online else 'offline'} (status={status_value})")
                return True
            elif response.status_code == 404:
                logger.warning(f"⚠️ Router {router_id} não encontrado (404)")
                return False
            else:
                logger.warning(
                    f"⚠️ Erro ao atualizar status do router {router_id}: "
                    f"HTTP {response.status_code} - {response.text[:200]}"
                )
                return False
    except httpx.TimeoutException:
        logger.error(f"⏱️ Timeout ao atualizar status do router {router_id}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar status do router {router_id} no banco: {e}")
        return False

