@echo off
REM setup_environment.bat - Script para configurar o ambiente de desenvolvimento do prudentIA no Windows

echo === Configurando ambiente para o projeto prudentIA ===
echo.

REM Verificar se Python está instalado
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Por favor, instale o Python 3.10 ou superior.
    exit /b 1
)

REM Verificar versão do Python
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [INFO] Versao do Python: %PYTHON_VERSION%

REM Verificar estrutura do projeto
if not exist prudentia (
    echo [AVISO] Diretorio 'prudentia/' nao encontrado. Verificando arquivos de configuracao...
    
    REM Verificar se arquivos de configuração estão na raiz
    if exist settings.py if exist urls.py if exist wsgi.py (
        echo [AVISO] Arquivos de configuracao encontrados na raiz do projeto.
        echo [INFO] Criando diretorio prudentia/ e movendo arquivos...
        
        REM Criar diretório prudentia e mover arquivos
        mkdir prudentia
        type nul > prudentia\__init__.py
        copy settings.py prudentia\
        copy urls.py prudentia\
        copy wsgi.py prudentia\
        if exist asgi.py copy asgi.py prudentia\
        if exist celery.py copy celery.py prudentia\
        
        REM Adicionar código de inicialização do Celery ao __init__.py
        echo """                                                                > prudentia\__init__.py
        echo Inicializacao do pacote prudentia.                               >> prudentia\__init__.py
        echo Este arquivo importa a aplicacao Celery para garantir que ela seja carregada >> prudentia\__init__.py
        echo quando o Django iniciar.                                         >> prudentia\__init__.py
        echo """                                                              >> prudentia\__init__.py
        echo.                                                                 >> prudentia\__init__.py
        echo # Importar a aplicacao Celery                                    >> prudentia\__init__.py
        echo from .celery import app as celery_app                            >> prudentia\__init__.py
        echo.                                                                 >> prudentia\__init__.py
        echo # Definir quais simbolos serao exportados quando alguem fizer "from prudentia import *" >> prudentia\__init__.py
        echo __all__ = ['celery_app']                                         >> prudentia\__init__.py
        
        echo [SUCESSO] Arquivos movidos para prudentia/. Estrutura corrigida!
    ) else (
        echo [AVISO] Nao foram encontrados arquivos de configuracao na raiz.
        echo [INFO] Criando estrutura basica do diretorio prudentia/...
        
        REM Criar diretório prudentia com arquivos básicos
        mkdir prudentia
        type nul > prudentia\__init__.py
        
        echo [SUCESSO] Diretorio prudentia/ criado com sucesso!
    )
)

REM Criar diretórios necessários
echo [INFO] Criando diretorios para logs, media e arquivos estaticos...
if not exist logs mkdir logs
if not exist media mkdir media
if not exist static mkdir static
echo [SUCESSO] Diretorios criados com sucesso!

REM Criar diretórios para migrations de cada app
echo [INFO] Verificando e criando diretorios de migrations para cada app...
for /d %%d in (apps\*) do (
    if exist "%%d" (
        if not exist "%%d\migrations" (
            mkdir "%%d\migrations"
            type nul > "%%d\migrations\__init__.py"
            echo [INFO] Criado diretorio de migrations para: %%d
        )
    )
)
echo [SUCESSO] Diretorios de migrations configurados!

REM Criar ambiente virtual
echo [INFO] Criando ambiente virtual Python...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao criar o ambiente virtual.
    exit /b 1
)
echo [SUCESSO] Ambiente virtual criado com sucesso!

REM Ativar ambiente virtual
echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao ativar o ambiente virtual.
    echo [INFO] Por favor, ative manualmente com: venv\Scripts\activate.bat
    exit /b 1
)
echo [SUCESSO] Ambiente virtual ativado com sucesso!

REM Atualizar pip
echo [INFO] Atualizando pip para a versao mais recente...
python -m pip install --upgrade pip

REM Instalar dependências do requirements.txt
echo [INFO] Instalando dependencias Python do projeto...
if exist requirements.txt (
    pip install -r requirements.txt
    echo [SUCESSO] Dependencias instaladas com sucesso!
) else (
    echo [AVISO] Arquivo requirements.txt nao encontrado.
    echo [INFO] Criando um arquivo requirements.txt basico...
    
    REM Criar um requirements.txt básico se não existir
    (
        echo # Django e componentes principais
        echo Django==4.2.10
        echo djangorestframework==3.14.0
        echo djangorestframework-simplejwt==5.2.2
        echo django-cors-headers==4.3.1
        echo django-filter==23.5
        echo django-allauth==0.61.0
        echo django-environ==0.11.2
        echo django-celery-beat==2.5.0
        echo django-celery-results==2.5.1
        echo django-redis==5.4.0
        echo.
        echo # Banco de dados
        echo psycopg2-binary==2.9.9
        echo dj-database-url==2.1.0
        echo.
        echo # Autenticacao e seguranca
        echo PyJWT==2.8.0
        echo cryptography==41.0.7
        echo python-jose[cryptography]==3.3.0
        echo.
        echo # Processamento assincrono
        echo celery==5.3.6
        echo redis==5.0.1
        echo flower==2.0.1
        echo.
        echo # Web scraping e HTTP
        echo httpx==0.26.0
        echo selectolax==0.3.17
        echo beautifulsoup4==4.12.3
        echo requests==2.31.0
        echo.
        echo # Processamento de documentos e OCR
        echo pytesseract==0.3.10
        echo Pillow==10.2.0
        echo opencv-python==4.9.0.80
        echo PyPDF2==3.0.1
        echo pdfplumber==0.10.3
        echo docxtpl==0.16.7
        echo.
        echo # Integracao com Google Drive
        echo google-api-python-client==2.114.0
        echo google-auth==2.27.0
        echo google-auth-oauthlib==1.2.0
        echo.
        echo # Servidor web para producao
        echo gunicorn==21.2.0
        echo.
        echo # Ferramentas de desenvolvimento
        echo python-dotenv==1.0.0
    ) > requirements.txt
    
    pip install -r requirements.txt
    echo [SUCESSO] Arquivo requirements.txt criado e dependencias basicas instaladas!
)

