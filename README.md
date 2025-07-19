# prudentIA - Software Jurídico Inteligente

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.x-green.svg)](https://www.djangoproject.com/)
[![Redis](https://img.shields.io/badge/Redis-6.x-red.svg)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13%2B-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**prudentIA** é um sistema de gestão SaaS (Software as a Service) focado na advocacia brasileira. O projeto automatiza rotinas jurídicas (PJe, prazos, documentos, finanças) em uma plataforma única, extensível e **open-source**.

---

## Índice
1. [Sobre o Projeto](#sobre-o-projeto)  
2. [Principais Funcionalidades](#principais-funcionalidades)  
3. [Tecnologias](#tecnologias)  
4. [Primeiros Passos Rápidos](#primeiros-passos-rápidos)  
5. [Instalação Manual Detalhada](#instalação-manual-detalhada)  
6. [Execução](#execução)  
7. [Estrutura do Projeto](#estrutura-do-projeto)  
8. [Contribuição](#contribuição)  
9. [Licença](#licença)  

---

## Sobre o Projeto
**Objetivo** Aumentar a produtividade de advogados e escritórios, eliminando tarefas repetitivas e centralizando informações (processos, clientes, documentos, finanças).

**Público-Alvo** Advogados autônomos, pequenos e médios escritórios de advocacia.

---

## Principais Funcionalidades
* Monitoramento automático do PJe e outros tribunais.  
* Agenda inteligente de prazos, tarefas e kanban.  
* Assinatura digital de documentos com blockchain.  
* Integração Google Drive + OCR + geração automática de documentos.  
* Controle financeiro (boletos com PIX, fluxo de caixa).  
* Portal do cliente, integração WhatsApp.  
* Dashboards, IA (resumos, insights), logs de auditoria.  

Lista completa: [`docs/project_specs/funcionalidades_completas.md`](docs/project_specs/funcionalidades_completas.md)

---

## Tecnologias
Backend Python 3.10 / Django 4 · DRF · Celery · Redis · PostgreSQL  
OCR Tesseract · OpenCV · PyMuPDF · pdfplumber  
Blockchain Web3 (Ethereum / Hyperledger)  
NLP spaCy · NLTK  
Frontend (opcional) React 18 / Vue / Angular  
Contêineres Docker & Compose (em breve)

---

## Primeiros Passos Rápidos
O modo mais fácil para subir tudo em minutos é usar **os scripts de automação** já inclusos.

### Linux / macOS

```bash
git clone https://github.com/<seu-usuario>/prudentia.git
cd prudentia
chmod +x setup_environment.sh quickstart.sh
./setup_environment.sh      # cria venv, instala libs, gera .env, etc.
./quickstart.sh             # migra DB, cria superuser e sobe servidor
```

### Windows 10+

```powershell
git clone https://github.com/<seu-usuario>/prudentia.git
cd prudentia
setup_environment.bat       # configura ambiente
quickstart.bat              # migra DB, cria usuário e inicia o server
```

Os scripts são **idempotentes**: pode rodar quantas vezes precisar.

> Prefere Docker? Consulte a seção “Containers” em `INSTALLATION.md` (em preparação).

---

## Instalação Manual Detalhada
Se preferir cada passo na mão, siga o guia completo [`INSTALLATION.md`](INSTALLATION.md).  
Abaixo está um resumo simplificado.

1. **Pré-requisitos**  
   Python 3.10+, Git, PostgreSQL, Redis, Tesseract (`por`), Node (frontend).  

2. **Clonar e criar venv**  
   ```bash
   git clone https://github.com/<seu-usuario>/prudentia.git
   cd prudentia
   python -m venv venv && source venv/bin/activate        # linux/macOS
   # ou venv\Scripts\activate                              # windows
   ```

3. **Instalar dependências**  
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variáveis de ambiente**  
   ```bash
   cp env.example .env
   # edite .env (DB, Redis, chaves Google, etc.)
   ```

5. **Banco de dados**  
   SQLite para testes (padrão do `.env`) ou PostgreSQL:  
   ```sql
   CREATE DATABASE prudentia_db;
   CREATE USER prudentia_user WITH PASSWORD 'senha';
   GRANT ALL PRIVILEGES ON DATABASE prudentia_db TO prudentia_user;
   ```

6. **Migrações + superusuário**  
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. **Executar**  
   ```bash
   python manage.py runserver            # http://127.0.0.1:8000/
   celery -A prudentia worker -l info    # tarefas assíncronas
   celery -A prudentia beat   -l info    # agendador
   ```

---

## Execução
| Componente | Comando |
|------------|---------|
| Django dev server | `python manage.py runserver` |
| Celery worker | `celery -A prudentia worker -l info` |
| Celery beat | `celery -A prudentia beat -l info` |
| Testes | `pytest` |
| Cobertura | `coverage run -m pytest && coverage html` |

Para produção, utilize **Gunicorn/Uvicorn + Nginx** e configure variáveis `DEBUG=False` e `ALLOWED_HOSTS`.

---

## Estrutura do Projeto
Árvore simplificada (detalhe em [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)):

```
.
├── manage.py               # utilitário CLI Django
├── prudentia/              # configs (settings, urls, wsgi, asgi, celery)
├── apps/                   # aplicativos Django (accounts, documents, etc.)
│   └── <app>/migrations/
├── static/                 # assets coletados
├── templates/              # base.html, etc.
├── docs/                   # documentação (arquitetura, design)
├── requirements.txt
├── env.example
└── scripts
    ├── setup_environment.sh / .bat
    ├── quickstart.sh / .bat
```

---

## Contribuição
1. Abra uma **issue** para bugs/idéias.  
2. Fork → branch (`feat/x`, `fix/y`) → PR.  
3. Siga padrão **Commit Semântico** + `pre-commit`.  
4. Inclua **testes** e atualize docs.

---

## Licença
Distribuído sob licença **MIT**. Consulte o arquivo [`LICENSE`](LICENSE).

---

Feito com ❤️ para a comunidade jurídica brasileira – **Pratique o código aberto!**
