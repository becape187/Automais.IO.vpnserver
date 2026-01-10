"""
Serviço VPN - Gerenciamento Completo de WireGuard
Cada instância é isolada e consulta a API principal (C#) para descobrir seus recursos.
Gerencia interfaces, peers, chaves, IPs, firewall, etc.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Imports dos módulos
from config import VPN_SERVER_NAME, API_C_SHARP_URL, SYNC_INTERVAL_SECONDS, WIREGUARD_CONFIG_DIR, PORT
from models import (
    ProvisionPeerRequest, ProvisionPeerResponse,
    AddNetworkRequest, RemoveNetworkRequest,
    VpnConfigResponse, EnsureInterfaceRequest
)
from sync import sync_resources_from_api, is_resource_managed, get_managed_resources
from api_client import get_vpn_network_from_api, get_router_from_api, update_peer_in_api
from wireguard import (
    ensure_interface_exists, generate_wireguard_keys, allocate_vpn_ip,
    add_peer_to_interface, generate_router_config, get_interface_name, remove_interface
)
from status import get_wireguard_status
from dashboard import get_dashboard_html

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VPN Service - WireGuard Management",
    description=f"""
    Serviço Python para gerenciamento completo de WireGuard.
    
    **Instância:** {VPN_SERVER_NAME or 'Não configurado'}
    
    ## Características
    
    - ✅ Auto-descoberta de recursos via API C#
    - ✅ Gerenciamento de interfaces WireGuard
    - ✅ Provisionamento de peers
    - ✅ Geração de chaves
    - ✅ Alocação de IPs
    - ✅ Configuração de firewall (iptables)
    - ✅ Sincronização periódica
    
    ## Acesso à Documentação
    
    - **Swagger UI:** `/docs`
    - **ReDoc:** `/redoc`
    - **OpenAPI JSON:** `/openapi.json`
    """,
    version="1.0.0",
    contact={
        "name": "Automais.io",
        "url": "https://automais.io"
    }
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def background_sync_loop():
    """Loop em background para sincronizar recursos periodicamente"""
    logger.info(f"🔄 Iniciando loop de sincronização (intervalo: {SYNC_INTERVAL_SECONDS}s)")
    
    while True:
        try:
            await sync_resources_from_api()
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Erro no loop de sincronização: {e}")
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)


async def sync_existing_interfaces():
    """Sincroniza interfaces WireGuard existentes com o banco"""
    logger.info("Sincronizando interfaces WireGuard existentes...")
    # TODO: Implementar sincronização de interfaces existentes
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    logger.info(f"🚀 Iniciando serviço VPN - Instância: {VPN_SERVER_NAME}")
    await sync_resources_from_api()
    
    # Sincronizar interfaces existentes na inicialização
    await sync_existing_interfaces()
    
    sync_task = asyncio.create_task(background_sync_loop())
    
    yield
    
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    logger.info("🛑 Serviço VPN encerrado")


app.router.lifespan_context = lifespan


# ===== ENDPOINTS =====

@app.get("/", tags=["Status"])
async def root():
    """
    Endpoint raiz - Informações do serviço
    
    Retorna informações sobre o status do serviço e recursos gerenciados.
    """
    managed = get_managed_resources()
    return {
        "service": "vpn-service",
        "status": "running",
        "server_name": VPN_SERVER_NAME,
        "managed_resources": {
            "vpn_networks_count": len(managed["vpn_networks"]),
            "routers_count": len(managed["routers"]),
            "last_sync": managed["last_sync"]
        }
    }


@app.get("/health", tags=["Status"])
async def health():
    """
    Health check do serviço
    
    Verifica se o serviço está funcionando corretamente.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "server_name": VPN_SERVER_NAME,
        "api_url": API_C_SHARP_URL
    }


@app.get("/api/v1/vpn/resources", tags=["Recursos"])
async def get_managed_resources_endpoint():
    """
    Lista recursos gerenciados por esta instância
    
    Retorna a lista de VPN Networks e Routers que esta instância do serviço VPN gerencia,
    baseado no `VPN_SERVER_NAME` configurado.
    """
    managed = get_managed_resources()
    return {
        "server_name": VPN_SERVER_NAME,
        "vpn_networks": managed["vpn_networks"],
        "routers": managed["routers"],
        "last_sync": managed["last_sync"]
    }


