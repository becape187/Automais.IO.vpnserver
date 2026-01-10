"""
Funções utilitárias
"""
import subprocess
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def execute_command(command: str, check: bool = True) -> tuple[str, str, int]:
    """Executa um comando shell e retorna (stdout, stderr, returncode)"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if check and result.returncode != 0:
            logger.error(f"Comando falhou: {command}, Erro: {result.stderr}")
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout ao executar comando: {command}")
        raise HTTPException(status_code=504, detail="Timeout ao executar comando")
    except Exception as e:
        logger.error(f"Erro ao executar comando {command}: {e}")
        if check:
            raise HTTPException(status_code=500, detail=f"Erro ao executar comando: {str(e)}")
        return "", str(e), 1


def parse_size_to_bytes(size_str: str) -> int:
    """Converte string de tamanho (ex: '1.23 MiB') para bytes"""
    try:
        size_str = size_str.strip().lower()
        multipliers = {
            'b': 1,
            'kib': 1024,
            'mib': 1024 * 1024,
            'gib': 1024 * 1024 * 1024,
            'kb': 1000,
            'mb': 1000 * 1000,
            'gb': 1000 * 1000 * 1000
        }
        
        for unit, multiplier in multipliers.items():
            if unit in size_str:
                number_str = size_str.replace(unit, '').strip()
                number = float(number_str)
                return int(number * multiplier)
        
        # Se não encontrou unidade, assumir bytes
        return int(float(size_str))
    except:
        return 0


def format_bytes(bytes_value: int) -> str:
    """Formata bytes para string legível"""
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PiB"

