# Estrutura de Diretórios do Projeto prudentIA

Este documento detalha a estrutura de diretórios recomendada para o projeto prudentIA, um sistema SaaS para advogados. A estrutura visa organizar o código de forma lógica, facilitando o desenvolvimento, manutenção e escalabilidade.

```
prudentia_project/
├── .git/
├── .github/
│   └── workflows/
├── prudentia/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── __init__.py
│   ├── accounts/
│   ├── clients/
│   ├── core/
│   ├── deadlines/
│   ├── documents/
│   ├── finance/
│   ├── forms_integration/
│   ├── notifications/
│   ├── pje_monitoring/
│   ├── processes/
│   └── signatures/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── templates/
│   └── base.html
├── media/
├── tests/
├── venv/
├── docs/
│   ├── api/
│   ├── architecture/
│   │   ├── arquitetura_sistema.md
│   │   └── estrutura_projeto.md
│   ├── design/
│   │   ├── color_scheme.md
│   │   ├── dashboard_interface.html
│   │   ├── homepage_design.html
│   │   └── signature_interface.html
│   ├── project_specs/
│   │   └── funcionalidades_completas.md
│   └── user_guide/
├── scripts/
├── .env.example
├── .gitignore
├── manage.py
├── Pipfile
├── README.md
├── docker-compose.yml
└── Dockerfile
```

## Descrição dos Diretórios e Arquivos

### Raiz do Projeto (`prudentia_project/`)

*   **`.git/`**: Diretório interno do Git, armazena o histórico de versões e metadados do repositório.
*   **`.github/`**: Contém configurações específicas do GitHub.
    *   **`workflows/`**: Arquivos de configuração para GitHub Actions (CI/CD), como automação de testes, linting e deploy.
*   **`prudentia/`**: Diretório principal do projeto Django. O nome deste diretório é o nome do seu projeto Django.
    *   **`__init__.py`**: Indica ao Python que este diretório deve ser tratado como um pacote.
    *   **`asgi.py`**: Ponto de entrada para servidores web compatíveis com ASGI (Asynchronous Server Gateway Interface), usado para deploy assíncrono (ex: com Daphne ou Uvicorn).
    *   **`settings.py`**: Arquivo de configurações do projeto Django (banco de dados, apps instalados, middleware, caminhos de templates, etc.).
    *   **`urls.py`**: Definições de URL de nível de projeto. Rotas principais que direcionam para as URLs das aplicações (`apps/`).
    *   **`wsgi.py`**: Ponto de entrada para servidores web compatíveis com WSGI (Web Server Gateway Interface), usado para deploy síncrono (ex: com Gunicorn).
*   **`apps/`**: Contém as diferentes aplicações (módulos) do seu projeto Django. Cada subdiretório aqui é uma aplicação Django separada, focada em uma funcionalidade específica.
    *   **`__init__.py`**: Torna o diretório `apps/` um pacote Python.
    *   **`accounts/`**: Aplicação para gerenciamento de usuários, autenticação (login, registro, recuperação de senha), perfis de usuário e permissões.
    *   **`clients/`**: Aplicação para gestão de clientes, incluindo cadastro, histórico, e funcionalidades do "Portal do Cliente".
    *   **`core/`**: Aplicação para funcionalidades centrais, modelos base, classes utilitárias, helpers e lógica de negócio que é compartilhada por múltiplas aplicações.
        *   `admin.py`: Configuração da interface de administração do Django para os modelos desta app.
        *   `apps.py`: Configuração da aplicação.
        *   `models.py`: Definição dos modelos de dados (tabelas do banco de dados).
        *   `services.py`: Lógica de negócio e serviços relacionados à aplicação.
        *   `tests/`: Testes unitários e de integração para a aplicação.
        *   `views.py`: Lógica de controle que lida com requisições HTTP e retorna respostas (geralmente HTML ou JSON).
    *   **`deadlines/`**: Aplicação para gestão de prazos processuais, tarefas, agenda e compromissos.
    *   **`documents/`**: Aplicação para gerenciamento de documentos, incluindo upload, armazenamento (possivelmente integrado com Google Drive), versionamento, templates de documentos, OCR e extração de dados de PDFs. O arquivo `google_drive_integration.py` e partes do `document_processing.py` residiriam aqui.
    *   **`finance/`**: Aplicação para o módulo financeiro, incluindo controle de honorários, emissão de boletos, integração com PIX, fluxo de caixa e relatórios financeiros.
    *   **`forms_integration/`**: Aplicação para integração com formulários externos, como Google Forms, e processamento de suas respostas. O arquivo `external_forms.py` e partes do `document_processing.py` (relacionadas a formulários) estariam aqui.
    *   **`notifications/`**: Aplicação para o sistema de notificações (e-mail, WhatsApp, in-app alerts).
    *   **`pje_monitoring/`**: Aplicação dedicada ao monitoramento de publicações do PJe e outros tribunais. O arquivo `pje_scraper.py` e `pje_monitor_service.py` seriam parte desta app.
    *   **`processes/`**: Aplicação para gestão de processos judiciais e casos, incluindo cadastro, acompanhamento de fases, partes envolvidas e histórico.
    *   **`signatures/`**: Aplicação para a funcionalidade de assinatura digital com blockchain. O arquivo `signature_service.py` e a interface `signature_interface.html` (ou seus componentes de frontend) estariam relacionados a esta app.