@app.post("/api/v1/vpn/sync", tags=["Recursos"])
async def force_sync():
    """
    Força sincronização de recursos
    
    Força uma sincronização imediata com a API C# para atualizar a lista de recursos gerenciados.
    Normalmente a sincronização acontece automaticamente a cada `SYNC_INTERVAL_SECONDS`.
    """
    await sync_resources_from_api()
    managed = get_managed_resources()
    return {"status": "synced", "timestamp": managed["last_sync"]}


@app.post(
    "/api/v1/vpn/provision-peer",
    response_model=ProvisionPeerResponse,
    tags=["Peers"],
    summary="Provisiona peer WireGuard",
    description="""
    Provisiona um novo peer WireGuard para um router.
    
    Este endpoint:
    - Gera chaves WireGuard (pública e privada)
    - Aloca um IP na rede VPN
    - Cria/garante que a interface WireGuard existe
    - Adiciona o peer à interface
    - Configura firewall (iptables)
    - Retorna as chaves e configuração
    
    **Importante:** O router e a VPN Network devem ser gerenciados por esta instância.
    """
)
async def provision_peer(request: ProvisionPeerRequest):
    """
    Provisiona um peer WireGuard para um router
    
    - **router_id**: ID do router
    - **vpn_network_id**: ID da rede VPN
    - **allowed_networks**: Redes adicionais permitidas (opcional)
    - **manual_ip**: IP manual para o router (opcional, formato: IP/PREFIX)
    """
    if not is_resource_managed(request.vpn_network_id, "vpn_network"):
        raise HTTPException(
            status_code=403,
            detail=f"VPN Network {request.vpn_network_id} não é gerenciada por esta instância"
        )
    
    if not is_resource_managed(request.router_id, "router"):
        raise HTTPException(
            status_code=403,
            detail=f"Router {request.router_id} não é gerenciado por esta instância"
        )
    
    logger.info(f"Provisionando peer para router {request.router_id} na VPN {request.vpn_network_id}")
    
    # Buscar dados da API C#
    vpn_network = await get_vpn_network_from_api(request.vpn_network_id)
    router = await get_router_from_api(request.router_id)
    
    if not vpn_network or not router:
        raise HTTPException(status_code=404, detail="Router ou VpnNetwork não encontrados")
    
    # Garantir que interface existe
    interface_name = await ensure_interface_exists(vpn_network)
    
    # Gerar chaves WireGuard
    private_key, public_key = await generate_wireguard_keys()
    
    # Alocar IP
    router_ip = await allocate_vpn_ip(request.vpn_network_id, request.manual_ip)
    
    # Construir allowed-ips
    allowed_ips_list = [router_ip]
    if request.allowed_networks:
        allowed_ips_list.extend(request.allowed_networks)
    allowed_ips_str = ",".join(allowed_ips_list)
    
    # Adicionar peer à interface
    await add_peer_to_interface(interface_name, public_key, allowed_ips_str)
    
    # Gerar configuração para o router
    peer_data = {
        "private_key": private_key,
        "public_key": public_key,
        "allowed_ips": router_ip
    }
    config_content = await generate_router_config(router, peer_data, vpn_network, request.allowed_networks)
    
    # Atualizar no banco via API C#
    await update_peer_in_api({
        "router_id": request.router_id,
        "vpn_network_id": request.vpn_network_id,
        "public_key": public_key,
        "private_key": private_key,
        "allowed_ips": router_ip,
        "config_content": config_content
    })
    
    return ProvisionPeerResponse(
        router_id=request.router_id,
        vpn_network_id=request.vpn_network_id,
        public_key=public_key,
        private_key=private_key,
        allowed_ips=router_ip,
        interface_name=interface_name,
        status="provisioned"
    )


@app.get(
    "/api/v1/vpn/config/{router_id}",
    response_model=VpnConfigResponse,
    tags=["Configuração"],
    summary="Obtém configuração WireGuard",
    description="Retorna o arquivo de configuração WireGuard (.conf) para um router específico."
)
async def get_config(router_id: str):
    """
    Obtém a configuração WireGuard para um router
    
    - **router_id**: ID do router (UUID)
    
    Retorna o conteúdo do arquivo .conf e o nome sugerido para o arquivo.
    """
    if not is_resource_managed(router_id, "router"):
        raise HTTPException(status_code=403, detail=f"Router {router_id} não é gerenciado por esta instância")
    
    # Buscar peer do banco via API C#
    # TODO: Implementar endpoint na API C# para buscar peer
    router = await get_router_from_api(router_id)
    if not router:
        raise HTTPException(status_code=404, detail=f"Router {router_id} não encontrado")
    
    # Por enquanto, retornar placeholder
    return {
        "config_content": "# TODO: Buscar do banco via API C#",
        "filename": f"router_{router_id}.conf"
    }


