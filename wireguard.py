"""
Lógica completa do WireGuard
Gerencia interfaces, peers, chaves, IPs, firewall, etc.
"""
import os
import ipaddress
import logging
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from config import WIREGUARD_CONFIG_DIR
from utils import execute_command
from api_client import get_vpn_network_from_api

logger = logging.getLogger(__name__)


def get_interface_name(vpn_network_id: str) -> str:
    """Gera nome da interface WireGuard baseado no ID da VPN"""
    clean_id = vpn_network_id.replace("-", "")[:8]
    return f"wg-{clean_id}"


async def generate_wireguard_keys() -> tuple[str, str]:
    """Gera par de chaves WireGuard (privada, pública)"""
    stdout, stderr, returncode = execute_command("wg genkey")
    if returncode != 0:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar chave privada: {stderr}")
    private_key = stdout.strip()
    
    stdout, stderr, returncode = execute_command(f"echo '{private_key}' | wg pubkey")
    if returncode != 0:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar chave pública: {stderr}")
    public_key = stdout.strip()
    
    return private_key, public_key


def parse_cidr(cidr: str) -> tuple[ipaddress.IPv4Address, int]:
    """Parse CIDR e retorna (network_ip, prefix_length)"""
    try:
        network = ipaddress.IPv4Network(cidr, strict=False)
        return network.network_address, network.prefixlen
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"CIDR inválido: {cidr}")


def get_server_ip(network_ip: ipaddress.IPv4Address) -> str:
    """Obtém IP do servidor (primeiro IP da rede + 1, ex: 10.100.1.0/24 -> 10.100.1.1)"""
    ip_bytes = network_ip.packed
    server_ip = ipaddress.IPv4Address(int.from_bytes(ip_bytes, 'big') + 1)
    return str(server_ip)


async def get_main_network_interface() -> Optional[str]:
    """Detecta a interface de rede principal"""
    try:
        stdout, _, returncode = execute_command("ip route | grep default | awk '{print $5}' | head -1", check=False)
        if returncode == 0 and stdout.strip():
            return stdout.strip()
        
        # Fallback: tentar interfaces comuns
        for iface in ["eth0", "ens3", "enp0s3", "enp0s8"]:
            _, _, returncode = execute_command(f"ip link show {iface} >/dev/null 2>&1", check=False)
            if returncode == 0:
                return iface
    except Exception as e:
        logger.warning(f"Erro ao detectar interface principal: {e}")
    return None


async def configure_firewall_rules(interface_name: str, vpn_cidr: str):
    """Configura regras de firewall (iptables) para WireGuard"""
    try:
        # Verificar se iptables está disponível
        _, _, returncode = execute_command("iptables --version", check=False)
        if returncode != 0:
            logger.warning("iptables não encontrado. Regras de firewall não serão configuradas.")
            return
        
        # Permitir tráfego na porta WireGuard (UDP 51820)
        execute_command("iptables -C INPUT -p udp --dport 51820 -j ACCEPT 2>/dev/null || iptables -A INPUT -p udp --dport 51820 -j ACCEPT", check=False)
        
        # Permitir tráfego na interface WireGuard
        execute_command(f"iptables -C INPUT -i {interface_name} -j ACCEPT 2>/dev/null || iptables -A INPUT -i {interface_name} -j ACCEPT", check=False)
        execute_command(f"iptables -C OUTPUT -o {interface_name} -j ACCEPT 2>/dev/null || iptables -A OUTPUT -o {interface_name} -j ACCEPT", check=False)
        
        # Permitir forwarding
        execute_command(f"iptables -C FORWARD -i {interface_name} -j ACCEPT 2>/dev/null || iptables -A FORWARD -i {interface_name} -j ACCEPT", check=False)
        execute_command(f"iptables -C FORWARD -o {interface_name} -j ACCEPT 2>/dev/null || iptables -A FORWARD -o {interface_name} -j ACCEPT", check=False)
        
        # NAT (masquerade) - detectar interface principal
        main_interface = await get_main_network_interface()
        if main_interface:
            execute_command(
                f"iptables -t nat -C POSTROUTING -s {vpn_cidr} -o {main_interface} -j MASQUERADE 2>/dev/null || "
                f"iptables -t nat -A POSTROUTING -s {vpn_cidr} -o {main_interface} -j MASQUERADE",
                check=False
            )
        
        logger.info(f"Regras de firewall configuradas para interface {interface_name}")
    except Exception as e:
        logger.warning(f"Erro ao configurar firewall: {e}")


