"""
Modelos Pydantic para requests e responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ProvisionPeerRequest(BaseModel):
    """Request para provisionar um peer WireGuard"""
    router_id: str = Field(..., description="ID do router (UUID)", example="123e4567-e89b-12d3-a456-426614174000")
    vpn_network_id: str = Field(..., description="ID da rede VPN (UUID)", example="123e4567-e89b-12d3-a456-426614174001")
    allowed_networks: List[str] = Field(default=[], description="Redes adicionais permitidas (CIDR)", example=["10.0.0.0/8", "192.168.1.0/24"])
    manual_ip: Optional[str] = Field(None, description="IP manual para o router (formato: IP/PREFIX)", example="10.100.1.10/24")

    class Config:
        json_schema_extra = {
            "example": {
                "router_id": "123e4567-e89b-12d3-a456-426614174000",
                "vpn_network_id": "123e4567-e89b-12d3-a456-426614174001",
                "allowed_networks": ["10.0.0.0/8"],
                "manual_ip": "10.100.1.10/24"
            }
        }


class AddNetworkRequest(BaseModel):
    """Request para adicionar rede permitida ao router"""
    router_id: str = Field(..., description="ID do router (UUID)", example="123e4567-e89b-12d3-a456-426614174000")
    network_cidr: str = Field(..., description="Rede em formato CIDR", example="10.0.0.0/8")
    description: Optional[str] = Field(None, description="Descrição da rede", example="Rede interna da empresa")


class RemoveNetworkRequest(BaseModel):
    """Request para remover rede permitida do router"""
    router_id: str = Field(..., description="ID do router (UUID)", example="123e4567-e89b-12d3-a456-426614174000")
    network_cidr: str = Field(..., description="Rede em formato CIDR a ser removida", example="10.0.0.0/8")


class VpnConfigResponse(BaseModel):
    """Resposta com configuração WireGuard"""
    config_content: str = Field(..., description="Conteúdo do arquivo de configuração WireGuard")
    filename: str = Field(..., description="Nome sugerido para o arquivo", example="router_123e4567.conf")


class EnsureInterfaceRequest(BaseModel):
    """Request para garantir que interface WireGuard existe"""
    vpn_network_id: str = Field(..., description="ID da rede VPN (UUID)", example="123e4567-e89b-12d3-a456-426614174001")


class ProvisionPeerResponse(BaseModel):
    """Resposta do provisionamento de peer"""
    router_id: str
    vpn_network_id: str
    public_key: str = Field(..., description="Chave pública WireGuard do peer")
    private_key: str = Field(..., description="Chave privada WireGuard do peer")
    allowed_ips: str = Field(..., description="IPs permitidos (formato: IP/PREFIX)")
    interface_name: str = Field(..., description="Nome da interface WireGuard no servidor")
    status: str = Field(..., description="Status do provisionamento", example="provisioned")


class AddRouteRequest(BaseModel):
    """Request para adicionar rota estática no RouterOS"""
    router_id: str = Field(..., description="ID do router (UUID)")
    route_id: str = Field(..., description="ID da rota no banco (UUID)")
    destination: str = Field(..., description="Destino da rota (ex: 0.0.0.0/0)")
    gateway: str = Field(..., description="Gateway da rota (ex: 10.0.0.1)")
    interface_name: Optional[str] = Field(None, description="Interface de saída (opcional)")
    distance: Optional[int] = Field(None, description="Distância da rota (opcional)")
    scope: Optional[int] = Field(None, description="Escopo da rota (opcional)")
    routing_table: Optional[str] = Field(None, description="Tabela de roteamento (opcional)")
    comment: str = Field(..., description="Comentário da rota (formato AUTOMAIS.IO)")


class RemoveRouteRequest(BaseModel):
    """Request para remover rota estática do RouterOS"""
    router_id: str = Field(..., description="ID do router (UUID)")
    router_os_route_id: str = Field(..., description="ID da rota no RouterOS")
