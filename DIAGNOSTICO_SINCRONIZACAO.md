# Diagnóstico de Sincronização - VPN Server

## 🔍 Consultas Realizadas

O serviço VPN Python faz as seguintes consultas HTTP para a API C#:

### 1. **Sincronização Periódica de Recursos** (A cada 60 segundos)

**Endpoint:**
```
GET {API_C_SHARP_URL}/api/vpn-servers/{VPN_SERVER_NAME}/resources
```

**Onde:**
- `API_C_SHARP_URL` = URL da API C# (ex: `http://localhost:5000`)
- `VPN_SERVER_NAME` = Nome do servidor VPN (ex: `automais.io`)

**Exemplo completo (HTTPS):**
```
GET https://srv01.automais.io:5001/api/vpn-servers/automais.io/resources
```

**Exemplo local (HTTP - apenas desenvolvimento):**
```
GET http://localhost:5000/api/vpn-servers/automais.io/resources
```

**O que retorna:**
```json
{
  "server_name": "automais.io",
  "vpn_networks": [
    {
      "id": "guid-da-vpn",
      "name": "Rede VPN Principal",
      "cidr": "10.0.0.0/24",
      "server_endpoint": "automais.io",
      "tenant_id": "guid-do-tenant"
    }
  ],
  "routers": [
    {
      "id": "guid-do-router",
      "name": "Router Principal",
      "vpn_network_id": "guid-da-vpn",
      "router_os_api_url": "https://...",
      "status": "Online"
    }
  ],
  "timestamp": "2026-01-09T22:00:00Z"
}
```

**Quando é executada:**
- A cada `SYNC_INTERVAL_SECONDS` (padrão: 60 segundos)
- Na inicialização do serviço
- Quando o endpoint `/api/v1/vpn/sync` é chamado manualmente

---

### 2. **Busca de VpnNetwork** (Quando necessário)

**Endpoint:**
```
GET {API_C_SHARP_URL}/api/vpn/networks/{vpn_network_id}
```

**Quando é executada:**
- Ao provisionar um peer
- Ao garantir interface WireGuard
- Ao adicionar/remover redes

---

### 3. **Busca de Router** (Quando necessário)

**Endpoint:**
```
GET {API_C_SHARP_URL}/api/routers/{router_id}
```

**Quando é executada:**
- Ao provisionar um peer
- Ao gerar configuração WireGuard

---

## ❌ Erro: "All connection attempts failed"

Este erro indica que o serviço Python **não consegue se conectar** à API C#.

### Possíveis Causas:

1. **API C# não está rodando**
   - Verificar se o serviço `automais-api.service` está ativo
   - Verificar logs: `sudo journalctl -u automais-api.service -f`

2. **URL incorreta no `vpnserver.env`**
   - Verificar se `API_C_SHARP_URL` está correto
   - Se a API está em outro servidor, usar IP/hostname correto
   - Se a API usa HTTPS, usar `https://` ao invés de `http://`

3. **API C# não está acessível na porta configurada**
   - Verificar se a porta 5000 está aberta
   - Verificar firewall: `sudo ufw status` ou `sudo iptables -L`

4. **API C# está rodando em localhost mas o Python está em outro servidor**
   - Se estão em servidores diferentes, usar IP/hostname ao invés de `localhost`
   - Exemplo: `API_C_SHARP_URL=http://192.168.1.100:5000`

5. **VPN_SERVER_NAME não existe no banco de dados**
   - Verificar se existe um registro `VpnServer` com `ServerName` igual ao `VPN_SERVER_NAME`
   - O endpoint retornará 404 se não existir

---

## 🔧 Como Diagnosticar

### 1. Verificar configuração do serviço Python

```bash
# Ver variáveis de ambiente do serviço
sudo systemctl show vpnserverio.service | grep Environment

# Ver conteúdo do arquivo de configuração
cat /root/automais.io/vpnserver.env
```

**Verificar:**
- `VPN_SERVER_NAME` está configurado?
- `API_C_SHARP_URL` está correto?
- A URL está acessível?

### 2. Testar conectividade com a API C#

```bash
# Testar se a API está acessível (HTTPS - produção)
curl https://srv01.automais.io:5001/api/vpn-servers/automais.io/resources

# Se usar certificado auto-assinado, adicionar -k
curl -k https://srv01.automais.io:5001/api/vpn-servers/automais.io/resources

# Testar local (HTTP - apenas desenvolvimento)
curl http://localhost:5000/api/vpn-servers/automais.io/resources

# Verificar se a API está respondendo (HTTPS)
curl https://srv01.automais.io:5001/health

# Verificar se a API está respondendo (HTTP local)
curl http://localhost:5000/health
```

### 3. Verificar se a API C# está rodando

```bash
# Status do serviço
sudo systemctl status automais-api.service

# Ver logs
sudo journalctl -u automais-api.service -n 50

# Verificar porta
sudo netstat -tlnp | grep 5000
# ou
sudo ss -tlnp | grep 5000
```

### 4. Verificar logs do serviço VPN Python

