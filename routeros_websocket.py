"""
Serviço WebSocket para gerenciamento RouterOS
Comunica com routers via RouterOS API e expõe via WebSocket para o frontend
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import websockets
from websockets.server import WebSocketServerProtocol
# Importação do routeros-api
# O pacote routeros-api versão 0.18.0 usa routeros_api.connect() ao invés de RouterOsApi()
import routeros_api
try:
    from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError
except ImportError:
    # Se as exceções não existirem, criar classes vazias
    class RouterOsApiConnectionError(Exception):
        pass
    class RouterOsApiCommunicationError(Exception):
        pass

from api_client import get_router_from_api, get_router_static_routes_from_api, get_router_wireguard_peers_from_api
from config import API_C_SHARP_URL

logger = logging.getLogger(__name__)

# Cache de conexões RouterOS (router_id -> routeros_api connection)
router_connections: Dict[str, 'routeros_api.Connection'] = {}

# Thread pool para executar operações RouterOS (não assíncrono)
executor = ThreadPoolExecutor(max_workers=10)

# Padrão para identificar rotas AUTOMAIS.IO
AUTOMAIS_ROUTE_PATTERN = re.compile(r'AUTOMAIS\.IO NÃO APAGAR:\s*([a-f0-9\-]{36})', re.IGNORECASE)


def is_automais_route(comment: Optional[str]) -> bool:
    """Verifica se uma rota foi criada pela plataforma AUTOMAIS.IO"""
    if not comment:
        return False
    return bool(AUTOMAIS_ROUTE_PATTERN.search(comment))


def extract_route_id_from_comment(comment: Optional[str]) -> Optional[str]:
    """Extrai o ID da rota do comentário AUTOMAIS.IO"""
    if not comment:
        return None
    match = AUTOMAIS_ROUTE_PATTERN.search(comment)
    return match.group(1) if match else None


def _get_router_connection_sync(router_id: str, router_ip: str, username: str, password: str):
    """Obtém ou cria conexão RouterOS API (síncrono)"""
    try:
        # Verificar se já existe conexão em cache
        if router_id in router_connections:
            try:
                # Testar conexão existente
                router_connections[router_id].get_resource('/system/identity').get()
                return router_connections[router_id]
            except:
                # Conexão inválida, remover do cache
                del router_connections[router_id]
        
        # Criar nova conexão usando routeros_api.connect()
        api = routeros_api.connect(router_ip, username=username, password=password)
        router_connections[router_id] = api
        logger.info(f"Conexão RouterOS estabelecida: {router_id} -> {router_ip}")
        return api
    except Exception as e:
        logger.error(f"Erro ao conectar RouterOS {router_id} ({router_ip}): {e}")
        return None


async def get_router_connection(router_id: str, router_ip: str, username: str, password: str):
    """Obtém ou cria conexão RouterOS API (assíncrono wrapper)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_router_connection_sync, router_id, router_ip, username, password)


