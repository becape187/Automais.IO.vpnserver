# Setup GitHub Actions - Guia Rápido

## 1. Configurar Secrets no GitHub

Acesse: **Settings → Secrets and variables → Actions → New repository secret**

Adicione os seguintes secrets (os mesmos do repositório server.io):

### `SERVER_HOST`
- **Valor:** IP ou hostname do servidor
- **Exemplo:** `automais.io` ou `192.168.1.100`
- **Mesmo valor usado no server.io**

### `SERVER_USER`
- **Valor:** Usuário SSH
- **Exemplo:** `root`
- **Mesmo valor usado no server.io**

### `SERVER_PASSWORD`
- **Valor:** Senha do usuário SSH
- **Mesmo valor usado no server.io**

### `SERVER_PORT` (Opcional)
- **Valor:** Porta SSH (padrão: 22)
- **Mesmo valor usado no server.io**

## 2. Configurar Serviços Systemd (Primeira Vez)

Após o primeiro deploy, configure os serviços:

```bash
# No servidor - Copiar ambos os serviços
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

**Editar variáveis de ambiente:**

```bash
# Editar serviço principal
sudo nano /etc/systemd/system/vpnserverio.service
```

Ajuste conforme necessário:
- `VPN_SERVER_NAME` - Nome da instância (ex: `vpn-server-usa`)
- `API_C_SHARP_URL` - URL da API C# (ex: `http://localhost:5000`)
- `PORT` - Porta do serviço (padrão: 8000)

**Nota:** O `routeros.service` usa o mesmo arquivo de ambiente (`/root/automais.io/vpnserver.env`).

## 3. Como Funciona o Deploy

No GitHub Actions, o workflow vai:
1. ✅ Fazer checkout do código
2. ✅ Criar pacote tar.gz
3. ✅ Copiar arquivos para `/root/automais.io/vpnserver.io/`
4. ✅ Instalar dependências Python
5. ✅ Copiar arquivos de serviço systemd (vpnserverio.service e routeros.service)
6. ✅ Reiniciar serviços vpnserverio.service e routeros.service

## 4. Executar Deploy

### Automático
- Push para `main` ou `master` → Deploy automático

### Manual
- **Actions → Deploy VPN Server → Run workflow**

## 5. Verificar Deploy

```bash
# Conectar ao servidor
ssh root@automais.io

# Verificar arquivos
ls -la ~/automais.io/vpnserver.io/

# Verificar serviços (se configurados)
sudo systemctl status vpnserverio.service
sudo systemctl status routeros.service
```

## Troubleshooting

### Erro: "Authentication failed"
- Verifique se `SERVER_PASSWORD` está correto no GitHub Secrets
- Use os mesmos secrets do repositório server.io

### Arquivos não copiados
- Verifique permissões: `chmod 755 /root/automais.io/vpnserver.io`
- Verifique logs do GitHub Actions

### Serviços não reiniciam
- O workflow procura por `vpnserverio.service` e `routeros.service`
- Se não encontrar, apenas copia arquivos (sem reiniciar)
- Configure os serviços na primeira vez conforme seção 2 acima
- Execute manualmente se necessário:
  ```bash
  sudo systemctl restart vpnserverio.service
  sudo systemctl restart routeros.service
  ```

### Erro ao instalar dependências
- Verifique se Python 3 está instalado: `python3 --version`
- Execute manualmente: `cd /root/automais.io/vpnserver.io && source venv/bin/activate && pip install -r requirements.txt`

