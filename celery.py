import os
from celery import Celery

# Defina o módulo de configurações padrão do Django para o 'celery'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings')

app = Celery('prudentia')

# Usar uma string aqui significa que o worker não precisa serializar
# o objeto de configuração para processos filhos.
# - namespace='CELERY' significa que todas as chaves de configuração do Celery
#   devem ter um prefixo `CELERY_`.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carregar módulos de tarefas de todas as aplicações Django registradas.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
