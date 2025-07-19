# Estrutura do Projeto **prudentIA**

Este documento descreve a organização dos diretórios e arquivos principais do projeto **prudentIA**, detalhando a função de cada componente. Use-o como guia rápido para navegação e contribuição no código-base.

---

## Visão Geral do Diretório Raiz

```
.
├── manage.py
├── prudentia/                ← Pacote de configuração do Django
├── apps/                     ← Módulos funcionais da aplicação
├── static/                   ← Arquivos estáticos (CSS, JS, imagens)
├── templates/                ← Templates HTML base
├── docs/                     ← Documentação técnica e de design
├── requirements.txt          ← Dependências Python
├── .env.example              ← Exemplo de variáveis de ambiente
├── .gitignore
└── README.md
```

---

## Arquivos de Configuração de Alto Nível

| Arquivo / Pasta | Função |
|-----------------|--------|
| **manage.py** | Executa comandos administrativos do Django (runserver, migrate, etc.). |
| **requirements.txt** | Lista todas as bibliotecas Python necessárias. |
| **.env.example** | Modelo de configuração de variáveis de ambiente; copie para `.env`. |
| **.gitignore** | Define quais arquivos/pastas não devem ser versionados (logs, venv, etc.). |
| **README.md** | Visão geral do projeto, instruções de uso rápido. |

---

## Pacote `prudentia/`

| Arquivo | Descrição |
|---------|-----------|
| **\_\_init\_\_.py** | Inicializa o pacote e carrega a instância Celery (`celery_app`). |
| **settings.py** | Configurações globais do Django (DB, apps instalados, middleware, etc.). |
| **urls.py** | Roteamento principal da aplicação. |
| **wsgi.py** | Ponto de entrada WSGI para servidores como Gunicorn. |
| **asgi.py** | Ponto de entrada ASGI (suporte a WebSockets/HTTP2). |
| **celery.py** | Configuração da fila Celery para tarefas assíncronas. |

---

## Diretório `apps/`

Cada subpasta em `apps/` é um **Django App** independente, responsável por um domínio funcional. Todos seguem a mesma estrutura básica (`models.py`, `views.py`, `admin.py`, `tests.py`, `migrations/`).

| App | Responsabilidade Principal |
|-----|----------------------------|
| **accounts** | Autenticação, perfis de usuário, permissões. |
| **clients** | Dados e relacionamento com clientes. |
| **core** | Funcionalidades transversais (mixins, utilidades). |
| **deadlines** | Gestão de prazos processuais. |
| **documents** | Gerenciamento de documentos e integração com Google Drive. |
| **finance** | Módulo financeiro (boletos, PIX, faturas). |
| **forms_integration** | Integração com formulários externos (Google Forms, etc.). |
| **notifications** | Sistema de notificações (email, push). |
| **pje_monitoring** | Robôs de scraping e monitoramento do sistema PJe. |
| **processes** | Fluxo e estados de processos jurídicos. |
| **signatures** | Assinatura digital de documentos (incl. blockchain). |

### Estrutura típica de um app

```
apps/<app_name>/
├── __init__.py
├── admin.py          ← Registra modelos no Django Admin
├── apps.py           ← Configuração do AppConfig
├── models.py         ← Definições ORM
├── views.py          ← Lógica de controle / API
├── urls.py           ← Rotas do app (opcional)
├── tests.py          ← Testes unitários
└── migrations/       ← Histórico de migrações do banco
```

---

## Diretórios de Suporte

| Pasta | Conteúdo | Observações |
|-------|----------|-------------|
| **static/** | CSS, JS, imagens, fontes. | Coletados em produção com `collectstatic`. |
| **templates/** | Arquivos HTML Jinja/Django. | `base.html` define o layout principal. |
| **media/** | Arquivos enviados por usuários. | Criada em tempo de execução; ignorada no Git. |
| **logs/** | Logs gerados pela aplicação e Celery. | Útil para debug; também ignorada no Git. |
| **docs/** | Markdown, diagramas e mockups. | Mantém documentação de arquitetura e UI. |
| **venv/** | Ambiente virtual Python. | Nunca versionar. |

---

## Scripts Auxiliares

| Script | Uso |
|--------|-----|
| **setup_environment.sh** | Automatiza criação de venv, instalação de dependências e preparação de diretórios (Linux/macOS). |
| **setup_environment.bat** | Mesmo propósito em ambiente Windows. |

---

## Fluxo de Execução

1. **Ativar ambiente virtual**  
2. **`python manage.py migrate`** – aplica migrações.  
3. **`python manage.py createsuperuser`** – cria admin.  
4. **`python manage.py runserver`** – inicia servidor de desenvolvimento.  
5. (Opcional) **`celery -A prudentia worker -l info`** – inicia workers.  

---

## Observações Finais

* Mantenha **.env** fora do controle de versão — armazena chaves e senhas.
* Cada app deve conservar **testes** em `tests.py` ou pasta `tests/`.
* Documentação adicional: consulte `docs/architecture` e `INSTALLATION.md`.

Contribuições são bem-vindas! Siga o padrão de commits semânticos e garanta cobertura de testes ao enviar um Pull Request.
