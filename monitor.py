"""
Serviço de monitoramento de peers WireGuard
Faz ping nos routers e atualiza estatísticas dos peers WireGuard no banco de dados
"""
import asyncio
import os
import subprocess
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from config import API_C_SHARP_URL, MONITOR_INTERVAL_SECONDS, PING_ATTEMPTS, PING_TIMEOUT_MS, MAX_CONCURRENT_PINGS
from sync import get_managed_resources
from status import get_wireguard_status
from api_client import get_router_wireguard_peers_from_api, update_router_status_in_api, update_router_data_in_api

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
    
    logger.debug(f"🔍 Monitorando router {router_name} ({router_id}) - {len(peers)} peer(s) encontrado(s)")
    
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
        logger.warning(f"⚠️ Router {router_name} ({router_id}) não tem IP válido para ping. Peer ID: {peer_id}, AllowedIPs: {active_peer.get('allowedIps', 'N/A')}")
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
        
        # Determinar status do router baseado no status do peer WireGuard
        # Priorizar status do WireGuard (mais confiável), mas considerar ping também
        router_is_online = False
        status_source = "unknown"
        if peer_wg_stats:
            peer_status = peer_wg_stats.get("status", "offline")
            router_is_online = peer_status == "online"
            status_source = "wireguard"
            logger.debug(f"Status do router {router_name} baseado em WireGuard: {peer_status}")
        else:
            # Se não encontrou stats do WireGuard, usar ping como fallback
            router_is_online = ping_result.get("success", False)
            status_source = "ping"
            logger.debug(f"Status do router {router_name} baseado em ping: {'online' if router_is_online else 'offline'}")
        
        # Nota: router_is_online não é enviado no payload do peer
        # O status do router é atualizado separadamente via PUT /api/routers/{id}
        
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
        
        # Preparar dados para atualização do router
        # IMPORTANTE: Usar PascalCase para compatibilidade com C# (LastSeenAt, Latency, etc)
        router_update_data = {}
        
        # Status do router
        status_value = 1 if router_is_online else 2  # RouterStatus.Online = 1, RouterStatus.Offline = 2
        router_update_data["status"] = status_value
        
        # Se router está online, atualizar LastSeenAt e Latency
        if router_is_online:
            router_update_data["lastSeenAt"] = datetime.now(timezone.utc).isoformat()
            
            # Latência do ping (converter para int se disponível)
            if ping_result.get("avg_time_ms") is not None:
                router_update_data["latency"] = int(round(ping_result.get("avg_time_ms")))
        
        logger.debug(f"📋 Dados preparados para atualização do router {router_name}: {router_update_data}")
        
        # Atualizar dados do router no banco
        if router_id:
            logger.info(f"📤 Atualizando dados do router {router_name} ({router_id}): {list(router_update_data.keys())}")
            status_updated = await update_router_data_in_api(router_id, router_update_data)
            if status_updated:
                updated_fields = list(router_update_data.keys())
                logger.info(f"✅ Dados do router {router_name} ({router_id}) atualizados com sucesso: {updated_fields} (status={'online' if router_is_online else 'offline'}, fonte: {status_source})")
            else:
                logger.warning(f"⚠️ Falha ao atualizar dados do router {router_name} ({router_id}) no banco. Payload: {router_update_data}")
        
        # Atualizar stats do peer no banco (inclui router_is_online no payload caso API atualize automaticamente)
        if peer_id:
            success = await update_peer_stats_in_api(peer_id, update_data)
            if success:
                logger.debug(
                    f"✅ Stats atualizados para router {router_name} ({router_ip}): "
                    f"status={'online' if router_is_online else 'offline'}, "
                    f"ping={'OK' if ping_result.get('success') else 'FAIL'}, "
                    f"latency={ping_result.get('avg_time_ms', 'N/A')}ms"
                )
            else:
                logger.warning(f"⚠️ Falha ao atualizar stats do router {router_name} ({router_id})")
        else:
            logger.debug(f"Peer {active_peer.get('public_key', 'unknown')[:16]}... não tem ID, pulando atualização")


async def monitor_all_routers() -> None:
    """Monitora todos os routers gerenciados (apenas peers WireGuard)"""
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


async def background_monitor_loop():
    """Loop em background para monitorar peers WireGuard periodicamente"""
    logger.info(f"🔄 Iniciando loop de monitoramento (intervalo: {MONITOR_INTERVAL_SECONDS}s)")
    
    while True:
        try:
            await monitor_all_routers()
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Erro no loop de monitoramento: {e}")
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)