async def add_route_to_routeros(router_id: str, route_data: Dict[str, Any]) -> Dict[str, Any]:
    """Adiciona rota estática no RouterOS (função reutilizável para HTTP e WebSocket)"""
    try:
        # Buscar router da API
        router = await get_router_from_api(router_id)
        if not router:
            return {"success": False, "error": "Router não encontrado"}
        
        # Buscar rotas do banco para obter o Comment
        routes = await get_router_static_routes_from_api(router_id)
        route_db = next((r for r in routes if r.get("id") == route_data.get("route_id")), None)
        
        if not route_db:
            return {"success": False, "error": "Rota não encontrada no banco de dados"}
        
        # Obter IP do router via peer WireGuard
        router_ip = route_data.get("router_ip")
        if not router_ip:
            peers = await get_router_wireguard_peers_from_api(router_id)
            if peers:
                allowed_ips = peers[0].get("allowedIps", "")
                if allowed_ips:
                    router_ip = allowed_ips.split(",")[0].strip().split("/")[0]
        
        if not router_ip:
            return {"success": False, "error": "IP do router não encontrado. Configure RouterOsApiUrl ou crie um peer WireGuard."}
        
        # Conectar ao RouterOS
        api = await get_router_connection(
            router_id,
            router_ip,
            router.get("routerOsApiUsername", "admin"),
            router.get("routerOsApiPassword", "")
        )
        
        if not api:
            return {"success": False, "error": "Não foi possível conectar ao RouterOS"}
        
        # Adicionar rota com comentário AUTOMAIS.IO (executar em thread)
        comment = route_db.get("comment", f"AUTOMAIS.IO NÃO APAGAR: {route_data.get('route_id')}")
        
        def add_route_sync():
            route_resource = api.get_resource('/ip/route')
            route_params = {
                "dst": route_data["destination"],
                "gateway": route_data["gateway"],
                "comment": comment
            }
            
            if route_data.get("interface_name"):
                route_params["interface"] = route_data["interface_name"]
            if route_data.get("distance"):
                route_params["distance"] = str(route_data["distance"])
            if route_data.get("scope"):
                route_params["scope"] = str(route_data["scope"])
            if route_data.get("routing_table"):
                route_params["routing-table"] = route_data["routing_table"]
            
            result = route_resource.add(**route_params)
            return result.get("ret")
        
        loop = asyncio.get_event_loop()
        route_id_routeros = await loop.run_in_executor(executor, add_route_sync)
        
        return {
            "success": True,
            "message": "Rota adicionada com sucesso",
            "router_os_id": route_id_routeros
        }
        
    except Exception as e:
        logger.error(f"Erro ao adicionar rota: {e}")
        return {"success": False, "error": str(e)}


async def remove_route_from_routeros(router_id: str, router_ip: str, username: str, password: str, router_os_route_id: str) -> Dict[str, Any]:
    """Remove rota do RouterOS (função reutilizável para HTTP e WebSocket)"""
    try:
        api = await get_router_connection(router_id, router_ip, username, password)
        if not api:
            return {"success": False, "error": "Não foi possível conectar ao RouterOS"}
        
        def remove_route_sync():
            route_resource = api.get_resource('/ip/route')
            route_resource.remove(id=router_os_route_id)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, remove_route_sync)
        
        return {
            "success": True,
            "message": "Rota removida com sucesso"
        }
        
    except Exception as e:
        logger.error(f"Erro ao remover rota: {e}")
        return {"success": False, "error": str(e)}


async def handle_add_route(router_id: str, route_data: Dict[str, Any], ws: WebSocketServerProtocol):
    """Adiciona rota estática no RouterOS"""
    try:
        # Buscar router da API
        router = await get_router_from_api(router_id)
        if not router:
            await ws.send(json.dumps({"error": "Router não encontrado"}))
            return
        
        # Buscar rotas do banco para obter o Comment
        routes = await get_router_static_routes_from_api(router_id)
        route_db = next((r for r in routes if r.get("id") == route_data.get("id")), None)
        
        if not route_db:
            await ws.send(json.dumps({"error": "Rota não encontrada no banco de dados"}))
            return
        
        # Obter IP do router via peer WireGuard
        router_ip = route_data.get("router_ip")
        if not router_ip:
            # Buscar do peer WireGuard
            peers = await get_router_wireguard_peers_from_api(router_id)
            if peers:
                allowed_ips = peers[0].get("allowedIps", "")
                if allowed_ips:
                    router_ip = allowed_ips.split(",")[0].strip().split("/")[0]
        
        if not router_ip:
            await ws.send(json.dumps({"error": "IP do router não encontrado. Configure RouterOsApiUrl ou crie um peer WireGuard."}))
            return
        
        # Conectar ao RouterOS
        api = await get_router_connection(
            router_id,
            router_ip,
            router.get("routerOsApiUsername", "admin"),
            router.get("routerOsApiPassword", "")
        )
        
        if not api:
            await ws.send(json.dumps({"error": "Não foi possível conectar ao RouterOS"}))
            return
        
        # Adicionar rota com comentário AUTOMAIS.IO (executar em thread)
        comment = route_db.get("comment", f"AUTOMAIS.IO NÃO APAGAR: {route_db.get('id')}")
        
        def add_route_sync():
            route_resource = api.get_resource('/ip/route')
            route_params = {
                "dst": route_data["destination"],
                "gateway": route_data["gateway"],
                "comment": comment
            }
            
            if route_data.get("interface"):
                route_params["interface"] = route_data["interface"]
            if route_data.get("distance"):
                route_params["distance"] = str(route_data["distance"])
            if route_data.get("scope"):
                route_params["scope"] = str(route_data["scope"])
            if route_data.get("routingTable"):
                route_params["routing-table"] = route_data["routingTable"]
            
            result = route_resource.add(**route_params)
            return result.get("ret")
        
        loop = asyncio.get_event_loop()
        route_id_routeros = await loop.run_in_executor(executor, add_route_sync)
        
        await ws.send(json.dumps({
            "success": True,
            "message": "Rota adicionada com sucesso",
            "router_os_id": route_id_routeros
        }))
        
    except Exception as e:
        logger.error(f"Erro ao adicionar rota: {e}")
        await ws.send(json.dumps({"error": str(e)}))


