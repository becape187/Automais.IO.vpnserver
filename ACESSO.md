# Guia de Acesso - VPN Server Service

## 📍 Informações do Serviço

O serviço VPN está configurado para rodar na **porta 8000** e está acessível em `0.0.0.0` (todas as interfaces de rede).

### Configuração Atual
- **Porta:** 8000
- **Host:** 0.0.0.0 (acessível externamente)
- **Instância:** `vpn-server-usa` (configurado via variável de ambiente)

---

## 🔍 Acessar Swagger (Documentação da API)

O FastAPI fornece automaticamente a documentação interativa via Swagger UI.

### URLs de Acesso:

1. **Swagger UI (Interface Interativa):**
   ```
   http://seu-servidor:8000/docs
   ```

2. **ReDoc (Documentação Alternativa):**
   ```
   http://seu-servidor:8000/redoc
   ```

3. **OpenAPI JSON (Especificação):**
   ```
   http://seu-servidor:8000/openapi.json
   ```

### Exemplo de Acesso Local:
```
http://localhost:8000/docs
```

### Exemplo de Acesso Remoto:
```
http://srv01.automais.io:8000/docs
```

### O que você pode fazer no Swagger:
- ✅ Ver todos os endpoints disponíveis
- ✅ Testar endpoints diretamente na interface
- ✅ Ver exemplos de requisições e respostas
- ✅ Verificar modelos de dados (schemas)
- ✅ Executar chamadas de API sem precisar de ferramentas externas

---

## 📊 Acessar Dashboard (Resumo em Tempo Real)

O dashboard fornece uma visão geral em tempo real do status do WireGuard.

### URL de Acesso:

```
http://seu-servidor:8000/dashboard
```

### Exemplo de Acesso Local:
```
http://localhost:8000/dashboard
```

### Exemplo de Acesso Remoto:
```
http://srv01.automais.io:8000/dashboard
```

### O que o Dashboard mostra:
- ✅ **Interfaces WireGuard** ativas
- ✅ **Status de cada peer** (online/offline)
- ✅ **Tráfego** (bytes enviados/recebidos)
- ✅ **Última conexão** (handshake)
- ✅ **IPs alocados** para cada peer
- ✅ **Chaves públicas** dos peers
- ✅ **Atualização automática** a cada 5 segundos

---

## 🔧 Verificar se o Serviço Está Rodando

### Via SSH no Servidor:

```bash
# Verificar status do serviço
sudo systemctl status vpnserverio.service

# Verificar se a porta está aberta
sudo netstat -tlnp | grep 8000
# ou
sudo ss -tlnp | grep 8000

# Ver logs do serviço
sudo journalctl -u vpnserverio.service -f
```

### Via Navegador:

Acesse qualquer um dos endpoints acima. Se o serviço estiver rodando, você verá:
- Swagger: Interface de documentação
- Dashboard: Página HTML com status
- Health: `http://seu-servidor:8000/health` retorna `{"status": "ok"}`

---

## 🌐 Configuração de Firewall

Se você não conseguir acessar externamente, verifique se a porta 8000 está aberta no firewall:

```bash
# UFW (Ubuntu)
sudo ufw allow 8000/tcp

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

---

## 🔐 Segurança (Recomendações)

⚠️ **Importante:** O serviço está configurado para aceitar conexões de qualquer origem (`CORS: allow_origins=["*"]`).

Para produção, considere:

1. **Restringir acesso por IP** usando firewall/iptables
2. **Adicionar autenticação** nos endpoints sensíveis
3. **Usar HTTPS** com certificado SSL
4. **Restringir CORS** para domínios específicos

---

## 📝 Endpoints Principais

| Endpoint | Método | Descrição |
|----------|---------|------------|
| `/docs` | GET | Swagger UI (Documentação) |
| `/dashboard` | GET | Dashboard HTML (Status em tempo real) |
| `/health` | GET | Health check |
| `/api/v1/vpn/status` | GET | Status JSON do WireGuard |
| `/api/v1/vpn/resources` | GET | Recursos gerenciados por esta instância |
| `/api/v1/vpn/provision-peer` | POST | Provisionar novo peer |
| `/api/v1/vpn/config/{router_id}` | GET | Obter configuração WireGuard para router |

---

## 🆘 Troubleshooting

### Serviço não responde:
```bash
# Verificar se está rodando
sudo systemctl status vpnserverio.service

# Reiniciar serviço
sudo systemctl restart vpnserverio.service

# Ver logs de erro
sudo journalctl -u vpnserverio.service -n 50
```

### Porta 8000 já em uso:
```bash
# Verificar qual processo está usando a porta
sudo lsof -i :8000
# ou
sudo netstat -tlnp | grep 8000

# Alterar porta no arquivo de serviço:
# Editar /etc/systemd/system/vpnserverio.service
# Alterar: Environment="PORT=8001"
# E no ExecStart: --port 8001
```

### Erro de permissão:
```bash
# Verificar permissões do diretório
ls -la /root/automais.io/vpnserver.io/

# Verificar se o venv existe
ls -la /root/automais.io/vpnserver.io/venv/bin/uvicorn
```

