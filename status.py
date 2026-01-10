"""
Status e monitoramento do WireGuard
"""
import os
import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from config import WIREGUARD_CONFIG_DIR
from utils import execute_command, format_bytes

logger = logging.getLogger(__name__)


async def get_wireguard_status() -> Dict[str, Any]:
    """Obtém status completo de todas as interfaces WireGuard"""
    interfaces = []
    interfaces_dict: Dict[str, Dict[str, Any]] = {}
    
    try:
        # Usar wg show all dump para obter dados estruturados
        # NOTA: O wg show all dump tem um bug conhecido onde o timestamp do handshake não é atualizado corretamente
        # Vamos usar wg show <interface> para obter handshake atualizado depois
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
                
                # Peer pode ter 8 ou 9 campos dependendo da versão do WireGuard
                # Formato pode ser: interface, public_key, endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive
                # Ou: interface, public_key, (none), endpoint, allowed_ips, latest_handshake, transfer_rx, transfer_tx, persistent_keepalive
                elif len(parts) >= 8:
                    # Log para debug - verificar ordem dos campos (INFO para ver melhor)
                    logger.info(f"🔍 Parseando peer: {len(parts)} campos")
                    for idx, part in enumerate(parts[:8]):
                        # Verificar se é um timestamp válido
                        is_timestamp = False
                        if part.strip().isdigit():
                            try:
                                ts = int(part.strip())
                                if ts >= 1000000000 and ts <= 9999999999:
                                    current_ts = datetime.utcnow().timestamp()
                                    diff = current_ts - ts
                                    is_timestamp = True
                                    logger.info(f"  Campo {idx}: '{part}' ⏰ TIMESTAMP (diferença: {diff:.1f}s = {diff/60:.1f}min)")
                                else:
                                    logger.info(f"  Campo {idx}: '{part}' (número, mas não timestamp válido)")
                            except:
                                logger.info(f"  Campo {idx}: '{part}'")
                        else:
                            logger.info(f"  Campo {idx}: '{part}'")
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
                        
                        # Baseado no dump real do WireGuard:
                        # Campo 0: interface (wg-7464f4d4)
                        # Campo 1: public_key do peer
                        # Campo 2: (none) ou endpoint
                        # Campo 3: endpoint real (se campo 2 for (none))
                        # Campo 4: allowed_ips (10.222.111.2/24 - IP do router, não da rede!)
                        # Campo 5: latest_handshake (timestamp Unix)
                        # Campo 6: transfer_rx (bytes recebidos)
                        # Campo 7: transfer_tx (bytes enviados)
                        # Campo 8: persistent_keepalive (off ou número)
                        
                        # Endpoint: pode estar no campo 2 ou 3
                        if len(parts) > 2:
                            if parts[2] == '(none)' and len(parts) > 3:
                                # Se campo 2 é (none), endpoint está no campo 3
                                endpoint = parts[3] if ':' in parts[3] else None
                            elif ':' in parts[2] and parts[2] != '(none)':
                                endpoint = parts[2]
                        
                        # Allowed IPs: campo 4 (contém o IP do router, ex: 10.222.111.2/24)
                        if len(parts) > 4:
                            allowed_ips_str = parts[4].strip()
                        
                        # Latest handshake: campo 5
                        if len(parts) > 5:
                            latest_handshake_str = parts[5].strip() if parts[5].strip() else None
                        
                        # Transfer RX: campo 6
                        if len(parts) > 6:
                            try:
                                transfer_rx = int(parts[6]) if parts[6].strip() else 0
                            except (ValueError, IndexError):
                                pass
                        
                        # Transfer TX: campo 7
                        if len(parts) > 7:
                            try:
                                transfer_tx = int(parts[7]) if parts[7].strip() else 0
                            except (ValueError, IndexError):
                                pass
                        
                        # Log para verificar o timestamp (apenas se muito antigo)
                        if latest_handshake_str:
                            try:
                                ts = int(latest_handshake_str)
                                current_ts = datetime.utcnow().timestamp()
                                diff = current_ts - ts
                                # Só logar se muito antigo para não poluir logs
                                if diff > 300:
                                    logger.warning(f"⚠️ Timestamp do handshake está muito antigo ({diff/60:.1f}min). O peer pode estar realmente offline ou há um problema com o WireGuard.")
                            except:
                                pass
                        
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
                        # Lógica: Se handshake foi há menos de 180 segundos (3 minutos), está ONLINE
                        # IMPORTANTE: O wg show all dump tem um bug onde o timestamp não é atualizado
                        # Vamos usar wg show <interface> para obter o handshake atualizado
                        status = "offline"
                        handshake_datetime = None
                        handshake_timestamp = None
                        
                        # Tentar obter handshake atualizado via wg show (mais confiável)
                        updated_handshake = _get_handshake_from_wg_show(current_interface, public_key)
                        if updated_handshake:
                            handshake_timestamp = updated_handshake
                            logger.info(f"✅ Handshake atualizado via wg show: {handshake_timestamp}")
                        elif latest_handshake_str and latest_handshake_str != '0' and latest_handshake_str.strip():
                            # Fallback: usar timestamp do dump (pode estar desatualizado)
                            try:
                                handshake_timestamp = int(latest_handshake_str)
                                logger.warning(f"⚠️ Usando timestamp do dump (pode estar desatualizado): {handshake_timestamp}")
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Erro ao processar handshake '{latest_handshake_str}': {e}")
                                pass
                        
                        if handshake_timestamp and handshake_timestamp > 0:
                            # Converter timestamp Unix para datetime UTC em formato ISO 8601
                            # IMPORTANTE: Usar timezone.utc explicitamente para garantir conversão correta
                            # O timestamp Unix é sempre em UTC, então a conversão deve estar correta
                            handshake_utc = datetime.fromtimestamp(handshake_timestamp, tz=timezone.utc)
                            # Garantir formato ISO 8601 correto com 'Z' para indicar UTC
                            handshake_datetime = handshake_utc.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
                            
                            # Log para debug - verificar timestamp e conversão
                            current_utc = datetime.now(timezone.utc)
                            logger.info(
                                f"🕐 Handshake: timestamp={handshake_timestamp}, "
                                f"UTC={handshake_utc.strftime('%Y-%m-%d %H:%M:%S')}, "
                                f"ISO={handshake_datetime}, "
                                f"Current UTC={current_utc.strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            # Considerar online se handshake foi nos últimos 3 minutos (mais tolerante)
                            # Usar timezone UTC explicitamente
                            current_timestamp = datetime.now(timezone.utc).timestamp()
                            time_diff = current_timestamp - handshake_timestamp
                            
                            # Log detalhado para debug (INFO para ver melhor)
                            logger.info(f"Peer {public_key[:16]}... handshake: ts={handshake_timestamp}, current={current_timestamp:.0f}, diff={time_diff:.1f}s")
                            
                            # Se a diferença for negativa, o timestamp está no futuro (erro)
                            if time_diff < 0:
                                logger.warning(f"Peer {public_key[:16]}... timestamp do handshake está no futuro! ts={handshake_timestamp}, current={current_timestamp:.0f}")
                                status = "offline"
                            # Se handshake foi há menos de 180 segundos (3 minutos), está ONLINE
                            elif time_diff < 180:  # 3 minutos (180 segundos)
                                status = "online"
                                logger.info(f"✅ Peer {public_key[:16]}... ONLINE: handshake há {time_diff:.1f}s")
                            else:
                                # Converter para minutos e segundos para log mais legível
                                minutes = int(time_diff // 60)
                                seconds = int(time_diff % 60)
                                logger.info(f"❌ Peer {public_key[:16]}... OFFLINE: handshake há {minutes}m {seconds}s ({time_diff:.0f}s, limite: 180s)")
                        else:
                            logger.info(f"Peer {public_key[:16]}... sem handshake válido")
                        
                        # Buscar informações do peer - priorizar cache em memória, depois arquivo de config
                        from peer_cache import get_peer_info
                        peer_info = get_peer_info(public_key)
                        
                        # Se não encontrou no cache, tentar arquivo de configuração
                        if not peer_info or not peer_info.get("router_name"):
                            peer_info = _get_peer_info_from_config(current_interface, public_key)
                            # Se encontrou no arquivo, atualizar o cache
                            if peer_info and peer_info.get("router_name"):
                                from peer_cache import set_peer_info
                                set_peer_info(
                                    public_key=public_key,
                                    router_id=peer_info.get("router_id"),
                                    router_name=peer_info.get("router_name"),
                                    vpn_network_id=peer_info.get("vpn_network_id"),
                                    vpn_network_name=peer_info.get("vpn_network_name"),
                                    peer_ip=peer_info.get("peer_ip")
                                )
                        
                        # Extrair IP do peer - priorizar cache/config, senão usar allowed_ips
                        # IMPORTANTE: O allowed_ips do dump contém o IP do router (ex: 10.222.111.2/24), não o IP da rede
                        peer_ip = peer_info.get("peer_ip")
                        if not peer_ip and allowed_ips_str:
                            # Pegar o primeiro IP da lista
                            first_ip = allowed_ips_str.split(',')[0].strip()
                            # Remover o prefixo CIDR se houver (ex: 10.222.111.2/24 -> 10.222.111.2)
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


def _get_handshake_from_wg_show(interface_name: str, public_key: str) -> Optional[int]:
    """Obtém o timestamp do handshake usando wg show (mais confiável que dump)"""
    try:
        # Usar wg show <interface> para obter handshake atualizado
        stdout, _, returncode = execute_command(f"wg show {interface_name}", check=False)
        if returncode != 0:
            return None
        
        # Procurar o peer pela public_key e extrair o handshake
        lines = stdout.strip().split('\n')
        in_peer_section = False
        for line in lines:
            if public_key in line:
                in_peer_section = True
            elif in_peer_section and 'latest handshake:' in line.lower():
                # Formato: "  latest handshake: 3 seconds ago" ou "  latest handshake: 1 minute, 34 seconds ago"
                import re
                # Tentar extrair "X seconds ago" ou "X minutes, Y seconds ago"
                match = re.search(r'(\d+)\s+seconds?\s+ago', line.lower())
                if match:
                    seconds_ago = int(match.group(1))
                    # Usar timezone UTC explicitamente para garantir cálculo correto
                    current_ts = datetime.now(timezone.utc).timestamp()
                    handshake_ts = int(current_ts - seconds_ago)
                    logger.debug(f"Handshake atualizado via wg show: {seconds_ago}s atrás = timestamp {handshake_ts}")
                    return handshake_ts
                else:
                    # Tentar "X minutes, Y seconds ago"
                    match = re.search(r'(\d+)\s+minutes?,\s+(\d+)\s+seconds?\s+ago', line.lower())
                    if match:
                        minutes_ago = int(match.group(1))
                        seconds_ago = int(match.group(2))
                        total_seconds = minutes_ago * 60 + seconds_ago
                        # Usar timezone UTC explicitamente para garantir cálculo correto
                        current_ts = datetime.now(timezone.utc).timestamp()
                        handshake_ts = int(current_ts - total_seconds)
                        logger.debug(f"Handshake atualizado via wg show: {minutes_ago}m {seconds_ago}s atrás = timestamp {handshake_ts}")
                        return handshake_ts
            elif in_peer_section and line.strip().startswith('peer:'):
                # Próximo peer, parar busca
                break
    except Exception as e:
        logger.debug(f"Erro ao obter handshake via wg show: {e}")
    return None


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
        # Pode ter Peer IP nos comentários também
        pattern = rf'# Router: (.+?)\n.*?# Router ID: (.+?)\n.*?# VPN Network: (.+?)\n.*?# VPN Network ID: (.+?)\n.*?(?:# Peer IP: ([^\n]+)\n)?.*?\[Peer\].*?PublicKey = {re.escape(public_key)}.*?AllowedIPs = ([^\n]+)'
        match = re.search(pattern, content, re.DOTALL)
        
        peer_ip = None
        if match:
            # Tentar extrair o IP dos comentários primeiro (mais confiável)
            if len(match.groups()) >= 5 and match.group(5):
                peer_ip = match.group(5).strip()
            else:
                # Fallback: extrair do AllowedIPs
                allowed_ips_line = match.group(6).strip() if len(match.groups()) >= 6 else ""
                if allowed_ips_line:
                    # Pegar o primeiro IP da lista
                    first_ip = allowed_ips_line.split(',')[0].strip()
                    # Remover o prefixo CIDR se houver
                    if '/' in first_ip:
                        peer_ip = first_ip.split('/')[0].strip()
                    else:
                        peer_ip = first_ip
            
            result = {
                "router_name": match.group(1).strip() if match.group(1) else None,
                "router_id": match.group(2).strip() if match.group(2) else None,
                "vpn_network_name": match.group(3).strip() if match.group(3) else None,
                "vpn_network_id": match.group(4).strip() if match.group(4) else None
            }
            if peer_ip:
                result["peer_ip"] = peer_ip
            return result
    except Exception as e:
        logger.debug(f"Erro ao ler informações do peer do arquivo de config: {e}")
    
    return {}

