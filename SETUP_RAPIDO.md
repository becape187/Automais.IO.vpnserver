# Setup Rápido - VPN Server

Guia rápido para configurar o VPN Server pela primeira vez.

---

## 🚀 Passos Rápidos

### 1. Criar arquivo de configuração

```bash
# Copiar exemplo
sudo cp /root/automais.io/vpnserver.io/vpnserver.env.example /root/automais.io/vpnserver.env

# Editar configuração
sudo nano /root/automais.io/vpnserver.env
```

### 2. Configurar variáveis mínimas

Edite o arquivo `/root/automais.io/vpnserver.env` e configure pelo menos:

```bash
VPN_SERVER_NAME=automais.io
API_C_SHARP_URL=http://localhost:5000
```

### 3. Reiniciar serviço

```bash
sudo systemctl daemon-reload
sudo systemctl restart vpnserverio.service
```

### 4. Verificar status

```bash
sudo systemctl status vpnserverio.service
```

---

## ✅ Verificação

### Verificar se o serviço está rodando:

```bash
curl http://localhost:8000/health
```

Deve retornar: `{"status":"ok"}`

### Acessar Swagger:

```
http://seu-servidor:8000/docs
```

### Acessar Dashboard:

```
http://seu-servidor:8000/dashboard
```

---

## 📝 Conteúdo do vpnserver.env

O arquivo deve conter:

```bash
# Nome identificador deste servidor VPN (OBRIGATÓRIO)
VPN_SERVER_NAME=automais.io

# URL da API C# principal
API_C_SHARP_URL=http://localhost:5000

# Intervalo de sincronização (segundos)
SYNC_INTERVAL_SECONDS=60

# Porta do serviço FastAPI
PORT=8000

# Diretório de configuração do WireGuard
WIREGUARD_CONFIG_DIR=/etc/wireguard
```

---

## 🔍 Troubleshooting

### Serviço não inicia:

```bash
# Ver logs
sudo journalctl -u vpnserverio.service -n 50

# Verificar se arquivo existe
ls -la /root/automais.io/vpnserver.env

# Verificar conteúdo
cat /root/automais.io/vpnserver.env
```

### Variáveis não carregadas:

```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Reiniciar serviço
sudo systemctl restart vpnserverio.service
```

---

📖 **Documentação completa:** [CONFIGURACAO_VPN_SERVER.md](./CONFIGURACAO_VPN_SERVER.md)

