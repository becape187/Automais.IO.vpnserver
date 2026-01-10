# Configuração do VPN Server - Arquivo vpnserver.env

O serviço VPN Server lê suas configurações de um arquivo `.env` localizado em `/root/automais.io/vpnserver.env`.

Isso permite que cada servidor tenha sua própria configuração personalizada sem modificar o arquivo de serviço systemd.

---

## 📍 Localização do Arquivo

O arquivo de configuração deve estar em:

```
/root/automais.io/vpnserver.env
```

**Importante:** O arquivo é lido pelo systemd, então ele deve existir antes de iniciar o serviço.

---

## 📝 Formato do Arquivo

O arquivo `vpnserver.env` deve seguir o formato padrão de variáveis de ambiente:

```bash
# Linhas começando com # são comentários e são ignoradas
# Não use aspas ao redor dos valores
# Não deixe espaços antes ou depois do sinal de igual

VPN_SERVER_NAME=automais.io
API_C_SHARP_URL=http://localhost:5000
SYNC_INTERVAL_SECONDS=60
PORT=8000
WIREGUARD_CONFIG_DIR=/etc/wireguard
```

---

## 🔧 Variáveis de Ambiente Disponíveis

### `VPN_SERVER_NAME` (Obrigatório)

**Descrição:** Nome identificador desta instância do servidor VPN.

**Uso:** O serviço usa este nome para consultar a API C# e descobrir quais recursos (VpnNetworks e Routers) ele deve gerenciar.

**Exemplo:**
```bash
VPN_SERVER_NAME=automais.io
```

**Valores comuns:**
- `automais.io` - Servidor principal
- `vpn-server-usa` - Servidor VPN nos EUA
- `vpn-server-brasil` - Servidor VPN no Brasil
- `vpn-server-europa` - Servidor VPN na Europa

**⚠️ Importante:** Este valor deve corresponder ao campo `ServerName` de um registro `VpnServer` no banco de dados da API C#.

---

### `API_C_SHARP_URL` (Opcional)

**Descrição:** URL base da API C# principal.

**Padrão:** `http://localhost:5000`

**Exemplo:**
```bash
API_C_SHARP_URL=http://localhost:5000
```

**Para acesso remoto:**
```bash
API_C_SHARP_URL=http://srv01.automais.io:5000
```

**Para HTTPS:**
```bash
API_C_SHARP_URL=https://api.automais.io
```

---

### `SYNC_INTERVAL_SECONDS` (Opcional)

**Descrição:** Intervalo em segundos entre sincronizações automáticas com a API C#.

**Padrão:** `60` (1 minuto)

**Exemplo:**
```bash
SYNC_INTERVAL_SECONDS=60
```

**Valores recomendados:**
- `30` - Sincronização rápida (mais carga no servidor)
- `60` - Padrão (balanceado)
- `120` - Sincronização lenta (menos carga)

---

### `PORT` (Opcional)

**Descrição:** Porta na qual o serviço FastAPI será executado.

**Padrão:** `8000`

**Exemplo:**
```bash
PORT=8000
```

**Importante:** Se você alterar esta porta, também deve atualizar o `ExecStart` no arquivo de serviço systemd:

```ini
ExecStart=/root/automais.io/vpnserver.io/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Altere `--port 8000` para a porta desejada.

---

### `WIREGUARD_CONFIG_DIR` (Opcional)

**Descrição:** Diretório onde os arquivos de configuração do WireGuard serão armazenados.

**Padrão:** `/etc/wireguard`

**Exemplo:**
```bash
WIREGUARD_CONFIG_DIR=/etc/wireguard
```

**⚠️ Importante:** O usuário que executa o serviço (geralmente `root`) deve ter permissões de escrita neste diretório.

---

## 📋 Exemplo Completo de Arquivo

Aqui está um exemplo completo do arquivo `vpnserver.env`:

```bash
# ============================================
# Configuração do VPN Server
# ============================================
# Este arquivo é lido pelo systemd ao iniciar o serviço vpnserverio.service
# Localização: /root/automais.io/vpnserver.env

# Nome identificador deste servidor VPN (OBRIGATÓRIO)
# Deve corresponder ao ServerName no banco de dados
VPN_SERVER_NAME=automais.io

# URL da API C# principal
API_C_SHARP_URL=http://localhost:5000

