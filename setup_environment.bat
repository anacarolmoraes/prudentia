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

REM Criar diretório para o projeto se não existir
if not exist prudentia (
    echo [INFO] Criando diretorio 'prudentia' para o projeto...
    mkdir prudentia
    echo [SUCESSO] Diretorio 'prudentia' criado com sucesso!
)

REM Criar diretório para logs, media e static se não existirem
echo [INFO] Criando diretorios para logs, media e arquivos estaticos...
if not exist logs mkdir logs
if not exist media mkdir media
if not exist static mkdir static
echo [SUCESSO] Diretorios criados com sucesso!

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
        echo # Processamento assincrono
        echo celery==5.3.6
        echo redis==5.0.1
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
    (
        echo # Django
        echo DEBUG=True
        echo SECRET_KEY=django-insecure-change-this-in-production-environment
        echo ALLOWED_HOSTS=localhost,127.0.0.1
        echo DJANGO_SETTINGS_MODULE=prudentia.settings
        echo.
        echo # Database
        echo DB_ENGINE=django.db.backends.sqlite3
        echo DB_NAME=db.sqlite3
        echo.
        echo # Redis (opcional, comente se nao estiver usando)
        echo REDIS_URL=redis://localhost:6379/0
        echo CACHE_URL=redis://localhost:6379/1
        echo.
        echo # Celery (opcional, comente se nao estiver usando)
        echo CELERY_BROKER_URL=redis://localhost:6379/0
        echo CELERY_RESULT_BACKEND=redis://localhost:6379/0
        echo.
        echo # Diretorios
        echo MEDIA_ROOT=media/
        echo STATIC_ROOT=static/
        echo LOG_DIR=logs/
    ) > .env
    echo [SUCESSO] Arquivo .env basico criado!
    echo [INFO] Por favor, edite o arquivo .env com suas configuracoes.
)

REM Verificar se o diretório prudentia está configurado corretamente
if not exist prudentia (
    echo [ERRO] O diretorio 'prudentia' nao foi encontrado ou esta vazio.
    echo [INFO] Certifique-se de que a estrutura do projeto esta correta.
) else (
    REM Verificar se __init__.py existe no diretório prudentia
    if not exist prudentia\__init__.py (
        echo [INFO] Criando arquivo __init__.py no diretorio prudentia...
        type nul > prudentia\__init__.py
        echo [SUCESSO] Arquivo __init__.py criado com sucesso!
    )
    
    REM Verificar se os arquivos principais do Django estão no diretório correto
    if exist settings.py (
        if not exist prudentia\settings.py (
            echo [INFO] Movendo settings.py para o diretorio prudentia...
            move settings.py prudentia\
            echo [SUCESSO] settings.py movido com sucesso!
        )
    )
    
    if exist urls.py (
        if not exist prudentia\urls.py (
            echo [INFO] Movendo urls.py para o diretorio prudentia...
            move urls.py prudentia\
            echo [SUCESSO] urls.py movido com sucesso!
        )
    )
    
    if exist wsgi.py (
        if not exist prudentia\wsgi.py (
            echo [INFO] Movendo wsgi.py para o diretorio prudentia...
            move wsgi.py prudentia\
            echo [SUCESSO] wsgi.py movido com sucesso!
        )
    )
    
    if exist asgi.py (
        if not exist prudentia\asgi.py (
            echo [INFO] Movendo asgi.py para o diretorio prudentia...
            move asgi.py prudentia\
            echo [SUCESSO] asgi.py movido com sucesso!
        )
    )
    
    if exist celery.py (
        if not exist prudentia\celery.py (
            echo [INFO] Movendo celery.py para o diretorio prudentia...
            move celery.py prudentia\
            echo [SUCESSO] celery.py movido com sucesso!
        )
    )
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
