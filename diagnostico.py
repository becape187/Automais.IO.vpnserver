#!/usr/bin/env python3
"""
Script de diagnóstico para o serviço VPN Server
Verifica configurações e dependências antes de iniciar o serviço
"""
import os
import sys
import subprocess
from pathlib import Path

def check_env_file():
    """Verifica se o arquivo .env existe e está configurado"""
    env_path = Path("/root/automais.io/vpnserver.env")
    
    print("=" * 60)
    print("DIAGNÓSTICO DO SERVIÇO VPN SERVER")
    print("=" * 60)
    print()
    
    print("1. Verificando arquivo de configuração...")
    if not env_path.exists():
        print(f"   ❌ Arquivo não encontrado: {env_path}")
        print(f"   💡 Solução: Copie o arquivo vpnserver.env.example para {env_path}")
        print(f"   💡 Comando: cp /root/automais.io/vpnserver.io/vpnserver.env.example {env_path}")
        return False
    else:
        print(f"   ✅ Arquivo encontrado: {env_path}")
    
    # Verificar variáveis obrigatórias
    print()
    print("2. Verificando variáveis de ambiente...")
    required_vars = ["VPN_SERVER_ENDPOINT", "API_C_SHARP_URL"]
    missing_vars = []
    
    with open(env_path, 'r') as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" in content:
                # Extrair valor
                for line in content.split('\n'):
                    if line.strip().startswith(f"{var}="):
                        value = line.split('=', 1)[1].strip()
                        if value:
                            print(f"   ✅ {var}={value}")
                        else:
                            print(f"   ⚠️  {var} está vazio")
                            missing_vars.append(var)
                        break
            else:
                print(f"   ❌ {var} não encontrado no arquivo")
                missing_vars.append(var)
    
    if missing_vars:
        print()
        print(f"   ❌ Variáveis obrigatórias faltando: {', '.join(missing_vars)}")
        return False
    
    return True


def check_python_venv():
    """Verifica se o ambiente virtual Python existe"""
    print()
    print("3. Verificando ambiente virtual Python...")
    venv_path = Path("/root/automais.io/vpnserver.io/venv")
    
    if not venv_path.exists():
        print(f"   ❌ Ambiente virtual não encontrado: {venv_path}")
        print(f"   💡 Solução: Crie o ambiente virtual")
        print(f"   💡 Comando: cd /root/automais.io/vpnserver.io && python3 -m venv venv")
        return False
    else:
        print(f"   ✅ Ambiente virtual encontrado: {venv_path}")
    
    # Verificar se uvicorn está instalado
    uvicorn_path = venv_path / "bin" / "uvicorn"
    if not uvicorn_path.exists():
        print(f"   ❌ uvicorn não encontrado no ambiente virtual")
        print(f"   💡 Solução: Instale as dependências")
        print(f"   💡 Comando: {venv_path}/bin/pip install -r requirements.txt")
        return False
    else:
        print(f"   ✅ uvicorn encontrado")
    
    return True


def check_python_modules():
    """Verifica se os módulos Python necessários podem ser importados"""
    print()
    print("4. Verificando módulos Python...")
    
    venv_python = Path("/root/automais.io/vpnserver.io/venv/bin/python")
    if not venv_python.exists():
        print(f"   ❌ Python do venv não encontrado")
        return False
    
    # Tentar importar módulos principais
    modules = ["fastapi", "uvicorn", "httpx", "pydantic"]
    missing_modules = []
    
    for module in modules:
        try:
            result = subprocess.run(
                [str(venv_python), "-c", f"import {module}"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"   ✅ {module}")
            else:
                print(f"   ❌ {module} - Erro: {result.stderr.decode()[:50]}")
                missing_modules.append(module)
        except Exception as e:
            print(f"   ❌ {module} - Erro: {e}")
            missing_modules.append(module)
    
    if missing_modules:
        print()
        print(f"   ❌ Módulos faltando: {', '.join(missing_modules)}")
        print(f"   💡 Solução: Instale as dependências")
        print(f"   💡 Comando: {venv_python.parent}/pip install -r requirements.txt")
        return False
    
    return True


def check_wireguard():
    """Verifica se WireGuard está instalado"""
    print()
    print("5. Verificando WireGuard...")
    
    try:
        result = subprocess.run(
            ["wg", "--version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.decode().strip()
            print(f"   ✅ WireGuard instalado: {version}")
            return True
        else:
            print(f"   ❌ WireGuard não encontrado ou com erro")
            return False
    except FileNotFoundError:
        print(f"   ❌ WireGuard não está instalado")
        print(f"   💡 Solução: Instale o WireGuard")
        print(f"   💡 Comando: apt-get update && apt-get install -y wireguard")
        return False
    except Exception as e:
        print(f"   ❌ Erro ao verificar WireGuard: {e}")
        return False


def check_main_py():
    """Verifica se main.py pode ser importado sem erros"""
    print()
    print("6. Verificando main.py...")
    
    main_py = Path("/root/automais.io/vpnserver.io/main.py")
    if not main_py.exists():
        print(f"   ❌ main.py não encontrado")
        return False
    
    venv_python = Path("/root/automais.io/vpnserver.io/venv/bin/python")
    
    # Tentar compilar o arquivo para verificar sintaxe
    try:
        result = subprocess.run(
            [str(venv_python), "-m", "py_compile", str(main_py)],
            capture_output=True,
            timeout=10,
            cwd=str(main_py.parent)
        )
        if result.returncode == 0:
            print(f"   ✅ main.py compilado com sucesso")
            return True
        else:
            error = result.stderr.decode()
            print(f"   ❌ Erro ao compilar main.py:")
            print(f"   {error[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Erro ao verificar main.py: {e}")
        return False


def main():
    """Executa todas as verificações"""
    checks = [
        check_env_file,
        check_python_venv,
        check_python_modules,
        check_wireguard,
        check_main_py
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"   ❌ Erro na verificação: {e}")
            results.append(False)
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ TODAS AS VERIFICAÇÕES PASSARAM!")
        print("   O serviço deve estar pronto para iniciar.")
        return 0
    else:
        print("❌ ALGUMAS VERIFICAÇÕES FALHARAM")
        print("   Corrija os problemas acima antes de iniciar o serviço.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

