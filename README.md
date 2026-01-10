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

O serviço lê suas configurações do arquivo `/root/automais.io/vpnserver.env`.

### Primeira Configuração

1. **Copie o arquivo de exemplo:**
   ```bash
   sudo cp vpnserver.env.example /root/automais.io/vpnserver.env
   ```

2. **Edite o arquivo com suas configurações:**
   ```bash
   sudo nano /root/automais.io/vpnserver.env
   ```

3. **Configure pelo menos:**
   - `VPN_SERVER_NAME` - Nome identificador do servidor (obrigatório)
   - `API_C_SHARP_URL` - URL da API C# principal

### Exemplo de Configuração

```bash
VPN_SERVER_NAME=automais.io
API_C_SHARP_URL=https://srv01.automais.io:5001
API_C_SHARP_VERIFY_SSL=true
SYNC_INTERVAL_SECONDS=60
PORT=8000
WIREGUARD_CONFIG_DIR=/etc/wireguard
```

> 📖 **Documentação completa:** Veja [CONFIGURACAO_VPN_SERVER.md](./CONFIGURACAO_VPN_SERVER.md) para detalhes de todas as variáveis e opções de configuração.

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

## 🔍 Acesso ao Serviço

### Swagger (Documentação Interativa)

Acesse a documentação completa da API com interface interativa:

- **Swagger UI:** `http://seu-servidor:8000/docs`
  - Interface interativa para testar todos os endpoints
  - Exemplos de requisições e respostas
  - Modelos de dados (schemas)

- **ReDoc:** `http://seu-servidor:8000/redoc`
  - Documentação alternativa em formato mais limpo

- **OpenAPI JSON:** `http://seu-servidor:8000/openapi.json`
  - Especificação OpenAPI em formato JSON

**Exemplos:**
- Local: `http://localhost:8000/docs`
- Remoto: `http://srv01.automais.io:8000/docs`

### 📊 Dashboard em Tempo Real

Acesse o dashboard visual para monitorar o WireGuard em tempo real:

- **Dashboard:** `http://seu-servidor:8000/dashboard`
  - Interface visual com atualização automática a cada 5 segundos
  - Status completo de interfaces e peers

**Exemplos:**
- Local: `http://localhost:8000/dashboard`
- Remoto: `http://srv01.automais.io:8000/dashboard`

**O dashboard mostra:**
- 📊 Estatísticas gerais (interfaces, peers, tráfego total)
- 🔌 Status de cada interface WireGuard
- 👥 Lista de peers com status online/offline
- 📈 Tráfego de download/upload por peer
- ⏱️ Último handshake de cada peer
- 🌐 Endpoints e IPs permitidos
- 🔑 Chaves públicas dos peers

> 📖 **Guia completo de acesso:** Veja [ACESSO.md](./ACESSO.md) para mais detalhes, troubleshooting e configurações de segurança.

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