async def ensure_interface_exists(vpn_network: Dict[str, Any]) -> str:
    """
    Garante que a interface WireGuard existe para uma VpnNetwork.
    Cria arquivo de configuração, gera chaves se necessário, ativa interface.
    """
    vpn_network_id = vpn_network["id"]
    interface_name = get_interface_name(vpn_network_id)
    config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
    
    # Verificar se arquivo já existe
    if os.path.exists(config_path):
        logger.debug(f"Interface {interface_name} já existe")
        # Verificar se está ativa
        stdout, _, returncode = execute_command(f"wg show {interface_name}", check=False)
        if returncode == 0:
            logger.debug(f"Interface {interface_name} já está ativa")
            return interface_name
    
    # Buscar ou gerar chaves do servidor
    server_private_key = vpn_network.get("server_private_key")
    server_public_key = vpn_network.get("server_public_key")
    
    if not server_private_key or not server_public_key:
        logger.info(f"Gerando novas chaves para VPN {vpn_network_id}")
        server_private_key, server_public_key = await generate_wireguard_keys()
        # TODO: Atualizar no banco via API C#
    
    # Parse CIDR
    network_ip, prefix_length = parse_cidr(vpn_network["cidr"])
    server_ip = get_server_ip(network_ip)
    
    # Criar conteúdo do arquivo de configuração
    config_content = f"""[Interface]
PrivateKey = {server_private_key}
Address = {server_ip}/{prefix_length}
ListenPort = 51820
"""
    
    if vpn_network.get("dns_servers"):
        config_content += f"DNS = {vpn_network['dns_servers']}\n"
    
    config_content += "\n# Peers serão adicionados automaticamente pela API\n"
    
    # Criar diretório se não existir
    os.makedirs(WIREGUARD_CONFIG_DIR, mode=0o700, exist_ok=True)
    
    # Salvar arquivo
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    # Definir permissões (600 = rw-------)
    execute_command(f"chmod 600 {config_path}", check=False)
    
    logger.info(f"Arquivo de configuração criado: {config_path}")
    
    # Configurar firewall
    await configure_firewall_rules(interface_name, vpn_network["cidr"])
    
    # Ativar interface se não estiver ativa
    stdout, _, returncode = execute_command(f"wg show {interface_name}", check=False)
    if returncode != 0:
        logger.info(f"Ativando interface {interface_name}")
        execute_command(f"wg-quick up {interface_name}", check=False)
    
    return interface_name


async def allocate_vpn_ip(vpn_network_id: str, manual_ip: Optional[str] = None) -> str:
    """Aloca um IP na rede VPN"""
    vpn_network = await get_vpn_network_from_api(vpn_network_id)
    if not vpn_network:
        raise HTTPException(status_code=404, detail=f"VpnNetwork {vpn_network_id} não encontrada")
    
    cidr = vpn_network["cidr"]
    network_ip, prefix_length = parse_cidr(cidr)
    
    if manual_ip:
        # Validar IP manual
        ip_parts = manual_ip.split('/')
        if len(ip_parts) != 2:
            raise HTTPException(status_code=400, detail="IP manual inválido. Use formato: IP/PREFIX")
        
        requested_ip = ipaddress.IPv4Address(ip_parts[0])
        requested_prefix = int(ip_parts[1])
        
        if requested_prefix != prefix_length:
            raise HTTPException(status_code=400, detail=f"Prefix deve ser {prefix_length}")
        
        # Verificar se está na rede
        network = ipaddress.IPv4Network(cidr, strict=False)
        if requested_ip not in network:
            raise HTTPException(status_code=400, detail=f"IP {manual_ip} não está na rede {cidr}")
        
        # Verificar se não é o IP do servidor (.1)
        server_ip = get_server_ip(network_ip)
        if str(requested_ip) == server_ip:
            raise HTTPException(status_code=400, detail=f"IP {manual_ip} é reservado para o servidor")
        
        return manual_ip
    
    # Alocar IP automaticamente
    # TODO: Buscar IPs alocados do banco via API C#
    # Por enquanto, começar do .2
    ip_bytes = network_ip.packed
    for i in range(2, 255):
        allocated_ip = ipaddress.IPv4Address(int.from_bytes(ip_bytes, 'big') + i)
        # TODO: Verificar se IP já está alocado
        return f"{allocated_ip}/{prefix_length}"
    
    raise HTTPException(status_code=500, detail="Não há IPs disponíveis na rede VPN")


