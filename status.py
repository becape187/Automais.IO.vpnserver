"""
Status e monitoramento do WireGuard
"""
import logging
from typing import Dict, Any
from datetime import datetime
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
                        endpoint = parts[2] if parts[2] != '(none)' and parts[2] else None
                        allowed_ips_str = parts[3] if len(parts) > 3 else ""
                        latest_handshake = parts[4] if len(parts) > 4 and parts[4] != '0' else None
                        
                        # Transfer pode estar em bytes (números grandes)
                        transfer_rx = 0
                        transfer_tx = 0
                        try:
                            if len(parts) > 5 and parts[5]:
                                transfer_rx = int(parts[5])
                        except (ValueError, IndexError):
                            pass
                        try:
                            if len(parts) > 6 and parts[6]:
                                transfer_tx = int(parts[6])
                        except (ValueError, IndexError):
                            pass
                        
                        # Determinar status baseado no handshake
                        status = "offline"
                        handshake_datetime = None
                        if latest_handshake and latest_handshake != '0':
                            try:
                                handshake_timestamp = int(latest_handshake)
                                if handshake_timestamp > 0:
                                    handshake_datetime = datetime.fromtimestamp(handshake_timestamp).isoformat()
                                    # Considerar online se handshake foi nos últimos 2 minutos
                                    if datetime.utcnow().timestamp() - handshake_timestamp < 120:
                                        status = "online"
                            except (ValueError, TypeError):
                                pass
                        
                        peer = {
                            "public_key": public_key,
                            "allowed_ips": [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()],
                            "latest_handshake": handshake_datetime,
                            "transfer_rx": transfer_rx,
                            "transfer_tx": transfer_tx,
                            "endpoint": endpoint,
                            "status": status
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

