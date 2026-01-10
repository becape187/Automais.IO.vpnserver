"""
Configurações do serviço VPN
"""
import os
import logging

logger = logging.getLogger(__name__)

# Configuração via variáveis de ambiente
VPN_SERVER_ENDPOINT = os.getenv("VPN_SERVER_ENDPOINT", "")
API_C_SHARP_URL = os.getenv("API_C_SHARP_URL", "http://localhost:5000")
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))
WIREGUARD_CONFIG_DIR = os.getenv("WIREGUARD_CONFIG_DIR", "/etc/wireguard")
PORT = int(os.getenv("PORT", "8000"))

if not VPN_SERVER_ENDPOINT:
    logger.warning("⚠️ VPN_SERVER_ENDPOINT não configurado! O serviço não saberá quais recursos gerenciar.")

