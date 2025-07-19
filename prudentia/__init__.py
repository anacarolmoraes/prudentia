"""
Inicialização do pacote prudentia.
Este arquivo importa a aplicação Celery para garantir que ela seja carregada
quando o Django iniciar.
"""

# Importar a aplicação Celery
from .celery import app as celery_app

# Definir quais símbolos serão exportados quando alguém fizer "from prudentia import *"
__all__ = ['celery_app']
