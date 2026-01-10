"""
Cache em memória para informações dos peers WireGuard
Armazena nomes de routers, VPNs e outras informações para acesso rápido
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Cache em memória: public_key -> informações do peer
_peer_cache: Dict[str, Dict[str, Optional[str]]] = {}


def get_peer_info(public_key: str) -> Dict[str, Optional[str]]:
    """
    Obtém informações do peer do cache
    
    Args:
        public_key: Chave pública do peer WireGuard
        
    Returns:
        Dicionário com informações do peer ou dicionário vazio se não encontrado
    """
    return _peer_cache.get(public_key, {})


def set_peer_info(
    public_key: str,
    router_id: Optional[str] = None,
    router_name: Optional[str] = None,
    vpn_network_id: Optional[str] = None,
    vpn_network_name: Optional[str] = None,
    peer_ip: Optional[str] = None,
    allowed_ips: Optional[str] = None
) -> None:
    """
    Armazena informações do peer no cache
    
    Args:
        public_key: Chave pública do peer WireGuard
        router_id: ID do router
        router_name: Nome do router
        vpn_network_id: ID da rede VPN
        vpn_network_name: Nome da rede VPN
        peer_ip: IP do peer (sem CIDR)
        allowed_ips: IPs permitidos (com CIDR)
    """
    if not public_key:
        return
    
    # Se já existe, atualizar apenas os campos fornecidos
    if public_key in _peer_cache:
        if router_id is not None:
            _peer_cache[public_key]["router_id"] = router_id
        if router_name is not None:
            _peer_cache[public_key]["router_name"] = router_name
        if vpn_network_id is not None:
            _peer_cache[public_key]["vpn_network_id"] = vpn_network_id
        if vpn_network_name is not None:
            _peer_cache[public_key]["vpn_network_name"] = vpn_network_name
        if peer_ip is not None:
            _peer_cache[public_key]["peer_ip"] = peer_ip
        if allowed_ips is not None:
            _peer_cache[public_key]["allowed_ips"] = allowed_ips
    else:
        # Criar novo registro
        _peer_cache[public_key] = {
            "router_id": router_id,
            "router_name": router_name,
            "vpn_network_id": vpn_network_id,
            "vpn_network_name": vpn_network_name,
            "peer_ip": peer_ip,
            "allowed_ips": allowed_ips
        }
    
    logger.debug(f"✅ Cache atualizado para peer {public_key[:16]}...: router={router_name}, vpn={vpn_network_name}, ip={peer_ip}")


def remove_peer_info(public_key: str) -> None:
    """
    Remove informações do peer do cache
    
    Args:
        public_key: Chave pública do peer WireGuard
    """
    if public_key in _peer_cache:
        del _peer_cache[public_key]
        logger.debug(f"🗑️ Peer {public_key[:16]}... removido do cache")


def clear_cache() -> None:
    """Limpa todo o cache"""
    _peer_cache.clear()
    logger.info("🗑️ Cache de peers limpo")


def get_all_peers() -> Dict[str, Dict[str, Optional[str]]]:
    """
    Retorna todo o cache (cópia)
    
    Returns:
        Dicionário completo do cache
    """
    return _peer_cache.copy()


def get_cache_size() -> int:
    """Retorna o número de peers no cache"""
    return len(_peer_cache)


def sync_from_api_data(routers: list, vpn_networks: list) -> None:
    """
    Sincroniza o cache com dados da API C#
    
    Args:
        routers: Lista de routers da API
        vpn_networks: Lista de VPNs da API
    """
    updated_count = 0
    
    # Criar dicionário de VPNs para lookup rápido
    vpn_dict = {vpn.get("id"): vpn for vpn in vpn_networks}
    
    # Processar cada router e seus peers
    for router in routers:
        router_id = router.get("id")
        router_name = router.get("name")
        vpn_network_id = router.get("vpn_network_id")
        
        # Obter informações da VPN
        vpn_network = vpn_dict.get(vpn_network_id, {})
        vpn_network_name = vpn_network.get("name")
        
        # Processar peers do router
        peers = router.get("peers", [])
        for peer in peers:
            public_key = peer.get("public_key", "").strip()
            if not public_key:
                continue
            
            allowed_ips = peer.get("allowed_ips", "").strip()
            
            # Extrair IP do allowed_ips
            peer_ip = None
            if allowed_ips:
                first_ip = allowed_ips.split(',')[0].strip()
                if '/' in first_ip:
                    peer_ip = first_ip.split('/')[0].strip()
                else:
                    peer_ip = first_ip
            
            # Atualizar cache
            set_peer_info(
                public_key=public_key,
                router_id=router_id,
                router_name=router_name,
                vpn_network_id=vpn_network_id,
                vpn_network_name=vpn_network_name,
                peer_ip=peer_ip,
                allowed_ips=allowed_ips
            )
            updated_count += 1
    
    logger.info(f"✅ Cache sincronizado: {updated_count} peer(s) atualizado(s)")

