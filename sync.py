"""
Sincronização de recursos com a API C#
"""
import os
import httpx
import logging
from typing import Dict, Any, List
from datetime import datetime
from config import VPN_SERVER_ENDPOINT, API_C_SHARP_URL, SYNC_INTERVAL_SECONDS, WIREGUARD_CONFIG_DIR
from wireguard import get_interface_name, remove_interface, ensure_interface_exists, add_peer_to_interface, rebuild_interface_config
from utils import execute_command

logger = logging.getLogger(__name__)

# Cache de recursos gerenciados por esta instância
managed_resources: Dict[str, Any] = {
    "vpn_networks": [],
    "routers": [],
    "last_sync": None
}


async def sync_resources_from_api():
    """Sincroniza recursos (VpnNetworks e Routers) da API C#"""
    if not VPN_SERVER_ENDPOINT:
        logger.warning("VPN_SERVER_ENDPOINT não configurado. Não é possível sincronizar recursos.")
        return
    
    try:
        # Configurar cliente HTTP
        # Se usar HTTPS com certificado auto-assinado, pode precisar de verify=False
        # ATENÇÃO: verify=False desabilita verificação SSL (não recomendado para produção)
        verify_ssl = os.getenv("API_C_SHARP_VERIFY_SSL", "true").lower() == "true"
        
        async with httpx.AsyncClient(
            timeout=30.0,
            verify=verify_ssl  # Verificar certificado SSL
        ) as client:
            response = await client.get(
                f"{API_C_SHARP_URL}/api/vpn/networks/{VPN_SERVER_ENDPOINT}/resources",
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 404:
                logger.warning(f"Nenhuma VpnNetwork encontrada com endpoint '{VPN_SERVER_ENDPOINT}' na API principal")
                # Limpar tudo se o servidor não existe
                await cleanup_all_interfaces()
                managed_resources["vpn_networks"] = []
                managed_resources["routers"] = []
                managed_resources["last_sync"] = datetime.utcnow().isoformat()
                return
            
            if response.status_code != 200:
                logger.error(f"Erro ao consultar recursos: {response.status_code} - {response.text}")
                return
            
            data = response.json()
            new_vpn_networks = data.get("vpn_networks", [])
            new_routers = data.get("routers", [])
            
            # Fazer sincronização completa (de-para)
            await sync_interfaces_with_vpns(new_vpn_networks)
            
            # Sincronizar peers dos routers
            await sync_peers_with_routers(new_routers, new_vpn_networks)
            
            # Atualizar cache
            managed_resources["vpn_networks"] = new_vpn_networks
            managed_resources["routers"] = new_routers
            managed_resources["last_sync"] = datetime.utcnow().isoformat()
            
            logger.info(
                f"✅ Recursos sincronizados: {len(managed_resources['vpn_networks'])} VPNs, "
                f"{len(managed_resources['routers'])} Routers"
            )
            
    except httpx.TimeoutException:
        logger.error(f"⏱️ Timeout ao consultar API principal: {API_C_SHARP_URL}")
        logger.error(f"   Verifique se a API C# está acessível e respondendo")
    except httpx.ConnectError as e:
        logger.error(f"🔌 Erro de conexão com API principal: {API_C_SHARP_URL}")
        logger.error(f"   Detalhes: {e}")
        logger.error(f"   Verifique se:")
        logger.error(f"   - A API C# está rodando (systemctl status automais-api.service)")
        logger.error(f"   - A URL está correta no vpnserver.env")
        logger.error(f"   - O firewall não está bloqueando a porta")
    except httpx.HTTPStatusError as e:
        logger.error(f"📡 Erro HTTP {e.response.status_code} ao consultar API: {e.response.url}")
        logger.error(f"   Resposta: {e.response.text[:200]}")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar recursos: {type(e).__name__}: {e}")
        logger.error(f"   URL tentada: {API_C_SHARP_URL}/api/vpn/networks/{VPN_SERVER_ENDPOINT}/resources")


def is_resource_managed(resource_id: str, resource_type: str = "vpn_network") -> bool:
    """Verifica se um recurso é gerenciado por esta instância"""
    if resource_type == "vpn_network":
        return any(vpn["id"] == resource_id for vpn in managed_resources["vpn_networks"])
    elif resource_type == "router":
        return any(router["id"] == resource_id for router in managed_resources["routers"])
    return False


def get_managed_resources() -> Dict[str, Any]:
    """Retorna recursos gerenciados"""
    return managed_resources


async def get_existing_interfaces() -> List[str]:
    """Lista todas as interfaces WireGuard existentes no sistema"""
    try:
        stdout, stderr, returncode = execute_command("wg show interfaces", check=False)
        if returncode != 0:
            return []
        
        interfaces = [name.strip() for name in stdout.strip().split('\n') if name.strip()]
        return interfaces
    except Exception as e:
        logger.error(f"Erro ao listar interfaces WireGuard: {e}")
        return []


async def sync_interfaces_with_vpns(vpn_networks: List[Dict[str, Any]]) -> None:
    """
    Sincronização completa: garante que interfaces WireGuard correspondem exatamente às VPNs retornadas pela API.
    
    - Se VPN existe na API mas não tem interface → CRIA interface
    - Se interface existe mas VPN não está na API → REMOVE interface
    - Se não há VPNs na API → REMOVE todas as interfaces
    """
    try:
        # Se não há VPNs na API, remover todas as interfaces
        if not vpn_networks:
            logger.warning("⚠️ Nenhuma VPN na API. Removendo todas as interfaces WireGuard...")
            await cleanup_all_interfaces()
            return
        # Obter interfaces existentes no sistema
        existing_interfaces = await get_existing_interfaces()
        
        # Mapear interfaces existentes para VPN IDs
        # Formato: {vpn_id: interface_name}
        existing_vpn_to_interface: Dict[str, str] = {}
        
        for interface_name in existing_interfaces:
            if not interface_name.startswith("wg-"):
                continue
            
            # Extrair ID curto da interface (wg-7464f4d4 -> 7464f4d4)
            interface_short_id = interface_name.replace("wg-", "")
            
            # Tentar encontrar VPN correspondente
            for vpn in vpn_networks:
                vpn_id_short = vpn["id"].replace("-", "")[:8]
                if interface_short_id == vpn_id_short:
                    existing_vpn_to_interface[vpn["id"]] = interface_name
                    break
        
        # Criar conjunto de VPN IDs da API
        api_vpn_ids = {vpn["id"] for vpn in vpn_networks}
        
        # 1. REMOVER: Interfaces que existem mas não estão na API
        interfaces_to_remove = []
        for vpn_id, interface_name in existing_vpn_to_interface.items():
            if vpn_id not in api_vpn_ids:
                interfaces_to_remove.append((vpn_id, interface_name))
        
        if interfaces_to_remove:
            logger.info(f"🗑️ Removendo {len(interfaces_to_remove)} interface(s) que não estão mais na API")
            for vpn_id, interface_name in interfaces_to_remove:
                try:
                    remove_interface(vpn_id)
                    logger.info(f"✅ Interface {interface_name} removida (VPN {vpn_id} não está mais na API)")
                except Exception as e:
                    logger.error(f"❌ Erro ao remover interface {interface_name} (VPN {vpn_id}): {e}")
        
        # 2. REMOVER: Interfaces órfãs (que não correspondem a nenhuma VPN)
        orphan_interfaces = []
        for interface_name in existing_interfaces:
            if not interface_name.startswith("wg-"):
                continue
            
            # Verificar se esta interface corresponde a alguma VPN
            interface_short_id = interface_name.replace("wg-", "")
            is_orphan = True
            
            for vpn in vpn_networks:
                vpn_id_short = vpn["id"].replace("-", "")[:8]
                if interface_short_id == vpn_id_short:
                    is_orphan = False
                    break
            
            if is_orphan:
                orphan_interfaces.append(interface_name)
        
        if orphan_interfaces:
            logger.info(f"🗑️ Removendo {len(orphan_interfaces)} interface(s) órfã(s)")
            for interface_name in orphan_interfaces:
                try:
                    execute_command(f"wg-quick down {interface_name}", check=False)
                    config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
                    if os.path.exists(config_path):
                        os.remove(config_path)
                        logger.info(f"✅ Arquivo removido: {config_path}")
                    logger.info(f"✅ Interface órfã {interface_name} removida")
                except Exception as e:
                    logger.error(f"❌ Erro ao remover interface órfã {interface_name}: {e}")
        
        # 3. CRIAR: VPNs que estão na API mas não têm interface
        vpns_to_create = []
        for vpn in vpn_networks:
            vpn_id = vpn["id"]
            if vpn_id not in existing_vpn_to_interface:
                vpns_to_create.append(vpn)
        
        if vpns_to_create:
            logger.info(f"➕ Criando {len(vpns_to_create)} interface(s) para VPN(s) da API")
            for vpn in vpns_to_create:
                try:
                    interface_name = await ensure_interface_exists(vpn)
                    logger.info(f"✅ Interface {interface_name} criada para VPN {vpn['id']}")
                except Exception as e:
                    logger.error(f"❌ Erro ao criar interface para VPN {vpn['id']}: {e}")
        
        # Resumo
        if not interfaces_to_remove and not orphan_interfaces and not vpns_to_create:
            logger.info("✅ Sincronização completa: tudo está em ordem")
        else:
            logger.info(
                f"📊 Sincronização completa: "
                f"{len(interfaces_to_remove) + len(orphan_interfaces)} removida(s), "
                f"{len(vpns_to_create)} criada(s)"
            )
            
    except Exception as e:
        logger.error(f"Erro ao sincronizar interfaces com VPNs: {e}")


async def get_existing_peers(interface_name: str) -> List[str]:
    """Lista chaves públicas dos peers existentes em uma interface WireGuard"""
    try:
        stdout, stderr, returncode = execute_command(f"wg show {interface_name}", check=False)
        if returncode != 0:
            return []
        
        # Parsear saída do wg show para extrair chaves públicas dos peers
        # Formato: peer <public_key>
        #          endpoint: ...
        #          allowed ips: ...
        peer_keys = []
        lines = stdout.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('peer '):
                # Extrair chave pública (peer <key>)
                parts = line.split()
                if len(parts) >= 2:
                    peer_keys.append(parts[1])
        
        return peer_keys
    except Exception as e:
        logger.error(f"Erro ao listar peers da interface {interface_name}: {e}")
        return []


async def sync_peers_with_routers(routers: List[Dict[str, Any]], vpn_networks: List[Dict[str, Any]]) -> None:
    """
    Sincroniza peers dos routers com as interfaces WireGuard.
    
    RECONSTRÓI o arquivo completo do zero para cada VPN Network e compara com o arquivo atual.
    Só atualiza se houver diferenças, garantindo formatação correta.
    """
    try:
        # Criar mapeamento de VPN ID para interface name
        vpn_to_interface: Dict[str, str] = {}
        for vpn in vpn_networks:
            interface_name = get_interface_name(vpn["id"])
            # Verificar se interface existe
            stdout, _, returncode = execute_command(f"wg show {interface_name}", check=False)
            if returncode == 0:
                vpn_to_interface[vpn["id"]] = interface_name
        
        if not vpn_to_interface:
            logger.debug("Nenhuma interface WireGuard ativa encontrada para sincronizar peers")
            return
        
        total_files_updated = 0
        total_peers_count = 0
        
        # Para cada VPN Network, reconstruir o arquivo completo
        for vpn_network in vpn_networks:
            vpn_network_id = vpn_network["id"]
            
            if vpn_network_id not in vpn_to_interface:
                continue
            
            interface_name = vpn_to_interface[vpn_network_id]
            
            # Reconstruir arquivo completo
            was_updated = await rebuild_interface_config(vpn_network, routers)
            
            if was_updated:
                # Contar peers desta VPN
                peers_count = 0
                for router in routers:
                    if router.get("vpn_network_id") == vpn_network_id:
                        peers = router.get("peers", [])
                        for peer in peers:
                            if peer.get("is_enabled", True) and peer.get("public_key") and peer.get("allowed_ips"):
                                peers_count += 1
                
                # Quando houver mudança no arquivo, recarregar interface completamente com down/up
                # Isso garante que todas as mudanças sejam aplicadas corretamente
                try:
                    logger.info(f"🔄 Recarregando interface {interface_name} após atualização do arquivo...")
                    execute_command(f"wg-quick down {interface_name}", check=False)
                    execute_command(f"wg-quick up {interface_name}", check=False)
                    logger.info(f"✅ Interface {interface_name} recarregada com sucesso ({peers_count} peer(s))")
                    
                    total_files_updated += 1
                    total_peers_count += peers_count
                except Exception as e:
                    logger.error(f"❌ Erro ao recarregar interface {interface_name}: {e}")
        
        # Sincronizar cache em memória com dados da API
        from peer_cache import sync_from_api_data
        sync_from_api_data(routers, vpn_networks)
        
        if total_files_updated > 0:
            logger.info(
                f"📊 Sincronização completa: {total_files_updated} arquivo(s) atualizado(s) "
                f"com {total_peers_count} peer(s) no total"
            )
        else:
            logger.debug("✅ Sincronização completa: todos os arquivos já estão atualizados")
            
    except Exception as e:
        logger.error(f"Erro ao sincronizar peers com routers: {e}")


async def cleanup_orphan_interfaces(managed_vpn_ids: set) -> None:
    """Remove interfaces WireGuard que não correspondem a VPNs gerenciadas"""
    try:
        existing_interfaces = await get_existing_interfaces()
        if not existing_interfaces:
            return
        
        # Se não há VPNs gerenciadas, todas as interfaces são órfãs
        if not managed_vpn_ids:
            logger.info("Nenhuma VPN gerenciada. Todas as interfaces serão removidas.")
            return
        
        # Para cada interface existente, verificar se corresponde a uma VPN gerenciada
        for interface_name in existing_interfaces:
            # Interfaces WireGuard criadas por este serviço seguem o padrão wg-{8_chars}
            if not interface_name.startswith("wg-"):
                continue
            
            # Extrair os primeiros 8 caracteres do nome da interface
            interface_short_id = interface_name.replace("wg-", "")
            
            # Verificar se existe uma VPN gerenciada que corresponde a esta interface
            interface_belongs_to_managed_vpn = False
            for vpn_id in managed_vpn_ids:
                vpn_id_short = vpn_id.replace("-", "")[:8]
                if interface_short_id == vpn_id_short:
                    interface_belongs_to_managed_vpn = True
                    break
            
            # Se não encontrou VPN correspondente, é uma interface órfã
            if not interface_belongs_to_managed_vpn:
                logger.warning(f"🗑️ Interface órfã detectada: {interface_name}. Removendo...")
                try:
                    # Desativar interface
                    execute_command(f"wg-quick down {interface_name}", check=False)
                    
                    # Remover arquivo de configuração
                    config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
                    if os.path.exists(config_path):
                        os.remove(config_path)
                        logger.info(f"✅ Arquivo removido: {config_path}")
                    
                    logger.info(f"✅ Interface {interface_name} removida (órfã)")
                except Exception as e:
                    logger.error(f"❌ Erro ao remover interface órfã {interface_name}: {e}")
    except Exception as e:
        logger.error(f"Erro ao limpar interfaces órfãs: {e}")


async def cleanup_all_interfaces() -> None:
    """Remove todas as interfaces WireGuard quando não há recursos gerenciados"""
    try:
        existing_interfaces = await get_existing_interfaces()
        if not existing_interfaces:
            logger.info("Nenhuma interface WireGuard encontrada para limpar")
            return
        
        logger.info(f"🗑️ Removendo {len(existing_interfaces)} interface(s) WireGuard...")
        
        for interface_name in existing_interfaces:
            if not interface_name.startswith("wg-"):
                continue
                
            try:
                # Desativar interface
                execute_command(f"wg-quick down {interface_name}", check=False)
                
                # Remover arquivo de configuração
                config_path = f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf"
                if os.path.exists(config_path):
                    os.remove(config_path)
                    logger.info(f"✅ Arquivo removido: {config_path}")
                
                logger.info(f"✅ Interface {interface_name} removida")
            except Exception as e:
                logger.error(f"❌ Erro ao remover interface {interface_name}: {e}")
        
        logger.info("✅ Limpeza completa de interfaces WireGuard concluída")
    except Exception as e:
        logger.error(f"Erro ao limpar todas as interfaces: {e}")

