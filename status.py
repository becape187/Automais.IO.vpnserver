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
            # Parsear saída do dump (formato: interface\tpublic_key\tlisten_port\tfwmark)
            # e depois peers (formato: interface\tpublic_key\tendpoint\tallowed_ips\tlatest_handshake\ttransfer_rx\ttransfer_tx\tpersistent_keepalive)
            lines = stdout.strip().split('\n')
            current_interface = None
            
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2:
                    interface_name = parts[0]
                    public_key = parts[1]
                    
                    # Se é uma linha de interface (tem listen_port)
                    if len(parts) >= 3 and parts[2].isdigit():
                        listen_port = int(parts[2])
                        if interface_name not in interfaces_dict:
                            interfaces_dict[interface_name] = {
                                "name": interface_name,
                                "public_key": public_key,
                                "listen_port": listen_port,
                                "peers": []
                            }
                        current_interface = interface_name
                    # Se é uma linha de peer (tem endpoint ou allowed_ips)
                    elif current_interface and len(parts) >= 4:
                        endpoint = parts[2] if parts[2] != '(none)' else None
                        allowed_ips_str = parts[3] if len(parts) > 3 else ""
                        latest_handshake = parts[4] if len(parts) > 4 and parts[4] != '0' else None
                        transfer_rx = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0
                        transfer_tx = int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 0
                        
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
                            except:
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