```bash
# Ver logs em tempo real
sudo journalctl -u vpnserverio.service -f

# Ver últimos erros
sudo journalctl -u vpnserverio.service -n 100 | grep ERROR
```

### 5. Testar manualmente a sincronização

```bash
# Chamar endpoint de sincronização manual
curl http://localhost:8000/api/v1/vpn/sync

# Ver recursos gerenciados
curl http://localhost:8000/api/v1/vpn/resources
```

---

## ✅ Soluções Comuns

### Problema: API C# em HTTPS mas Python configurado para HTTP

**Solução:** Alterar `API_C_SHARP_URL` no `vpnserver.env` para usar HTTPS:

```bash
# Antes (errado - HTTP na porta 5000)
API_C_SHARP_URL=http://localhost:5000

# Depois (correto - HTTPS na porta 5001)
API_C_SHARP_URL=https://srv01.automais.io:5001
```

**Se usar certificado auto-assinado:**
O Python `httpx` pode rejeitar certificados auto-assinados. Nesse caso, você pode:
1. Adicionar o certificado ao sistema
2. Ou configurar `httpx` para aceitar certificados não verificados (não recomendado para produção)

### Problema: API C# não está rodando

**Solução:**
```bash
# Iniciar serviço
sudo systemctl start automais-api.service

# Habilitar para iniciar automaticamente
sudo systemctl enable automais-api.service
```

### Problema: Firewall bloqueando conexão

**Solução:**
```bash
# UFW
sudo ufw allow 5000/tcp

# Firewalld
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
```

### Problema: VPN_SERVER_NAME não existe no banco

**Solução:**
1. Verificar se existe um `VpnServer` no banco com `ServerName` igual ao configurado
2. Criar o registro se não existir:
   ```sql
   INSERT INTO vpn_servers (id, name, server_name, host, is_active, created_at, updated_at)
   VALUES (
     gen_random_uuid(),
     'Servidor VPN Principal',
     'automais.io',  -- Deve corresponder ao VPN_SERVER_NAME
     'srv01.automais.io',
     true,
     NOW(),
     NOW()
   );
   ```

### Problema: API C# retorna 404

**Solução:**
- Verificar se o endpoint `/api/vpn-servers/{serverName}/resources` existe na API C#
- Verificar se o `VpnServersController` está registrado
- Verificar logs da API C# para ver o erro específico

---

## 📊 Monitoramento

### Verificar status da sincronização

```bash
# Ver última sincronização
curl http://localhost:8000/api/v1/vpn/resources | jq '.last_sync'

# Ver quantos recursos estão sendo gerenciados
curl http://localhost:8000/api/v1/vpn/resources | jq '.vpn_networks | length'
curl http://localhost:8000/api/v1/vpn/resources | jq '.routers | length'
```

### Logs úteis

```bash
# Ver apenas erros de sincronização
sudo journalctl -u vpnserverio.service | grep "Erro ao sincronizar"

# Ver tentativas de conexão
sudo journalctl -u vpnserverio.service | grep "sync"

# Ver todas as requisições HTTP
sudo journalctl -u vpnserverio.service | grep "GET\|POST\|DELETE"
```

---

## 🔄 Fluxo de Sincronização

```
┌─────────────────┐
│  Serviço Python │
│   (vpnserverio) │
└────────┬────────┘
         │
         │ GET /api/vpn-servers/{VPN_SERVER_NAME}/resources
         │
         ▼
┌─────────────────┐
│   API C#        │
│  (automais-api) │
└────────┬────────┘
         │
         │ Consulta banco de dados
         │ - Busca VpnServer pelo ServerName
         │ - Busca VpnNetworks associadas
         │ - Busca Routers associados
         │
         ▼
┌─────────────────┐
│  Banco de Dados │
│   (PostgreSQL)  │
└─────────────────┘
```

---

## 📝 Checklist de Diagnóstico

- [ ] API C# está rodando? (`systemctl status automais-api.service`)
- [ ] Porta 5000 está aberta? (`netstat -tlnp | grep 5000`)
- [ ] `API_C_SHARP_URL` está correto no `vpnserver.env`?
- [ ] `VPN_SERVER_NAME` está configurado?
- [ ] Consegue fazer curl manual para a API? (`curl http://localhost:5000/health`)
- [ ] Existe `VpnServer` no banco com `ServerName` correto?
- [ ] Firewall não está bloqueando?
- [ ] Logs da API C# mostram requisições chegando?

---

## 🆘 Se Nada Funcionar

1. **Verificar conectividade de rede:**
   ```bash
   ping IP_DO_SERVIDOR_API
   telnet IP_DO_SERVIDOR_API 5000
   ```

2. **Verificar DNS (se usando hostname):**
   ```bash
   nslookup srv01.automais.io
   ```

3. **Testar com curl direto:**
   ```bash
   curl -v http://localhost:5000/api/vpn-servers/automais.io/resources
   ```

4. **Verificar logs completos:**
   ```bash
   # Python
   sudo journalctl -u vpnserverio.service -n 200
   
   # C#
   sudo journalctl -u automais-api.service -n 200
   ```

