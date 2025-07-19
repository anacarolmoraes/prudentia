# prudentIA – Guia de Configuração de Ambiente

Este documento orienta, passo a passo, a preparar **qualquer máquina** (Windows, macOS ou Linux) para executar o projeto **prudentIA** em modo de desenvolvimento.

---

## Índice

1. Pré-requisitos gerais  
2. Clonagem do repositório  
3. Criação do ambiente virtual  
4. Ativação do ambiente virtual  
5. Instalação das dependências Python  
6. Instalação de dependências do sistema operacional  
7. Configuração do arquivo `.env`  
8. Verificação da instalação  
9. Próximos passos  
10. Solução de problemas comuns  

---

## 1. Pré-requisitos gerais

Ferramenta | Versão recomendada | Observações
-----------|-------------------|------------
Python     | 3.10 ou superior  | Necessário `pip` embutido
Git        | qualquer          | Para clonar o repositório
PostgreSQL | 13+ (opcional)    | Produção / testes avançados
Redis      | 6+ (opcional)     | Usado pelo Celery
Tesseract OCR | 5+ (opcional) | OCR de documentos

> Se preferir, você pode usar **Docker** para tudo, porém este guia cobre a instalação tradicional.

---

## 2. Clonagem do repositório

```bash
git clone https://github.com/anacarolmoraes/prudentia.git
cd prudentia
```

---

## 3. Criação do ambiente virtual

### Linux / macOS

```bash
python3 -m venv venv
```

### Windows (PowerShell ou CMD)

```powershell
python -m venv venv
```

> O diretório `venv` pode ter qualquer nome, mas “venv” é o padrão usado neste guia.

---

## 4. Ativação do ambiente virtual

Sistema | Comando
--------|---------
Linux / macOS (bash/zsh) | `source venv/bin/activate`
Windows – PowerShell     | `venv\Scripts\Activate.ps1`
Windows – CMD            | `venv\Scripts\activate.bat`

Você saberá que o **venv** está ativo quando aparecer `(venv)` no início da linha de comando.  
Para **desativar**, digite `deactivate`.

---

## 5. Instalação das dependências Python

1. Atualize o `pip`:

   ```bash
   pip install --upgrade pip
   ```

2. Instale todas as libs listadas em `requirements.txt`:

   ```bash
   pip install -r requirements.txt
   ```

Principais bibliotecas instaladas:

- Django 4, Django REST Framework  
- Celery + Redis  
- Psycopg2‐binary (PostgreSQL)  
- httpx, selectolax (web-scraping)  
- Pillow, PyMuPDF, pytesseract (PDF / OCR)  
- Google API Client  
- Web3 (blockchain)  

---

## 6. Instalação de dependências do sistema operacional

Alguns pacotes Python precisam de bibliotecas nativas.

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y build-essential libpq-dev redis-server \
                    tesseract-ocr tesseract-ocr-por \
                    libjpeg-dev zlib1g-dev libopencv-dev
```

### macOS (Homebrew)

```bash
brew update
brew install postgresql redis tesseract
brew install tesseract-lang        # adiciona idioma pt-BR
```

### Windows

1. PostgreSQL: https://www.postgresql.org/download/windows/  
2. Redis: https://github.com/microsoftarchive/redis/releases  
3. Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki  
   - Inclua `tesseract.exe` no **PATH**

---

## 7. Configuração do arquivo `.env`

1. Copie o template:

   ```bash
   cp env.example .env
   ```

2. Edite o `.env` com pelo menos:

   ```dotenv
   SECRET_KEY=sua-chave-segura
   DB_ENGINE=django.db.backends.sqlite3   # ou postgresql
   DB_NAME=db.sqlite3
   ```

3. Se usar Redis/Celery, confirme:

   ```dotenv
   CELERY_BROKER_URL=redis://localhost:6379/0
   ```

---

## 8. Verificação da instalação

Dentro do **venv**:

```bash
python -m django --version                # deve exibir 4.x
python -c "import rest_framework, celery, PIL, pytesseract; print('Import OK')" 
```

Se tudo carregar sem erros, prossiga.

---

## 9. Próximos passos

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Em terminais separados (opcional):

```bash
celery -A prudentia worker -l info
celery -A prudentia beat   -l info
```

Acesse `http://127.0.0.1:8000/`.

---

## 10. Solução de problemas comuns

Sintoma | Possível causa & solução
------- | ------------------------
`ModuleNotFoundError: prudentia.settings` | Verifique se `prudentia/` contém `settings.py` **e** `__init__.py`.
Erro ao instalar `psycopg2` | Falta de `libpq-dev` (Linux) ou Build Tools (Windows).
`TesseractNotFoundError` | `tesseract.exe` não está no PATH ou `TESSERACT_CMD` incorreto no `.env`.
Celery não conecta | Redis não está rodando ou URL incorreta em `CELERY_BROKER_URL`.

---

**Parabéns!** Seu ambiente de desenvolvimento do prudentIA está pronto. Bons códigos e bom planejamento!  