*   **`static/`**: Armazena arquivos estáticos globais do projeto, como CSS, JavaScript e imagens que não são específicos de uma aplicação.
    *   **`css/`**: Arquivos CSS.
    *   **`js/`**: Arquivos JavaScript.
    *   **`images/`**: Imagens.
*   **`templates/`**: Contém templates HTML globais do projeto, como o `base.html` que pode ser estendido por templates de aplicações específicas.
    *   **`base.html`**: Template base HTML.
*   **`media/`**: Diretório onde os arquivos enviados pelos usuários (uploads) são armazenados durante o desenvolvimento. Em produção, este diretório geralmente é servido por um servidor de mídia dedicado ou um serviço de armazenamento em nuvem (como AWS S3 ou Google Cloud Storage).
*   **`tests/`**: Diretório para testes de integração e end-to-end que cobrem múltiplas aplicações ou o projeto como um todo. Testes específicos de cada app ficam dentro do diretório `tests/` da respectiva app.
*   **`venv/`**: Diretório do ambiente virtual Python. Este diretório é geralmente adicionado ao `.gitignore` para não ser versionado.
*   **`docs/`**: Contém toda a documentação do projeto.
    *   **`api/`**: Documentação da API (gerada por ferramentas como Swagger/OpenAPI).
    *   **`architecture/`**: Diagramas de arquitetura, decisões de design e outros documentos relacionados à arquitetura do sistema. Os arquivos `arquitetura_sistema.md` e `estrutura_projeto.md` (este arquivo) ficariam aqui.
    *   **`design/`**: Arquivos relacionados ao design da interface e experiência do usuário, como mockups, esquemas de cores. Os arquivos `color_scheme.md`, `dashboard_interface.html`, `homepage_design.html`, e `signature_interface.html` seriam colocados aqui.
    *   **`project_specs/`**: Especificações funcionais e de requisitos do projeto. O arquivo `funcionalidades_completas.md` seria colocado aqui.
    *   **`user_guide/`**: Manuais e guias para os usuários finais do sistema.
*   **`scripts/`**: Contém scripts utilitários para automação de tarefas, como deploy, backup, manutenção do banco de dados, etc.
*   **`.env.example`**: Arquivo de exemplo para variáveis de ambiente. Desenvolvedores devem copiar este arquivo para `.env` (que estará no `.gitignore`) e preencher com suas configurações locais.
*   **`.gitignore`**: Especifica arquivos e diretórios que devem ser ignorados pelo Git (ex: `venv/`, `__pycache__/`, arquivos `.env`, `media/` se não for para versionar, etc.).
*   **`manage.py`**: Utilitário de linha de comando do Django para interagir com o projeto (ex: rodar o servidor de desenvolvimento, criar migrações, rodar testes, etc.).
*   **`Pipfile`** (ou `requirements.txt`): Arquivo que lista as dependências Python do projeto. `Pipfile` é usado com `pipenv`, enquanto `requirements.txt` é usado com `pip`.
*   **`README.md`**: Arquivo principal com informações sobre o projeto: descrição, como configurar o ambiente de desenvolvimento, como rodar o projeto, etc.
*   **`docker-compose.yml`**: (Opcional) Arquivo de configuração para Docker Compose, usado para definir e rodar aplicações multi-container Docker (ex: aplicação web, banco de dados, Redis, Celery).
*   **`Dockerfile`**: (Opcional) Arquivo de configuração para construir a imagem Docker da aplicação.

### Estrutura Interna de uma Aplicação Django (ex: `apps/processes/`)

Cada diretório dentro de `apps/` (como `apps/processes/`) geralmente segue uma estrutura padrão do Django:

```
apps/processes/
├── __init__.py
├── admin.py         # Configuração da interface de admin do Django para os modelos desta app
├── apps.py          # Configuração da aplicação (ex: nome da app)
├── forms.py         # Definição de formulários Django (se usar Django Forms)
├── migrations/      # Migrações do banco de dados geradas pelo Django
│   └── __init__.py
├── models.py        # Definição dos modelos de dados (tabelas)
├── serializers.py   # (Se usar Django REST Framework) Serializers para converter modelos em JSON/XML
├── services.py      # Lógica de negócio e serviços específicos desta app
├── static/          # Arquivos estáticos específicos desta app (se houver)
│   └── processes/
│       ├── css/
│       └── js/
├── templates/       # Templates HTML específicos desta app
│   └── processes/
│       └── process_list.html
├── tests/           # Testes unitários e de integração para esta app
│   ├── __init__.py
│   ├── test_models.py
│   └── test_views.py
├── urls.py          # Definições de URL específicas desta app
└── views.py         # Lógica de controle (views) para esta app
```

Esta estrutura modular ajuda a manter o código organizado e facilita a colaboração e manutenção à medida que o projeto cresce.