@app.post(
    "/api/v1/vpn/ensure-interface",
    tags=["Interfaces"],
    summary="Garante interface WireGuard",
    description="""
    Garante que a interface WireGuard existe para uma VpnNetwork.
    
    Se a interface não existir:
    - Cria o arquivo de configuração
    - Gera chaves do servidor (se necessário)
    - Configura firewall (iptables)
    - Ativa a interface
    
    Se já existir, apenas verifica se está ativa.
    """
)
async def ensure_interface(request: EnsureInterfaceRequest):
    """
    Garante que a interface WireGuard existe para uma VpnNetwork
    
    - **vpn_network_id**: ID da rede VPN (UUID)
    """
    if not is_resource_managed(request.vpn_network_id, "vpn_network"):
        raise HTTPException(status_code=403, detail=f"VPN Network {request.vpn_network_id} não é gerenciada por esta instância")
    
    vpn_network = await get_vpn_network_from_api(request.vpn_network_id)
    if not vpn_network:
        raise HTTPException(status_code=404, detail=f"VpnNetwork {request.vpn_network_id} não encontrada")
    
    interface_name = await ensure_interface_exists(vpn_network)
    
    return {
        "vpn_network_id": request.vpn_network_id,
        "interface_name": interface_name,
        "config_path": f"{WIREGUARD_CONFIG_DIR}/{interface_name}.conf",
        "status": "ensured"
    }


@app.delete(
    "/api/v1/vpn/remove-interface",
    tags=["Interfaces"],
    summary="Remove interface WireGuard",
    description="Remove a interface WireGuard de uma VpnNetwork. Desativa a interface e remove o arquivo de configuração."
)
async def remove_interface_endpoint(request: EnsureInterfaceRequest):
    """
    Remove a interface WireGuard de uma VpnNetwork
    
    - **vpn_network_id**: ID da rede VPN (UUID)
    
    **Atenção:** Esta operação desativa a interface e remove todos os peers associados.
    """
    if not is_resource_managed(request.vpn_network_id, "vpn_network"):
        raise HTTPException(status_code=403, detail=f"VPN Network {request.vpn_network_id} não é gerenciada por esta instância")
    
    interface_name = remove_interface(request.vpn_network_id)
    
    return {
        "vpn_network_id": request.vpn_network_id,
        "interface_name": interface_name,
        "status": "removed"
    }


@app.post(
    "/api/v1/vpn/add-network",
    tags=["Redes"],
    summary="Adiciona rede permitida",
    description="Adiciona uma rede permitida (AllowedIPs) ao peer de um router."
)
async def add_network(request: AddNetworkRequest):
    """
    Adiciona uma rede permitida ao router
    
    - **router_id**: ID do router (UUID)
    - **network_cidr**: Rede em formato CIDR (ex: 10.0.0.0/8)
    - **description**: Descrição opcional da rede
    """
    if not is_resource_managed(request.router_id, "router"):
        raise HTTPException(status_code=403, detail=f"Router {request.router_id} não é gerenciado por esta instância")
    
    # TODO: Implementar lógica completa
    return {"status": "success", "message": "Rede adicionada"}


@app.delete(
    "/api/v1/vpn/remove-network",
    tags=["Redes"],
    summary="Remove rede permitida",
    description="Remove uma rede permitida (AllowedIPs) do peer de um router."
)
async def remove_network(request: RemoveNetworkRequest):
    """
    Remove uma rede permitida do router
    
    - **router_id**: ID do router (UUID)
    - **network_cidr**: Rede em formato CIDR a ser removida
    """
    if not is_resource_managed(request.router_id, "router"):
        raise HTTPException(status_code=403, detail=f"Router {request.router_id} não é gerenciado por esta instância")
    
    # TODO: Implementar lógica completa
    return {"status": "success", "message": "Rede removida"}


@app.get(
    "/api/v1/vpn/status",
    tags=["Status"],
    summary="Status completo do WireGuard",
    description="Retorna status completo de todas as interfaces WireGuard, incluindo peers, tráfego e conexões."
)
async def get_wireguard_status_endpoint():
    """Obtém status completo do WireGuard em tempo real"""
    return await get_wireguard_status()


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard():
    """Dashboard em tempo real do WireGuard"""
    return HTMLResponse(content=get_dashboard_html())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
