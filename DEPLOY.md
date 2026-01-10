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

### 2. Configurar Serviço Systemd

O arquivo de serviço está em `deploy/vpnserverio.service`. 

**No servidor, após o primeiro deploy:**

```bash
# Copiar arquivo de serviço
sudo cp /root/automais.io/vpnserver.io/deploy/vpnserverio.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar e iniciar serviço
sudo systemctl enable vpnserverio.service
sudo systemctl start vpnserverio.service

# Verificar status
sudo systemctl status vpnserverio.service
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
7. **Copy Service:** Copia arquivo de serviço systemd (se existir)
8. **Restart Service:** Reinicia o serviço vpnserverio.service

## Execução Manual

Você pode executar o deploy manualmente:

**Actions → Deploy VPN Server → Run workflow**

## Serviço Systemd

O arquivo de serviço está em `deploy/vpnserverio.service` e é copiado automaticamente durante o deploy.

**Primeira vez (manual):**

```bash
sudo cp /root/automais.io/vpnserver.io/deploy/vpnserverio.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vpnserverio.service
sudo systemctl start vpnserverio.service
```

**Após o primeiro deploy, o serviço é gerenciado automaticamente pelo workflow.**

## Verificação

Após o deploy, verifique:

```bash
# Conectar ao servidor
ssh root@automais.io

# Verificar arquivos
ls -la ~/automais.io/vpnserver.io/

# Verificar serviço
sudo systemctl status vpnserverio.service

# Ver logs
sudo journalctl -u vpnserverio.service -f
```

## Troubleshooting

### Erro de autenticação SSH
- Verifique se `SERVER_PASSWORD` está correto no GitHub Secrets
- Verifique se o usuário tem permissão para acessar o servidor

### Serviço não reinicia
- O workflow procura por `vpnserverio.service`
- Se não encontrar, apenas copia os arquivos (sem reiniciar)
- Execute manualmente: `sudo systemctl restart vpnserverio.service`

### Arquivos não copiados
- Verifique se o diretório existe: `mkdir -p /root/automais.io/vpnserver.io`
- Verifique permissões do usuário SSH

### Erro ao instalar dependências
- Verifique se Python 3 está instalado: `python3 --version`
- Verifique se pip está instalado: `pip3 --version`
- Execute manualmente: `cd /root/automais.io/vpnserver.io && source venv/bin/activate && pip install -r requirements.txt`

