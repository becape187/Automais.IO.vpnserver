"""
Status e monitoramento do WireGuard
"""
import os
import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from config import WIREGUARD_CONFIG_DIR
from utils import execute_command, format_bytes

logger = logging.getLogger(__name__)


async def get_wireguard_status() -> Dict[str, Any]:
    """Obtém status completo de todas as interfaces WireGuard"""
    interfaces = []
    interfaces_dict: Dict[str, Dict[str, Any]] = {}
    
    try:
        # Usar wg show all dump para obter dados estruturados
        stdout, stderr, returncode = execute_command("wg show all dump", check=False)
        if returncode != 0:
            # Fallback: tentar listar interfaces
            stdout, _, returncode = execute_command("wg show interfaces", check=False)
            if returncode != 0:
                return {
                    "interfaces": [],
                    "total_interfaces": 0,
                    "total_peers": 0,
                    "total_rx": 0,
                    "total_tx": 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            # Se não tem dump, usar método antigo
            interface_names = [name.strip() for name in stdout.strip().split('\n') if name.strip()]
            for interface_name in interface_names:
                interfaces_dict[interface_name] = {
                    "name": interface_name,
                    "public_key": "",
                    "listen_port": 0,
                    "peers": []
                }
        else:
            # Parsear saída do dump
            # Formato interface: interface_name\tpublic_key\tlisten_port\tfwmark (4 campos)
            # Formato peer: interface_name\tpublic_key\tendpoint\tallowed_ips\tlatest_handshake\ttransfer_rx\ttransfer_tx\tpersistent_keepalive (8 campos)
            lines = stdout.strip().split('\n')
            current_interface = None
            
            for line in lines:
                if not line.strip():
                    continue
                    
                parts = line.split('\t')
                if len(parts) < 2:
                    continue
                    
                interface_name = parts[0]
                public_key = parts[1]
                
                # Interface tem 4 campos: interface, public_key, listen_port, fwmark
                if len(parts) == 4:
                    try:
                        listen_port = int(parts[2]) if parts[2].isdigit() else 0
                        if interface_name not in interfaces_dict:
                            interfaces_dict[interface_name] = {
                                "name": interface_name,
                                "public_key": public_key,
                                "listen_port": listen_port,
                                "peers": []
                            }
                        current_interface = interface_name
                    except (ValueError, IndexError):
                        logger.warning(f"Erro ao parsear linha de interface: {line}")
                        continue
                
                # Peer tem 8 campos: interface, public_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive
                elif len(parts) >= 8:
                    # Log para debug - verificar ordem dos campos
                    logger.debug(f"Parseando peer: {len(parts)} campos - {parts[:8]}")
                    # Se não há interface atual, criar uma (pode acontecer se peer aparecer antes da interface)
                    if interface_name not in interfaces_dict:
                        interfaces_dict[interface_name] = {
                            "name": interface_name,
                            "public_key": "",  # Interface não tem public_key própria no dump do peer
                            "listen_port": 51820,  # Porta padrão
                            "peers": []
                        }
                    current_interface = interface_name
                    try:
                        # Formato peer: interface, public_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive
                        # Mas pode haver variações - vamos detectar automaticamente
                        endpoint = None
                        allowed_ips_str = ""
                        latest_handshake_str = None
                        transfer_rx = 0
                        transfer_tx = 0
                        
                        # Procurar o endpoint (geralmente tem :porta ou é (none))
                        for i in range(2, min(8, len(parts))):
                            if parts[i] == '(none)' or (':' in parts[i] and not parts[i].startswith('10.')):
                                endpoint = parts[i] if parts[i] != '(none)' else None
                                break
                        
                        # Procurar allowed_ips (contém / ou é um IP com .)
                        for i in range(2, min(8, len(parts))):
                            if '/' in parts[i] or ('.' in parts[i] and not ':' in parts[i] and not parts[i].isdigit()):
                                allowed_ips_str = parts[i].strip()
                                break
                        
                        # Procurar latest_handshake (número grande, timestamp Unix)
                        for i in range(2, min(8, len(parts))):
                            candidate = parts[i].strip()
                            # Timestamp Unix é um número grande (10 dígitos ou mais)
                            if candidate and candidate.isdigit() and len(candidate) >= 9:
                                latest_handshake_str = candidate
                                # Se encontramos o handshake, os próximos campos são transfer_rx e transfer_tx
                                if i + 1 < len(parts):
                                    try:
                                        transfer_rx = int(parts[i + 1]) if parts[i + 1].strip() else 0
                                    except (ValueError, IndexError):
                                        pass
                                if i + 2 < len(parts):
                                    try:
                                        transfer_tx = int(parts[i + 2]) if parts[i + 2].strip() else 0
                                    except (ValueError, IndexError):
                                        pass
                                break
                        
                        # Fallback: se não encontramos, usar ordem padrão
                        if not latest_handshake_str and len(parts) >= 8:
                            endpoint = parts[2] if len(parts) > 2 and parts[2] != '(none)' and parts[2].strip() else None
                            allowed_ips_str = parts[3] if len(parts) > 3 and parts[3].strip() else ""
                            latest_handshake_str = parts[4] if len(parts) > 4 and parts[4].strip() else None
                            try:
                                if len(parts) > 5 and parts[5].strip():
                                    transfer_rx = int(parts[5])
                            except (ValueError, IndexError):
                                pass
                            try:
                                if len(parts) > 6 and parts[6].strip():
                                    transfer_tx = int(parts[6])
                            except (ValueError, IndexError):
                                pass
                        
                        # Determinar status baseado no handshake
                        status = "offline"
                        handshake_datetime = None
                        if latest_handshake_str and latest_handshake_str != '0' and latest_handshake_str.strip():
                            try:
                                handshake_timestamp = int(latest_handshake_str)
                                if handshake_timestamp > 0:
                                    # Converter timestamp Unix para datetime UTC
                                    handshake_datetime = datetime.utcfromtimestamp(handshake_timestamp).isoformat() + 'Z'
                                    # Considerar online se handshake foi nos últimos 3 minutos (mais tolerante)
                                    current_timestamp = datetime.utcnow().timestamp()
                                    time_diff = current_timestamp - handshake_timestamp
                                    if time_diff >= 0 and time_diff < 180:  # 3 minutos (180 segundos)
                                        status = "online"
                                        logger.debug(f"Peer {public_key[:16]}... ONLINE: handshake há {time_diff:.1f}s")
                                    else:
                                        logger.info(f"Peer {public_key[:16]}... OFFLINE: handshake há {time_diff:.0f}s (limite: 180s)")
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Erro ao processar handshake '{latest_handshake_str}': {e}")
                                pass
                        else:
                            logger.info(f"Peer {public_key[:16]}... sem handshake válido: '{latest_handshake_str}'")
                        
                        # Buscar informações do router/VPN do arquivo de configuração
                        peer_info = _get_peer_info_from_config(current_interface, public_key)
                        
                        # Extrair IP do peer - priorizar o IP do arquivo de config, senão usar allowed_ips
                        peer_ip = peer_info.get("peer_ip")
                        if not peer_ip and allowed_ips_str:
                            # Pegar o primeiro IP da lista
                            first_ip = allowed_ips_str.split(',')[0].strip()
                            # Remover o prefixo CIDR se houver (ex: 10.222.111.0/24 -> 10.222.111.0)
                            if '/' in first_ip:
                                peer_ip = first_ip.split('/')[0].strip()
                            else:
                                peer_ip = first_ip
                        
                        # Log para debug
                        logger.debug(f"Peer parseado: key={public_key[:16]}..., endpoint={endpoint}, allowed_ips={allowed_ips_str}, peer_ip={peer_ip}, handshake={latest_handshake_str}, status={status}, rx={transfer_rx}, tx={transfer_tx}")
                        
                        peer = {
                            "public_key": public_key,
                            "allowed_ips": [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()],
                            "peer_ip": peer_ip,  # IP do peer sem CIDR
                            "latest_handshake": handshake_datetime,
                            "transfer_rx": transfer_rx,
                            "transfer_tx": transfer_tx,
                            "endpoint": endpoint,
                            "status": status,
                            "router_name": peer_info.get("router_name"),
                            "router_id": peer_info.get("router_id"),
                            "vpn_network_name": peer_info.get("vpn_network_name"),
                            "vpn_network_id": peer_info.get("vpn_network_id")
                        }
                        interfaces_dict[current_interface]["peers"].append(peer)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Erro ao parsear linha de peer: {line}, Erro: {e}")
                        continue
        
        # Converter dict para lista
        interfaces = list(interfaces_dict.values())
        
        # Calcular totais
        total_peers = sum(len(iface["peers"]) for iface in interfaces)
        total_rx = sum(sum(peer["transfer_rx"] for peer in iface["peers"]) for iface in interfaces)
        total_tx = sum(sum(peer["transfer_tx"] for peer in iface["peers"]) for iface in interfaces)
        
        return {
            "interfaces": interfaces,
            "total_interfaces": len(interfaces),
            "total_peers": total_peers,
            "total_rx": total_rx,
            "total_tx": total_tx,
            "total_rx_formatted": format_bytes(total_rx),
            "total_tx_formatted": format_bytes(total_tx),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter status WireGuard: {e}")
        return {
            "interfaces": [],
            "total_interfaces": 0,
            "total_peers": 0,
            "total_rx": 0,
            "total_tx": 0,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def _get_peer_info_from_config(interface_name: str, public_key: str) -> Dict[str, Optional[str]]:
    """Extrai informações do router/VPN dos comentários do arquivo de configuração"""
    config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Procurar o bloco de comentários antes do peer com esta public_key
        # Padrão: comentários antes de [Peer] seguido de PublicKey = {public_key}
        pattern = rf'# Router: (.+?)\n.*?# Router ID: (.+?)\n.*?# VPN Network: (.+?)\n.*?# VPN Network ID: (.+?)\n.*?\[Peer\].*?PublicKey = {re.escape(public_key)}.*?AllowedIPs = ([^\n]+)'
        match = re.search(pattern, content, re.DOTALL)
        
        peer_ip = None
        if match:
            # Tentar extrair o IP do AllowedIPs
            allowed_ips_line = match.group(5).strip() if len(match.groups()) >= 5 else ""
            if allowed_ips_line:
                # Pegar o primeiro IP da lista
                first_ip = allowed_ips_line.split(',')[0].strip()
                # Remover o prefixo CIDR se houver
                if '/' in first_ip:
                    peer_ip = first_ip.split('/')[0].strip()
                else:
                    peer_ip = first_ip
            
            result = {
                "router_name": match.group(1).strip(),
                "router_id": match.group(2).strip(),
                "vpn_network_name": match.group(3).strip(),
                "vpn_network_id": match.group(4).strip()
            }
            if peer_ip:
                result["peer_ip"] = peer_ip
            return result
    except Exception as e:
        logger.debug(f"Erro ao ler informações do peer do arquivo de config: {e}")
    
    return {}

