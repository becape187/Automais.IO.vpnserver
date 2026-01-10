# Estrutura Modular do Serviço VPN

## ✅ Módulos Criados

### 1. `config.py`
**Responsabilidade:** Configurações e variáveis de ambiente
- `VPN_SERVER_NAME` - Nome da instância do servidor VPN
- `API_C_SHARP_URL` - URL da API C# principal
- `SYNC_INTERVAL_SECONDS` - Intervalo de sincronização
- `WIREGUARD_CONFIG_DIR` - Diretório de configuração WireGuard
- `PORT` - Porta do serviço

### 2. `models.py`
**Responsabilidade:** Modelos Pydantic para requests e responses
- `ProvisionPeerRequest` - Request para provisionar peer
- `ProvisionPeerResponse` - Response do provisionamento
- `AddNetworkRequest` - Request para adicionar rede
- `RemoveNetworkRequest` - Request para remover rede
- `VpnConfigResponse` - Response com configuração
- `EnsureInterfaceRequest` - Request para garantir interface

### 3. `utils.py`
**Responsabilidade:** Funções utilitárias
- `execute_command()` - Executa comandos shell
- `format_bytes()` - Formata bytes para string legível
- `parse_size_to_bytes()` - Converte string de tamanho para bytes

### 4. `api_client.py`
**Responsabilidade:** Cliente HTTP para comunicação com API C#
- `get_vpn_network_from_api()` - Busca VpnNetwork
- `get_router_from_api()` - Busca Router
- `update_peer_in_api()` - Atualiza peer no banco

### 5. `sync.py`
**Responsabilidade:** Sincronização de recursos com API C#
- `sync_resources_from_api()` - Sincroniza recursos
- `is_resource_managed()` - Verifica se recurso é gerenciado
- `get_managed_resources()` - Retorna recursos gerenciados
- `managed_resources` - Cache de recursos

### 6. `wireguard.py`
**Responsabilidade:** Lógica completa do WireGuard
- `get_interface_name()` - Gera nome da interface
- `generate_wireguard_keys()` - Gera chaves WireGuard
- `parse_cidr()` - Parse CIDR
- `get_server_ip()` - Obtém IP do servidor
- `get_main_network_interface()` - Detecta interface principal
- `configure_firewall_rules()` - Configura firewall (iptables)
- `ensure_interface_exists()` - Garante que interface existe
- `allocate_vpn_ip()` - Aloca IP na rede VPN
- `add_peer_to_interface()` - Adiciona peer à interface
- `generate_router_config()` - Gera configuração para router
- `remove_interface()` - Remove interface WireGuard

### 7. `status.py`
**Responsabilidade:** Status e monitoramento do WireGuard
- `get_wireguard_status()` - Obtém status completo (interfaces, peers, tráfego)

### 8. `dashboard.py`
**Responsabilidade:** Dashboard HTML em tempo real
- `get_dashboard_html()` - Retorna HTML completo do dashboard

### 9. `main.py`
**Responsabilidade:** Apenas endpoints FastAPI e configuração
- Configuração do FastAPI
- Lifespan e background tasks
- Todos os endpoints da API
- Importa e usa todos os módulos acima

## 📊 Estrutura de Arquivos

```
vpnserver.io/
├── main.py              # Endpoints FastAPI (refatorado)
├── config.py            # Configurações
├── models.py            # Modelos Pydantic
├── utils.py             # Funções utilitárias
├── api_client.py        # Cliente HTTP API C#
├── sync.py              # Sincronização de recursos
├── wireguard.py         # Lógica WireGuard
├── status.py            # Status e monitoramento
├── dashboard.py         # HTML do dashboard
├── requirements.txt     # Dependências
└── README.md            # Documentação
```

## 🔄 Fluxo de Dependências

```
main.py
  ├── config.py
  ├── models.py
  ├── sync.py
  │     └── config.py
  ├── api_client.py
  │     └── config.py
  ├── wireguard.py
  │     ├── config.py
  │     ├── utils.py
  │     └── api_client.py
  ├── status.py
  │     └── utils.py
  └── dashboard.py
        └── config.py
```

## 📝 Benefícios da Modularização

1. **Organização:** Cada módulo tem responsabilidade única e clara
2. **Manutenibilidade:** Fácil localizar e modificar código específico
3. **Testabilidade:** Módulos podem ser testados isoladamente
4. **Reutilização:** Funções podem ser reutilizadas em diferentes contextos
5. **Legibilidade:** Código mais limpo e fácil de entender
6. **Escalabilidade:** Fácil adicionar novas funcionalidades

## 🚀 Como Usar

O `main.py` agora importa todos os módulos e funciona exatamente como antes, mas com código muito mais organizado:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Todas as funcionalidades permanecem as mesmas, apenas organizadas em módulos separados.
