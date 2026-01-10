# Deploy Automático - GitHub Actions

Este repositório possui deploy automático via GitHub Actions que copia todos os arquivos para o servidor.

## Configuração

### 1. Secrets do GitHub

Configure os seguintes secrets no repositório GitHub:

**Settings → Secrets and variables → Actions → New repository secret**

- `SERVER_HOST` - IP ou hostname do servidor (ex: `automais.io` ou `192.168.1.100`)
- `SERVER_USER` - Usuário SSH (ex: `root`)
- `SERVER_PASSWORD` - Senha do usuário SSH
- `SERVER_PORT` - Porta SSH (opcional, padrão: 22)

### 2. Configurar Serviços Systemd

Existem dois serviços systemd:

1. **vpnserverio.service** - Serviço principal (API FastAPI)
2. **routeros.service** - Serviço WebSocket para gerenciamento RouterOS

Os arquivos de serviço estão em `deploy/vpnserverio.service` e `deploy/routeros.service`.

**No servidor, após o primeiro deploy:**

```bash
# Copiar arquivos de serviço
sudo cp /root/automais.io/vpnserver.io/deploy/vpnserverio.service /etc/systemd/system/
sudo cp /root/automais.io/vpnserver.io/deploy/routeros.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar e iniciar serviços
sudo systemctl enable vpnserverio.service
sudo systemctl enable routeros.service
sudo systemctl start vpnserverio.service
sudo systemctl start routeros.service

# Verificar status
sudo systemctl status vpnserverio.service
sudo systemctl status routeros.service
```

**Editar variáveis de ambiente no arquivo de serviço:**

```bash
sudo nano /etc/systemd/system/vpnserverio.service
```

Ajuste as variáveis:
- `VPN_SERVER_NAME` - Nome da instância (ex: `vpn-server-usa`)
- `API_C_SHARP_URL` - URL da API C# (ex: `http://localhost:5000`)
- `SYNC_INTERVAL_SECONDS` - Intervalo de sincronização (padrão: 60)
- `PORT` - Porta do serviço (padrão: 8000)

### 3. Estrutura no Servidor

O deploy copia arquivos para: `~/automais.io/vpnserver.io/`

```
~/automais.io/
└── vpnserver.io/
    ├── main.py
    ├── config.py
    ├── models.py
    ├── utils.py
    ├── api_client.py
    ├── sync.py
    ├── wireguard.py
    ├── status.py
    ├── dashboard.py
    ├── requirements.txt
    └── ...
```

## Como Funciona

1. **Trigger:** Push para `main` ou `master`, ou execução manual
2. **Checkout:** Baixa o código do repositório
3. **Package:** Cria arquivo tar.gz com todos os arquivos (exceto .git, venv, etc)
4. **Copy Files:** Copia arquivo tar.gz para o servidor via SCP
5. **Extract:** Extrai arquivos no servidor
6. **Install Dependencies:** Instala/atualiza dependências Python no venv
7. **Copy Services:** Copia arquivos de serviço systemd (vpnserverio.service e routeros.service)
8. **Restart Services:** Reinicia os serviços vpnserverio.service e routeros.service

## Execução Manual

Você pode executar o deploy manualmente:

**Actions → Deploy VPN Server → Run workflow**

## Serviços Systemd

Os arquivos de serviço estão em `deploy/vpnserverio.service` e `deploy/routeros.service` e são copiados automaticamente durante o deploy.

**Primeira vez (manual):**

```bash
# Copiar serviços
sudo cp /root/automais.io/vpnserver.io/deploy/vpnserverio.service /etc/systemd/system/
sudo cp /root/automais.io/vpnserver.io/deploy/routeros.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar e iniciar serviços
sudo systemctl enable vpnserverio.service
sudo systemctl enable routeros.service
sudo systemctl start vpnserverio.service
sudo systemctl start routeros.service
```

**Após o primeiro deploy, os serviços são gerenciados automaticamente pelo workflow.**

## Verificação

Após o deploy, verifique:

```bash
# Conectar ao servidor
ssh root@automais.io

# Verificar arquivos
ls -la ~/automais.io/vpnserver.io/

# Verificar serviços
sudo systemctl status vpnserverio.service
sudo systemctl status routeros.service

# Ver logs
sudo journalctl -u vpnserverio.service -f
sudo journalctl -u routeros.service -f
```

## Troubleshooting

### Erro de autenticação SSH
- Verifique se `SERVER_PASSWORD` está correto no GitHub Secrets
- Verifique se o usuário tem permissão para acessar o servidor

### routeros.service não foi copiado
Se o `routeros.service` não foi copiado automaticamente pelo deploy, você pode instalá-lo manualmente:

**Opção 1: Usar script de instalação**
```bash
cd /root/automais.io/vpnserver.io
chmod +x deploy/install-routeros-service.sh
./deploy/install-routeros-service.sh
```

**Opção 2: Instalação manual**
```bash
cd /root/automais.io/vpnserver.io
sudo cp deploy/routeros.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable routeros.service
sudo systemctl start routeros.service
```

**Verificar se foi instalado:**
```bash
sudo systemctl status routeros.service
ls -la /etc/systemd/system/routeros.service
```

### Serviços não reiniciam
- O workflow procura por `vpnserverio.service` e `routeros.service`
- Se não encontrar, apenas copia os arquivos (sem reiniciar)
- Execute manualmente:
  ```bash
  sudo systemctl restart vpnserverio.service
  sudo systemctl restart routeros.service
  ```

### Arquivos não copiados
- Verifique se o diretório existe: `mkdir -p /root/automais.io/vpnserver.io`
- Verifique permissões do usuário SSH

### Erro ao instalar dependências
- Verifique se Python 3 está instalado: `python3 --version`
- Verifique se pip está instalado: `pip3 --version`
- Execute manualmente: `cd /root/automais.io/vpnserver.io && source venv/bin/activate && pip install -r requirements.txt`

