"""
Serviço de monitoramento de routers
Faz ping nos routers e atualiza estatísticas dos peers no banco de dados
"""
import asyncio
import os
import subprocess
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import httpx
from config import API_C_SHARP_URL, MONITOR_INTERVAL_SECONDS, PING_ATTEMPTS, PING_TIMEOUT_MS, MAX_CONCURRENT_PINGS
from sync import get_managed_resources
from status import get_wireguard_status
from api_client import get_router_static_routes_from_api, get_router_wireguard_peers_from_api, get_router_from_api
from routeros_websocket import get_router_connection, is_automais_route, extract_route_id_from_comment

logger = logging.getLogger(__name__)

# Semáforo para limitar pings simultâneos
ping_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PINGS)


async def ping_router(ip: str, attempts: int = None, timeout_ms: int = None) -> Dict[str, Any]:
    """
    Faz ping em um router e retorna estatísticas
    
    Args:
        ip: IP do router para fazer ping
        attempts: Número de tentativas (padrão: PING_ATTEMPTS)
        timeout_ms: Timeout em milissegundos (padrão: PING_TIMEOUT_MS)
    
    Returns:
        Dict com success, packet_loss, avg_time_ms, min_time_ms, max_time_ms
    """
    attempts = attempts or PING_ATTEMPTS
    timeout_ms = timeout_ms or PING_TIMEOUT_MS
    
    # Converter timeout de ms para segundos (com margem)
    timeout_sec = (timeout_ms / 1000.0) * attempts + 1
    
    try:
        # Executar ping em thread separada para não bloquear
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _ping_sync,
            ip,
            attempts,
            timeout_sec
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao fazer ping em {ip}: {e}")
        return {
            "success": False,
            "packet_loss": 100.0,
            "avg_time_ms": None,
            "min_time_ms": None,
            "max_time_ms": None,
            "error": str(e)
        }


def _ping_sync(ip: str, attempts: int, timeout_sec: float) -> Dict[str, Any]:
    """Executa ping de forma síncrona (chamado em thread separada)"""
    try:
        # Comando ping: -c (count), -W (timeout em segundos), -i (intervalo)
        # Linux: ping -c 3 -W 1 10.0.0.1
        cmd = ["ping", "-c", str(attempts), "-W", "1", "-i", "0.2", ip]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
        
        if result.returncode == 0:
            # Parsear saída do ping
            output = result.stdout
            lines = output.split('\n')
            
            # Buscar linha de estatísticas (ex: "3 packets transmitted, 3 received, 0% packet loss")
            stats_line = None
            time_line = None
            for line in lines:
                if "packets transmitted" in line.lower():
                    stats_line = line
                if "min/avg/max" in line.lower() or "round-trip" in line.lower():
                    time_line = line
            
            packet_loss = 100.0
            avg_time_ms = None
            min_time_ms = None
            max_time_ms = None
            
            # Extrair packet loss
            if stats_line:
                try:
                    if "0% packet loss" in stats_line:
                        packet_loss = 0.0
                    else:
                        # Extrair porcentagem (ex: "1% packet loss")
                        import re
                        match = re.search(r'(\d+(?:\.\d+)?)% packet loss', stats_line)
                        if match:
                            packet_loss = float(match.group(1))
                except:
                    pass
            
            # Extrair tempos
            if time_line:
                try:
                    # Formato: "min/avg/max = 1.234/2.345/3.456 ms"
                    import re
                    match = re.search(r'(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)', time_line)
                    if match:
                        min_time_ms = float(match.group(1))
                        avg_time_ms = float(match.group(2))
                        max_time_ms = float(match.group(3))
                except:
                    pass
            
            return {
                "success": packet_loss < 100.0,
                "packet_loss": packet_loss,
                "avg_time_ms": avg_time_ms,
                "min_time_ms": min_time_ms,
                "max_time_ms": max_time_ms
            }
        else:
            return {
                "success": False,
                "packet_loss": 100.0,
                "avg_time_ms": None,
                "min_time_ms": None,
                "max_time_ms": None,
                "error": result.stderr or "Ping failed"
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "packet_loss": 100.0,
            "avg_time_ms": None,
            "min_time_ms": None,
            "max_time_ms": None,
            "error": "Timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "packet_loss": 100.0,
            "avg_time_ms": None,
            "min_time_ms": None,
            "max_time_ms": None,
            "error": str(e)
        }


async def get_router_ip_from_peer(peer: Dict[str, Any]) -> Optional[str]:
    """Extrai IP do router a partir do peer (allowed_ips)"""
    allowed_ips = peer.get("allowed_ips", "").strip()
    if not allowed_ips:
        return None
    
    # Pegar o primeiro IP (pode ter múltiplos separados por vírgula)
    first_ip = allowed_ips.split(',')[0].strip()
    
    # Remover prefixo CIDR se houver (ex: "10.222.111.2/32" -> "10.222.111.2")
    if '/' in first_ip:
        first_ip = first_ip.split('/')[0].strip()
    
    return first_ip