# Intervalo de sincronização com a API (em segundos)
SYNC_INTERVAL_SECONDS=60

# Porta do serviço FastAPI
PORT=8000

# Diretório de configuração do WireGuard
WIREGUARD_CONFIG_DIR=/etc/wireguard
```

---

## 🚀 Como Criar/Editar o Arquivo

### Via SSH:

```bash
# Criar/editar o arquivo
sudo nano /root/automais.io/vpnserver.env

# Ou usando vim
sudo vim /root/automais.io/vpnserver.env
```

### Verificar se o arquivo existe:

```bash
ls -la /root/automais.io/vpnserver.env
```

### Verificar conteúdo:

```bash
cat /root/automais.io/vpnserver.env
```

---

## ✅ Validação e Teste

### 1. Verificar se o arquivo está correto:

```bash
# Verificar sintaxe (sem erros de formato)
cat /root/automais.io/vpnserver.env | grep -v "^#" | grep "="
```

### 2. Testar carregamento pelo systemd:

```bash
# Recarregar systemd para ler o arquivo
sudo systemctl daemon-reload

# Verificar variáveis de ambiente do serviço
sudo systemctl show vpnserverio.service | grep Environment
```

### 3. Reiniciar o serviço:

```bash
sudo systemctl restart vpnserverio.service
```

### 4. Verificar logs:

```bash
# Ver logs do serviço
sudo journalctl -u vpnserverio.service -f

# Verificar se o VPN_SERVER_NAME foi lido corretamente
sudo journalctl -u vpnserverio.service | grep "VPN_SERVER_NAME"
```

---

## 🔄 Múltiplos Servidores VPN

Se você tiver múltiplos servidores VPN, cada um deve ter seu próprio arquivo `vpnserver.env` com configurações diferentes:

### Servidor 1 (EUA):
```bash
# /root/automais.io/vpnserver.env no servidor USA
VPN_SERVER_NAME=vpn-server-usa
API_C_SHARP_URL=http://api.automais.io:5000
PORT=8000
```

### Servidor 2 (Brasil):
```bash
# /root/automais.io/vpnserver.env no servidor Brasil
VPN_SERVER_NAME=vpn-server-brasil
API_C_SHARP_URL=http://api.automais.io:5000
PORT=8000
```

**Nota:** Ambos podem usar a mesma porta se estiverem em servidores diferentes.

---

## 🛠️ Troubleshooting

### Problema: Serviço não inicia

**Sintoma:** `systemctl status vpnserverio.service` mostra erro

**Solução:**
```bash
# Verificar se o arquivo existe
ls -la /root/automais.io/vpnserver.env

# Verificar permissões (deve ser legível)
chmod 644 /root/automais.io/vpnserver.env

# Verificar sintaxe do arquivo
cat /root/automais.io/vpnserver.env
```

### Problema: Variáveis não são carregadas

**Sintoma:** O serviço inicia mas não encontra `VPN_SERVER_NAME`

**Solução:**
```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Reiniciar serviço
sudo systemctl restart vpnserverio.service

# Verificar variáveis carregadas
sudo systemctl show vpnserverio.service --property=Environment
```

### Problema: Erro de permissão no WIREGUARD_CONFIG_DIR

**Sintoma:** Erro ao criar arquivos em `/etc/wireguard`

**Solução:**
```bash
# Verificar permissões do diretório
ls -ld /etc/wireguard

# Garantir que o diretório existe
sudo mkdir -p /etc/wireguard
sudo chmod 755 /etc/wireguard
```

---

## 📚 Referências

- [Systemd EnvironmentFile](https://www.freedesktop.org/software/systemd/man/systemd.exec.html#EnvironmentFile=)
- [FastAPI Configuration](https://fastapi.tiangolo.com/advanced/settings/)
- [WireGuard Documentation](https://www.wireguard.com/)

---

## 🔐 Segurança

⚠️ **Importante:** O arquivo `vpnserver.env` pode conter informações sensíveis (URLs, tokens, etc.).

**Recomendações:**
- Mantenha o arquivo com permissões restritas: `chmod 600 /root/automais.io/vpnserver.env`
- Não commite o arquivo no Git (já está no `.gitignore`)
- Use HTTPS para `API_C_SHARP_URL` em produção
- Considere usar secrets management para produção (HashiCorp Vault, AWS Secrets Manager, etc.)

