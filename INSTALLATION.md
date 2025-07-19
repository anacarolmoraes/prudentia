# prudentIA – Guia de Instalação Completo

Este documento explica **passo a passo** como preparar sua máquina para executar o projeto **prudentIA** em modo de desenvolvimento (ou produção simples).  

Índice rápido:
1. Pré-requisitos  
2. Clonagem do repositório  
3. Criação e ativação do ambiente virtual  
4. Instalação de dependências Python (`requirements.txt`)  
5. Instalação de dependências do sistema operacional  
6. Configuração das variáveis de ambiente (`.env`)  
7. Configuração do banco de dados  
8. Aplicação de migrações e criação de superusuário  
9. Execução da aplicação (Django + Celery)  
10. Testes automatizados  
11. Docker (opcional)  
12. Solução de problemas comuns  

---

## 1. Pré-requisitos

| Ferramenta | Versão recomendada | Observações |
|------------|-------------------|-------------|
| Python     | 3.10 +            | Inclua `pip` |
| Git        | Qualquer          | Para clonar o repo |
| PostgreSQL | 13 +              | Produção / testes avançados |
| Redis      | 6 +               | Broker do Celery |
| Tesseract  | 5 +               | OCR de documentos |
| Node.js    | 18 +              | Apenas se for mexer no frontend |

> Se preferir contêineres, pule para a seção **Docker**.

---

## 2. Clonagem do repositório

```bash
git clone https://github.com/anacarolmoraes/prudentia.git
cd prudentia
```

---

## 3. Ambiente virtual

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

Você saberá que o *venv* está ativo quando vir “(venv)” no prompt.  
Para sair use `deactivate`.

---

## 4. Instalação das dependências Python

Atualize o pip e instale tudo do `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Principais libs instaladas:

* Django 4
* Django REST Framework
* Celery + Redis
* Psycopg2-binary (PostgreSQL)
* Pillow, PyMuPDF, pytesseract
* httpx, selectolax
* Google API Client
* Web3
* Ferramentas de qualidade: black, flake8, pytest, etc.

---

## 5. Dependências do sistema operacional

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y build-essential libpq-dev redis-server \
                    tesseract-ocr tesseract-ocr-por \
                    libjpeg-dev zlib1g-dev libpoppler-cpp-dev
```

### macOS (Homebrew)

```bash
brew update
brew install postgresql redis tesseract
brew install tesseract-lang    # adiciona idioma PT-BR
```

### Windows

1. PostgreSQL: https://www.postgresql.org/download/windows/  
2. Redis: https://github.com/tporadowski/redis/releases  
3. Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki  
   *Adicione `tesseract.exe` ao **PATH***.

---

## 6. Configuração do `.env`

Copie o template e edite:

```bash
cp env.example .env
```

Campos essenciais:

```
SECRET_KEY=troque-por-uma-chave-segura
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# SQLite rápido
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# ou PostgreSQL
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=prudentia_db
# DB_USER=prudentia_user
# DB_PASSWORD=senha
# DB_HOST=localhost
# DB_PORT=5432
```

Acrescente chaves da Google API, Blockchain, etc., se for usar esses recursos.

---

## 7. Banco de dados

### 7.1 SQLite (desenvolvimento rápido)

Nada a fazer além de manter as variáveis acima.

### 7.2 PostgreSQL

```sql
CREATE DATABASE prudentia_db;
CREATE USER prudentia_user WITH PASSWORD 'senha_forte';
GRANT ALL PRIVILEGES ON DATABASE prudentia_db TO prudentia_user;
```

Atualize o `.env` com as credenciais.

---

## 8. Migrações e superusuário

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## 9. Execução da aplicação

### 9.1 Servidor Django

```bash
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

### 9.2 Workers Celery (opcional)

Em terminais separados, **com o venv ativo**:

```bash
# Worker
celery -A prudentia worker -l info

# Scheduler (tarefas periódicas)
celery -A prudentia beat -l info
```

---

## 10. Testes

```bash
pytest
coverage run -m pytest && coverage html  # relatório de cobertura
```

---

## 11. Docker (opcional)

Existe um arquivo `docker-compose.yml`?  
Se sim, execute:

```bash
docker compose up --build
```

Isso levanta web, postgres, redis e workers Celery.

Se não existir, siga o guia tradicional acima ou crie seus próprios serviços.

---

## 12. Solução de problemas comuns

| Erro | Possíveis causas / correção |
|------|-----------------------------|
| `ModuleNotFoundError: prudentia.settings` | Arquivos de configuração não movidos para `prudentia/` ou falta de `__init__.py`. |
| `psycopg2` falha ao compilar | Instale `libpq-dev` (Linux) ou *Build Tools* (Windows). |
| `TesseractNotFoundError` | Binário não está no PATH ou `TESSERACT_CMD` incorreto no `.env`. |
| Worker Celery não conecta | Redis não em execução ou URL errada em `CELERY_BROKER_URL`. |
| `django.core.exceptions.ImproperlyConfigured: SECRET_KEY` | Esqueceu de definir `SECRET_KEY` no `.env`. |

---

🎉 **Pronto!** Seu ambiente está configurado. Comece a codar, rodar seus testes e evoluir o prudentIA. Se algo der errado, leia novamente o passo correspondente ou abra uma issue.  