async def update_peer_stats_in_api(peer_id: str, stats: Dict[str, Any]) -> bool:
    """Atualiza estatísticas do peer no banco via API C#"""
    try:
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
            response = await client.patch(
                f"{API_C_SHARP_URL}/api/wireguard/peers/{peer_id}/stats",
                json={
                    "last_handshake": stats.get("last_handshake"),
                    "bytes_received": stats.get("bytes_received"),
                    "bytes_sent": stats.get("bytes_sent"),
                    "ping_success": stats.get("ping_success"),
                    "ping_avg_time_ms": stats.get("ping_avg_time_ms"),
                    "ping_packet_loss": stats.get("ping_packet_loss")
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 204]:
                return True
            else:
                logger.warning(f"Erro ao atualizar stats do peer {peer_id}: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Erro ao atualizar stats do peer {peer_id} no banco: {e}")
        return False


async def monitor_router(router: Dict[str, Any]) -> None:
    """Monitora um router específico: faz ping e atualiza stats"""
    router_id = router.get("id")
    router_name = router.get("name", "Unknown")
    peers = router.get("peers", [])
    
    if not peers:
        logger.debug(f"Router {router_name} ({router_id}) não tem peers, pulando monitoramento")
        return
    
    # Pegar o primeiro peer habilitado
    active_peer = None
    for peer in peers:
        if peer.get("is_enabled", True):
            active_peer = peer
            break
    
    if not active_peer:
        logger.debug(f"Router {router_name} ({router_id}) não tem peers habilitados")
        return
    
    peer_id = active_peer.get("id")
    router_ip = await get_router_ip_from_peer(active_peer)
    
    if not router_ip:
        logger.debug(f"Router {router_name} ({router_id}) não tem IP válido para ping")
        return
    
    # Fazer ping com semáforo (limita concorrência)
    async with ping_semaphore:
        logger.debug(f"Fazendo ping em router {router_name} ({router_ip})")
        ping_result = await ping_router(router_ip)
        
        # Buscar stats do WireGuard para este peer
        wg_status = await get_wireguard_status()
        peer_wg_stats = None
        
        # Procurar peer nas interfaces WireGuard
        for interface in wg_status.get("interfaces", []):
            for peer in interface.get("peers", []):
                if peer.get("public_key") == active_peer.get("public_key"):
                    peer_wg_stats = peer
                    break
            if peer_wg_stats:
                break
        
        # Preparar dados para atualização
        update_data = {
            "ping_success": ping_result.get("success", False),
            "ping_avg_time_ms": ping_result.get("avg_time_ms"),
            "ping_packet_loss": ping_result.get("packet_loss", 100.0)
        }
        
        if peer_wg_stats:
            # Converter latest_handshake de ISO string para datetime se necessário
            handshake = peer_wg_stats.get("latest_handshake")
            if handshake:
                try:
                    if isinstance(handshake, str):
                        # Remover Z e converter para datetime
                        handshake_clean = handshake.replace('Z', '+00:00')
                        dt = datetime.fromisoformat(handshake_clean)
                        # Converter para ISO string para JSON
                        update_data["last_handshake"] = dt.isoformat()
                    elif isinstance(handshake, datetime):
                        # Converter para ISO string para JSON
                        update_data["last_handshake"] = handshake.isoformat()
                except Exception as e:
                    logger.debug(f"Erro ao converter handshake {handshake}: {e}")
                    pass
            
            update_data["bytes_received"] = peer_wg_stats.get("transfer_rx", 0)
            update_data["bytes_sent"] = peer_wg_stats.get("transfer_tx", 0)
        
        # Atualizar no banco
        if peer_id:
            success = await update_peer_stats_in_api(peer_id, update_data)
            if success:
                logger.debug(
                    f"✅ Stats atualizados para router {router_name} ({router_ip}): "
                    f"ping={'OK' if ping_result.get('success') else 'FAIL'}, "
                    f"latency={ping_result.get('avg_time_ms', 'N/A')}ms"
                )
            else:
                logger.warning(f"⚠️ Falha ao atualizar stats do router {router_name} ({router_id})")
        else:
            logger.debug(f"Peer {active_peer.get('public_key', 'unknown')[:16]}... não tem ID, pulando atualização")


async def monitor_all_routers() -> None:
    """Monitora todos os routers gerenciados"""
    try:
        managed = get_managed_resources()
        routers = managed.get("routers", [])
        
        if not routers:
            logger.debug("Nenhum router para monitorar")
            return
        
        logger.info(f"🔍 Iniciando monitoramento de {len(routers)} router(s)")
        
        # Criar tasks para monitorar todos os routers em paralelo
        # O semáforo já limita a concorrência
        tasks = [monitor_router(router) for router in routers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"✅ Monitoramento concluído para {len(routers)} router(s)")
        
    except Exception as e:
        logger.error(f"Erro ao monitorar routers: {e}")


async def sync_routes_for_router(router: Dict[str, Any]) -> None:
    """Sincroniza rotas de um router: verifica se rotas Applied ainda existem no RouterOS"""
    router_id = router.get("id")
    router_name = router.get("name", "Unknown")
    
    try:
        # Buscar rotas do banco com status Applied
        routes_db = await get_router_static_routes_from_api(router_id)
        # Status pode vir como string ("Applied") ou número (3) do JSON
        routes_applied = [
            r for r in routes_db 
            if r.get("status") == "Applied" or r.get("status") == 3 or str(r.get("status")).lower() == "applied"
        ]
        
        if not routes_applied:
            return
        
        # Obter IP do router
        router_data = await get_router_from_api(router_id)
        if not router_data:
            return
        
        router_ip = router_data.get("routerOsApiUrl", "").split(":")[0] if router_data.get("routerOsApiUrl") else None
        if not router_ip:
            # Tentar buscar do peer WireGuard
            peers = await get_router_wireguard_peers_from_api(router_id)
            if peers:
                allowed_ips = peers[0].get("allowedIps", "")
                if allowed_ips:
                    router_ip = allowed_ips.split(",")[0].strip().split("/")[0]
        
        if not router_ip:
            logger.debug(f"Router {router_name} ({router_id}) não tem IP válido para sincronização de rotas")
            return
        
        # Conectar ao RouterOS
        api = await get_router_connection(
            router_id,
            router_ip,
            router_data.get("routerOsApiUsername", "admin"),
            router_data.get("routerOsApiPassword", "")
        )
        
        if not api:
            logger.debug(f"Não foi possível conectar ao RouterOS para sincronizar rotas: {router_name} ({router_id})")
            return
        
        # Buscar rotas do RouterOS
        def get_routes_sync():
            route_resource = api.get_resource('/ip/route')
            return route_resource.get()
        
        loop = asyncio.get_event_loop()
        routes_routeros = await loop.run_in_executor(None, get_routes_sync)
        
        # Criar mapa de rotas RouterOS por ID (extraído do comment)
        routes_routeros_map = {}
        for route in routes_routeros:
            comment = route.get("comment", "")
            if is_automais_route(comment):
                route_id = extract_route_id_from_comment(comment)
                if route_id:
                    routes_routeros_map[route_id] = route
        
        # Verificar quais rotas Applied não existem mais no RouterOS
        routes_to_remove = []
        for route_db in routes_applied:
            route_id = route_db.get("id")
            if route_id and route_id not in routes_routeros_map:
                # Rota deveria existir mas não existe mais - marcar para remover
                routes_to_remove.append(route_id)
                logger.warning(
                    f"⚠️ Rota {route_id} (destino: {route_db.get('destination')}) "
                    f"deveria existir no RouterOS mas não foi encontrada. Removendo do banco."
                )
        
        # Remover rotas ausentes do banco via API C#
        for route_id in routes_to_remove:
            try:
                verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
                async with httpx.AsyncClient(timeout=30.0, verify=verify_ssl) as client:
                    response = await client.delete(
                        f"{API_C_SHARP_URL}/api/routers/{router_id}/routes/{route_id}",
                        headers={"Accept": "application/json"}
                    )
                    
                    if response.status_code in [200, 204]:
                        logger.info(f"✅ Rota {route_id} removida do banco (não existia no RouterOS)")
                    else:
                        logger.warning(f"⚠️ Erro ao remover rota {route_id} do banco: {response.status_code}")
            except Exception as e:
                logger.error(f"Erro ao remover rota {route_id} do banco: {e}")
        
    except Exception as e:
        logger.error(f"Erro ao sincronizar rotas do router {router_name} ({router_id}): {e}")


async def sync_routes_for_all_routers() -> None:
    """Sincroniza rotas de todos os routers"""
    try:
        managed = get_managed_resources()
        routers = managed.get("routers", [])
        
        if not routers:
            return
        
        logger.debug(f"🔄 Sincronizando rotas de {len(routers)} router(s)")
        
        # Sincronizar rotas de todos os routers em paralelo
        tasks = [sync_routes_for_router(router) for router in routers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except Exception as e:
        logger.error(f"Erro ao sincronizar rotas: {e}")


async def background_monitor_loop():
    """Loop em background para monitorar routers periodicamente"""
    logger.info(f"🔄 Iniciando loop de monitoramento (intervalo: {MONITOR_INTERVAL_SECONDS}s)")
    
    while True:
        try:
            await monitor_all_routers()
            # Sincronizar rotas após monitoramento
            await sync_routes_for_all_routers()
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Erro no loop de monitoramento: {e}")
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)