async def add_peer_to_interface(interface_name: str, public_key: str, allowed_ips: str, router_id: str = None, router_name: str = None, vpn_network_id: str = None, vpn_network_name: str = None):
    """Adiciona peer à interface WireGuard com comentários identificadores"""
    # Verificar se interface está ativa
    stdout, _, returncode = execute_command(f"wg show {interface_name}", check=False)
    interface_active = returncode == 0
    
    # Adicionar peer via wg set (funciona mesmo se interface não estiver ativa, mas será aplicado quando ativar)
    execute_command(f"wg set {interface_name} peer {public_key} allowed-ips {allowed_ips}")
    
    # Adicionar ao arquivo de configuração
    config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Verificar se peer já existe
        peer_exists = public_key in content
        
        if not peer_exists:
            # Peer não existe, adicionar novo
            with open(config_path, 'a') as f:
                # Adicionar comentários identificadores com informações completas
                f.write(f"\n# ============================================\n")
                if router_name:
                    f.write(f"# Router: {router_name}\n")
                if router_id:
                    f.write(f"# Router ID: {router_id}\n")
                if vpn_network_name:
                    f.write(f"# VPN Network: {vpn_network_name}\n")
                if vpn_network_id:
                    f.write(f"# VPN Network ID: {vpn_network_id}\n")
                # Adicionar IP configurado do peer
                if allowed_ips:
                    # Extrair IP do allowed_ips (pode ser uma rede como 10.222.111.0/24)
                    peer_ip = allowed_ips.split(',')[0].strip()
                    if '/' in peer_ip:
                        peer_ip = peer_ip.split('/')[0]
                    f.write(f"# Peer IP: {peer_ip}\n")
                f.write(f"# Public Key: {public_key}\n")
                f.write(f"# ============================================\n")
                f.write(f"[Peer]\n")
                f.write(f"PublicKey = {public_key}\n")
                f.write(f"AllowedIPs = {allowed_ips}\n")
                f.write(f"PersistentKeepalive = 25\n")
            
            execute_command(f"chmod 600 {config_path}", check=False)
            logger.info(f"Peer {public_key} adicionado ao arquivo {config_path}")
        else:
            # Peer já existe, atualizar comentários se necessário
            import re
            # Construir novos comentários
            new_comments_lines = [
                "\n# ============================================"
            ]
            if router_name:
                new_comments_lines.append(f"# Router: {router_name}")
            if router_id:
                new_comments_lines.append(f"# Router ID: {router_id}")
            if vpn_network_name:
                new_comments_lines.append(f"# VPN Network: {vpn_network_name}")
            if vpn_network_id:
                new_comments_lines.append(f"# VPN Network ID: {vpn_network_id}")
            if allowed_ips:
                peer_ip = allowed_ips.split(',')[0].strip()
                if '/' in peer_ip:
                    peer_ip = peer_ip.split('/')[0]
                new_comments_lines.append(f"# Peer IP: {peer_ip}")
            new_comments_lines.append(f"# Public Key: {public_key}")
            new_comments_lines.append("# ============================================")
            new_comments = "\n".join(new_comments_lines) + "\n"
            
            # Procurar bloco de comentários existente antes do [Peer] com esta public_key
            # Padrão: comentários entre # ============================================ e [Peer] seguido de PublicKey = {public_key}
            pattern = rf'(# ============================================\n(?:# [^\n]+\n)*# Public Key: {re.escape(public_key)}\n# ============================================\n\[Peer\])'
            
            # Substituir comentários antigos pelos novos
            updated_content = re.sub(pattern, new_comments + "[Peer]", content, flags=re.DOTALL)
            if updated_content != content:
                with open(config_path, 'w') as f:
                    f.write(updated_content)
                execute_command(f"chmod 600 {config_path}", check=False)
                logger.info(f"✅ Comentários do peer {public_key[:16]}... atualizados no arquivo {config_path}")
            else:
                logger.debug(f"Peer {public_key[:16]}... já existe, comentários já estão atualizados")
    
    # Sincronizar arquivo com interface (aplica mudanças sem derrubar conexões existentes)
    if interface_active:
        # Se interface está ativa, usar syncconf que não derruba conexões
        execute_command(f"wg syncconf {interface_name} {config_path}", check=False)
        logger.info(f"✅ Peer {public_key[:16]}... adicionado à interface ativa {interface_name}")
    else:
        # Se interface não está ativa, ativar com wg-quick up
        logger.info(f"Interface {interface_name} não está ativa, ativando...")
        execute_command(f"wg-quick up {interface_name}", check=False)
        logger.info(f"✅ Interface {interface_name} ativada com peer {public_key[:16]}...")


async def generate_router_config(router: Dict[str, Any], peer: Dict[str, Any], vpn_network: Dict[str, Any], allowed_networks: List[str]) -> str:
    """Gera conteúdo do arquivo .conf para o router"""
    from datetime import datetime
    
    config_lines = [
        "# Configuração VPN para Router",
        "",
        f"# Router: {router.get('name', 'Unknown')}",
        f"# Gerado em: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "[Interface]",
        f"PrivateKey = {peer['private_key']}",
        f"Address = {peer['allowed_ips']}",
        "",
        "[Peer]",
        f"PublicKey = {vpn_network.get('server_public_key', '')}",
        f"Endpoint = {vpn_network.get('server_endpoint', 'automais.io')}:51820",
    ]
    
    # Adicionar redes permitidas
    all_networks = [vpn_network["cidr"]] + allowed_networks
    config_lines.append(f"AllowedIPs = {', '.join(all_networks)}")
    config_lines.append("PersistentKeepalive = 25")
    
    return "\n".join(config_lines)


def remove_interface(vpn_network_id: str) -> str:
    """Remove interface WireGuard"""
    interface_name = get_interface_name(vpn_network_id)
    config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
    
    # Desativar interface
    execute_command(f"wg-quick down {interface_name}", check=False)
    
    # Remover arquivo
    if os.path.exists(config_path):
        os.remove(config_path)
        logger.info(f"Arquivo de configuração removido: {config_path}")
    
    return interface_name