REM Configurar arquivo .env
echo [INFO] Configurando variaveis de ambiente...
if exist env.example (
    if not exist .env (
        copy env.example .env
        echo [SUCESSO] Arquivo .env criado com base no env.example!
        echo [INFO] Por favor, edite o arquivo .env com suas configuracoes.
    ) else (
        echo [AVISO] Arquivo .env ja existe. Nao foi sobrescrito.
    )
) else (
    echo [AVISO] Arquivo env.example nao encontrado. Criando um arquivo .env basico...
    
    REM Gerar uma chave secreta aleatória
    for /f "tokens=*" %%a in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set SECRET_KEY=%%a
    
    (
        echo # Django Core Settings
        echo DEBUG=True
        echo SECRET_KEY=django-insecure-%SECRET_KEY%
        echo ALLOWED_HOSTS=localhost,127.0.0.1
        echo DJANGO_SETTINGS_MODULE=prudentia.settings
        echo.
        echo # Database Configuration
        echo # SQLite (for quick development)
        echo DB_ENGINE=django.db.backends.sqlite3
        echo DB_NAME=db.sqlite3
        echo.
        echo # PostgreSQL (recommended for production - uncomment and configure)
        echo # DB_ENGINE=django.db.backends.postgresql
        echo # DB_NAME=prudentia_db
        echo # DB_USER=postgres
        echo # DB_PASSWORD=postgres
        echo # DB_HOST=localhost
        echo # DB_PORT=5432
        echo.
        echo # Redis Configuration
        echo REDIS_URL=redis://localhost:6379/0
        echo CACHE_URL=redis://localhost:6379/1
        echo.
        echo # Celery Configuration
        echo CELERY_BROKER_URL=redis://localhost:6379/0
        echo CELERY_RESULT_BACKEND=redis://localhost:6379/0
        echo CELERY_TIMEZONE=America/Sao_Paulo
        echo.
        echo # Email Configuration
        echo EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
        echo EMAIL_HOST=smtp.gmail.com
        echo EMAIL_PORT=587
        echo EMAIL_USE_TLS=True
        echo EMAIL_HOST_USER=seu-email@gmail.com
        echo EMAIL_HOST_PASSWORD=sua-senha-de-app
        echo.
        echo # Storage Paths
        echo MEDIA_ROOT=media/
        echo STATIC_ROOT=static/
        echo LOG_DIR=logs/
    ) > .env
    echo [SUCESSO] Arquivo .env basico criado!
    echo [INFO] Por favor, edite o arquivo .env com suas configuracoes.
)

REM Instalar dependências do sistema operacional
echo [INFO] Dependencias do sistema operacional para Windows:
echo 1. PostgreSQL: https://www.postgresql.org/download/windows/
echo 2. Redis: https://github.com/microsoftarchive/redis/releases
echo 3. Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
echo.
echo [INFO] Certifique-se de instalar essas dependencias manualmente.

REM Verificar instalação
echo [INFO] Verificando instalacao de pacotes Python...
python -c "import django; print(f'Django {django.__version__} instalado com sucesso!')" 2>nul || echo [AVISO] Django nao esta instalado corretamente.
python -c "import rest_framework; print('Django REST Framework instalado com sucesso!')" 2>nul || echo [AVISO] Django REST Framework nao esta instalado corretamente.
python -c "import celery; print(f'Celery {celery.__version__} instalado com sucesso!')" 2>nul || echo [AVISO] Celery nao esta instalado ou nao pode ser importado.
python -c "import PIL; print(f'Pillow {PIL.__version__} instalado com sucesso!')" 2>nul || echo [AVISO] Pillow nao esta instalado ou nao pode ser importado.

echo.
echo === Configuracao do ambiente concluida! ===
echo [INFO] Proximos passos:
echo 1. Edite o arquivo .env com suas configuracoes especificas
echo 2. Configure o banco de dados (PostgreSQL recomendado para producao)
echo 3. Execute as migracoes: python manage.py migrate
echo 4. Crie um superusuario: python manage.py createsuperuser
echo 5. Inicie o servidor de desenvolvimento: python manage.py runserver
echo 6. (Opcional) Inicie o Celery worker: celery -A prudentia worker -l info
echo 7. (Opcional) Inicie o Celery beat: celery -A prudentia beat -l info
echo.
echo [INFO] Para ativar o ambiente virtual em sessoes futuras:
echo venv\Scripts\activate.bat
echo.
echo Boa codificacao!
pause
