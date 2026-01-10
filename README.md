# VPN Server - Serviço de Gerenciamento WireGuard

Serviço Python isolado para gerenciamento completo de WireGuard.

## Características

- ✅ Auto-descoberta de recursos via API C#
- ✅ Gerenciamento completo de interfaces WireGuard
- ✅ Provisionamento de peers
- ✅ Geração de chaves
- ✅ Alocação de IPs
- ✅ Configuração de firewall (iptables)
- ✅ Sincronização periódica

## Instalação

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

## Configuração

Criar arquivo `.env`:

```env
VPN_SERVER_NAME=vpn-server-usa
API_C_SHARP_URL=http://localhost:5000
SYNC_INTERVAL_SECONDS=60
PORT=8000
```

## Execução

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Arquitetura

Cada instância do serviço VPN:
1. **Identifica-se** via variável de ambiente `VPN_SERVER_NAME`
2. **Consulta a API C#** para descobrir seus recursos (VpnNetworks e Routers)
3. **Sincroniza periodicamente** (padrão: 60s)
4. **Gerencia apenas** os recursos atribuídos a ela

## Dashboard em Tempo Real

Acesse o dashboard visual para monitorar o WireGuard em tempo real:

- **Dashboard:** `http://localhost:8000/dashboard` - Interface visual com atualização automática a cada 3 segundos

O dashboard mostra:
- 📊 Estatísticas gerais (interfaces, peers, tráfego)
- 🔌 Status de cada interface WireGuard
- 👥 Lista de peers com status online/offline
- 📈 Tráfego de download/upload por peer
- ⏱️ Último handshake de cada peer
- 🌐 Endpoints e IPs permitidos

## Documentação da API (Swagger)

O serviço inclui documentação interativa via Swagger/OpenAPI:

- **Swagger UI:** `http://localhost:8000/docs` - Interface interativa para testar endpoints
- **ReDoc:** `http://localhost:8000/redoc` - Documentação alternativa em formato mais limpo
- **OpenAPI JSON:** `http://localhost:8000/openapi.json` - Especificação OpenAPI em JSON

### Principais Endpoints:

- `GET /` - Status do serviço
- `GET /health` - Health check
- `GET /api/v1/vpn/resources` - Lista recursos gerenciados
- `POST /api/v1/vpn/sync` - Força sincronização
- `POST /api/v1/vpn/provision-peer` - Provisiona peer WireGuard
- `GET /api/v1/vpn/config/{router_id}` - Obtém configuração
- `POST /api/v1/vpn/ensure-interface` - Garante interface existe
- `DELETE /api/v1/vpn/remove-interface` - Remove interface
- `POST /api/v1/vpn/add-network` - Adiciona rede permitida
- `DELETE /api/v1/vpn/remove-network` - Remove rede permitida

## Múltiplas Instâncias

Cada servidor VPN físico deve ter sua própria instância:

**Servidor VPN 1 (EUA):**
```env
VPN_SERVER_NAME=vpn-server-usa
PORT=8000
```

**Servidor VPN 2 (Brasil):**
```env
VPN_SERVER_NAME=vpn-server-brasil
PORT=8001
```