async def handle_list_routes(router_id: str, router_ip: str, username: str, password: str, ws: WebSocketServerProtocol):
    """Lista rotas do RouterOS, identificando quais são AUTOMAIS.IO"""
    try:
        api = await get_router_connection(router_id, router_ip, username, password)
        if not api:
            await ws.send(json.dumps({"error": "Não foi possível conectar ao RouterOS"}))
            return
        
        def get_routes_sync():
            route_resource = api.get_resource('/ip/route')
            return route_resource.get()
        
        loop = asyncio.get_event_loop()
        routes = await loop.run_in_executor(executor, get_routes_sync)
        
        # Buscar rotas do banco para mapear
        routes_db = await get_router_static_routes_from_api(router_id)
        routes_db_map = {r.get("id"): r for r in routes_db}
        
        # Processar rotas e identificar AUTOMAIS.IO
        processed_routes = []
        for route in routes:
            comment = route.get("comment", "")
            is_automais = is_automais_route(comment)
            route_id = extract_route_id_from_comment(comment)
            
            route_data = {
                "id": route.get(".id"),
                "dst": route.get("dst", ""),
                "gateway": route.get("gateway", ""),
                "interface": route.get("interface", ""),
                "distance": route.get("distance", ""),
                "scope": route.get("scope", ""),
                "routing-table": route.get("routing-table", ""),
                "comment": comment,
                "is_automais": is_automais,
                "route_id": route_id,
                "active": route.get("active", "false") == "true",
                "disabled": route.get("disabled", "false") == "true"
            }
            
            # Adicionar dados do banco se for rota AUTOMAIS.IO
            if is_automais and route_id and route_id in routes_db_map:
                route_data["db_data"] = routes_db_map[route_id]
            
            processed_routes.append(route_data)
        
        await ws.send(json.dumps({
            "success": True,
            "routes": processed_routes
        }))
        
    except Exception as e:
        logger.error(f"Erro ao listar rotas: {e}")
        await ws.send(json.dumps({"error": str(e)}))


async def handle_delete_route(router_id: str, router_ip: str, username: str, password: str, route_routeros_id: str, ws: WebSocketServerProtocol):
    """Remove rota do RouterOS"""
    try:
        api = await get_router_connection(router_id, router_ip, username, password)
        if not api:
            await ws.send(json.dumps({"error": "Não foi possível conectar ao RouterOS"}))
            return
        
        def remove_route_sync():
            route_resource = api.get_resource('/ip/route')
            route_resource.remove(id=route_routeros_id)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, remove_route_sync)
        
        await ws.send(json.dumps({
            "success": True,
            "message": "Rota removida com sucesso"
        }))
        
    except Exception as e:
        logger.error(f"Erro ao remover rota: {e}")
        await ws.send(json.dumps({"error": str(e)}))


