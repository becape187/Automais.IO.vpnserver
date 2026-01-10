# Configuração HTTPS - API C#

## 🔒 Problema: API C# em HTTPS na porta 5001

Se a API C# está configurada para rodar em **HTTPS na porta 5001**, você precisa atualizar a configuração do serviço VPN Python.

---

## ✅ Solução Rápida

### 1. Editar arquivo de configuração

```bash
sudo nano /root/automais.io/vpnserver.env
```

### 2. Atualizar URL da API

**Antes (errado):**
```bash
API_C_SHARP_URL=http://localhost:5000
```

**Depois (correto):**
```bash
API_C_SHARP_URL=https://srv01.automais.io:5001
```

**Se estiver no mesmo servidor:**
```bash
API_C_SHARP_URL=https://localhost:5001
```

### 3. Configurar verificação SSL

**Se usar certificado válido (Let's Encrypt, etc):**
```bash
API_C_SHARP_VERIFY_SSL=true
```

**Se usar certificado auto-assinado (apenas desenvolvimento):**
```bash
API_C_SHARP_VERIFY_SSL=false
```

⚠️ **Atenção:** `false` desabilita verificação SSL e não é recomendado para produção.

### 4. Reiniciar serviço

```bash
sudo systemctl daemon-reload
sudo systemctl restart vpnserverio.service
```

### 5. Verificar logs

```bash
sudo journalctl -u vpnserverio.service -f
```

Deve ver mensagens de sincronização bem-sucedida:
```
✅ Recursos sincronizados: X VPNs, Y Routers
```

---

## 🔍 Verificar Configuração Atual

```bash
# Ver variáveis de ambiente do serviço
sudo systemctl show vpnserverio.service | grep Environment

# Ver conteúdo do arquivo de configuração
cat /root/automais.io/vpnserver.env
```

---

## 🧪 Testar Conectividade

### Testar com curl

```bash
# Testar HTTPS (com certificado válido)
curl https://srv01.automais.io:5001/api/vpn-servers/automais.io/resources

# Testar HTTPS (ignorar certificado - apenas para debug)
curl -k https://srv01.automais.io:5001/api/vpn-servers/automais.io/resources

# Testar health check
curl https://srv01.automais.io:5001/health
```

### Testar do serviço Python

```bash
# Forçar sincronização manual
curl http://localhost:8000/api/v1/vpn/sync

# Ver recursos gerenciados
curl http://localhost:8000/api/v1/vpn/resources
```

---

## ❌ Erros Comuns

### Erro: "SSL certificate verification failed"

**Causa:** Certificado não é confiável (auto-assinado ou expirado)

**Solução temporária:**
```bash
# No vpnserver.env
API_C_SHARP_VERIFY_SSL=false
```

**Solução recomendada:**
- Usar certificado válido (Let's Encrypt)
- Adicionar certificado ao trust store do sistema

### Erro: "Connection refused"

**Causa:** API não está acessível na porta 5001

**Verificar:**
```bash
# Ver se API está rodando
sudo systemctl status automais-api.service

# Ver se porta está aberta
sudo netstat -tlnp | grep 5001
```

### Erro: "All connection attempts failed"

**Causa:** URL incorreta ou API não está acessível

**Verificar:**
```bash
# Testar URL manualmente
curl -k https://srv01.automais.io:5001/health

# Verificar DNS
nslookup srv01.automais.io
```

---

## 📋 Exemplo Completo de Configuração

```bash
# /root/automais.io/vpnserver.env

# Nome do servidor VPN
VPN_SERVER_NAME=automais.io

# URL da API C# (HTTPS na porta 5001)
API_C_SHARP_URL=https://srv01.automais.io:5001

# Verificar certificado SSL (true = verifica, false = ignora)
API_C_SHARP_VERIFY_SSL=true

# Intervalo de sincronização
SYNC_INTERVAL_SECONDS=60

# Porta do serviço Python
PORT=8000

# Diretório WireGuard
WIREGUARD_CONFIG_DIR=/etc/wireguard
```

---

## 🔐 Segurança

### Recomendações:

1. **Sempre use HTTPS em produção**
   - Não use HTTP para comunicação entre serviços

2. **Use certificados válidos**
   - Let's Encrypt (gratuito)
   - Certificados comerciais

3. **Mantenha `API_C_SHARP_VERIFY_SSL=true`**
   - Apenas use `false` em desenvolvimento
   - Nunca em produção

4. **Use firewall**
   - Restrinja acesso à porta 5001 apenas para serviços necessários

---

## 📚 Referências

- [Documentação httpx - SSL](https://www.python-httpx.org/advanced/ssl/)
- [Let's Encrypt](https://letsencrypt.org/)
- [CONFIGURACAO_VPN_SERVER.md](./CONFIGURACAO_VPN_SERVER.md)