async def handle_execute_command(router_id: str, router_ip: str, username: str, password: str, command: str, ws: WebSocketServerProtocol):
    """Executa comando RouterOS genérico"""
    try:
        api = await get_router_connection(router_id, router_ip, username, password)
        if not api:
            await ws.send(json.dumps({"error": "Não foi possível conectar ao RouterOS"}))
            return
        
        # Parse do comando (ex: "/ip/firewall/filter/print")
        parts = command.strip().split("/")
        if len(parts) < 3:
            await ws.send(json.dumps({"error": "Comando inválido"}))
            return
        
        resource_path = "/" + "/".join(parts[1:-1])
        action = parts[-1]
        
        def execute_command_sync():
            resource = api.get_resource(resource_path)
            if action == "print":
                return resource.get()
            else:
                raise ValueError(f"Ação '{action}' não suportada")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, execute_command_sync)
        await ws.send(json.dumps({"success": True, "data": result}))
        
    except Exception as e:
        logger.error(f"Erro ao executar comando: {e}")
        await ws.send(json.dumps({"error": str(e)}))


async def handle_websocket(ws: WebSocketServerProtocol, path: str):
    """Handler principal do WebSocket"""
    logger.info(f"Nova conexão WebSocket: {ws.remote_address}")
    
    try:
        async for message in ws:
            try:
                data = json.loads(message)
                action = data.get("action")
                router_id = data.get("router_id")
                
                if not action or not router_id:
                    await ws.send(json.dumps({"error": "action e router_id são obrigatórios"}))
                    continue
                
                # Buscar router da API
                router = await get_router_from_api(router_id)
                if not router:
                    await ws.send(json.dumps({"error": "Router não encontrado"}))
                    continue
                
                # Obter IP do router (via peer WireGuard ou RouterOsApiUrl)
                router_ip = data.get("router_ip")
                if not router_ip:
                    # Tentar extrair do RouterOsApiUrl
                    router_ip = router.get("routerOsApiUrl", "").split(":")[0] if router.get("routerOsApiUrl") else None
                
                # Se ainda não tem IP, buscar do peer WireGuard
                if not router_ip:
                    peers = await get_router_wireguard_peers_from_api(router_id)
                    if peers:
                        # Extrair IP do primeiro peer (formato: "10.222.111.2/32" -> "10.222.111.2")
                        allowed_ips = peers[0].get("allowedIps", "")
                        if allowed_ips:
                            router_ip = allowed_ips.split(",")[0].strip().split("/")[0]
                
                if not router_ip:
                    await ws.send(json.dumps({"error": "IP do router não encontrado. Configure RouterOsApiUrl ou crie um peer WireGuard."}))
                    continue
                
                username = router.get("routerOsApiUsername", "admin")
                password = router.get("routerOsApiPassword", "")
                
                # Roteamento de ações
                if action == "add_route":
                    await handle_add_route(router_id, data.get("route_data", {}), ws)
                elif action == "list_routes":
                    await handle_list_routes(router_id, router_ip, username, password, ws)
                elif action == "delete_route":
                    await handle_delete_route(router_id, router_ip, username, password, data.get("route_routeros_id"), ws)
                elif action == "execute_command":
                    await handle_execute_command(router_id, router_ip, username, password, data.get("command", ""), ws)
                else:
                    await ws.send(json.dumps({"error": f"Ação '{action}' não reconhecida"}))
                    
            except json.JSONDecodeError:
                await ws.send(json.dumps({"error": "JSON inválido"}))
            except Exception as e:
                logger.error(f"Erro ao processar mensagem: {e}")
                await ws.send(json.dumps({"error": str(e)}))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Conexão WebSocket fechada: {ws.remote_address}")
    except Exception as e:
        logger.error(f"Erro na conexão WebSocket: {e}")


async def start_websocket_server(host: str = "0.0.0.0", port: int = 8765):
    """Inicia servidor WebSocket"""
    logger.info(f"🚀 Iniciando servidor WebSocket RouterOS em ws://{host}:{port}")
    
    async with websockets.serve(handle_websocket, host, port):
        await asyncio.Future()  # Rodar indefinidamente


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_websocket_server())

