@echo off
REM quickstart.bat - Script para inicialização rápida do projeto prudentIA no Windows
REM Uso: quickstart.bat [--no-superuser] [--no-server]

setlocal enabledelayedexpansion

REM Cores para melhor visualização (funciona no Windows 10+)
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "BLUE=[34m"
set "NC=[0m"

REM Processar argumentos
set CREATE_SUPERUSER=true
set START_SERVER=true

:parse_args
if "%~1"=="" goto :end_parse_args
if "%~1"=="--no-superuser" (
    set CREATE_SUPERUSER=false
    shift
    goto :parse_args
)
if "%~1"=="--no-server" (
    set START_SERVER=false
    shift
    goto :parse_args
)
if "%~1"=="--help" (
    echo Uso: quickstart.bat [opcoes]
    echo Opcoes:
    echo   --no-superuser    Nao solicita criacao de superusuario
    echo   --no-server       Nao inicia o servidor de desenvolvimento
    echo   --help            Exibe esta mensagem de ajuda
    exit /b 0
)
shift
goto :parse_args
:end_parse_args

echo %BLUE%=======================================%NC%
echo %BLUE%   prudentIA - Inicializacao Rapida    %NC%
echo %BLUE%=======================================%NC%

REM Verificar se o diretório prudentia existe
if not exist prudentia (
    echo %YELLOW%Diretorio 'prudentia/' nao encontrado. Verificando arquivos de configuracao...%NC%
    
    REM Verificar se arquivos de configuração estão na raiz
    if exist settings.py if exist urls.py if exist wsgi.py (
        echo %YELLOW%Arquivos de configuracao encontrados na raiz do projeto.%NC%
        echo %BLUE%Criando diretorio prudentia/ e movendo arquivos...%NC%
        
        REM Criar diretório prudentia e mover arquivos
        mkdir prudentia
        type nul > prudentia\__init__.py
        copy settings.py prudentia\
        copy urls.py prudentia\
        copy wsgi.py prudentia\
        if exist asgi.py copy asgi.py prudentia\
        if exist celery.py copy celery.py prudentia\
        
        echo %GREEN%Arquivos movidos para prudentia/. Estrutura corrigida!%NC%
    ) else (
        echo %RED%Estrutura de arquivos incorreta. Verifique se voce esta no diretorio raiz do projeto.%NC%
        exit /b 1
    )
)

REM Verificar se o ambiente virtual existe
if not exist venv (
    echo %BLUE%Ambiente virtual nao encontrado. Criando...%NC%
    python -m venv venv
    if errorlevel 1 (
        echo %RED%Falha ao criar ambiente virtual. Verifique se o modulo venv esta instalado.%NC%
        exit /b 1
    )
    echo %GREEN%Ambiente virtual criado com sucesso!%NC%
)

REM Ativar o ambiente virtual
echo %BLUE%Ativando ambiente virtual...%NC%
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo %RED%Falha ao ativar o ambiente virtual.%NC%
    exit /b 1
)
echo %GREEN%Ambiente virtual ativado!%NC%

REM Verificar se o requirements.txt existe e instalar dependências
if exist requirements.txt (
    echo %BLUE%Verificando dependencias...%NC%
    
    REM Verificar se o Django está instalado
    python -c "import django" 2>nul
    if errorlevel 1 (
        echo %YELLOW%Django nao encontrado. Instalando dependencias...%NC%
        pip install -r requirements.txt
        if errorlevel 1 (
            echo %RED%Falha ao instalar dependencias.%NC%
            exit /b 1
        )
        echo %GREEN%Dependencias instaladas com sucesso!%NC%
    ) else (
        echo %GREEN%Dependencias ja instaladas!%NC%
    )
) else (
    echo %RED%Arquivo requirements.txt nao encontrado. Verifique se voce esta no diretorio raiz do projeto.%NC%
    exit /b 1
)

REM Verificar se o arquivo .env existe
if not exist .env (
    echo %YELLOW%Arquivo .env nao encontrado.%NC%
    if exist env.example (
        echo %BLUE%Copiando env.example para .env...%NC%
        copy env.example .env
        echo %GREEN%Arquivo .env criado! Por favor, edite-o com suas configuracoes.%NC%
    ) else (
        echo %YELLOW%Arquivo env.example nao encontrado. Criando .env basico...%NC%
        
        REM Gerar uma chave secreta aleatória
        for /f "tokens=*" %%a in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set SECRET_KEY=%%a
        
        (
            echo # Django Core Settings
            echo DEBUG=True
            echo SECRET_KEY=django-insecure-%SECRET_KEY%
            echo ALLOWED_HOSTS=localhost,127.0.0.1
            echo DJANGO_SETTINGS_MODULE=prudentia.settings
            echo.
            echo # Database Configuration (SQLite for quick development)
            echo DB_ENGINE=django.db.backends.sqlite3
            echo DB_NAME=db.sqlite3
            echo.
            echo # Directories
            echo MEDIA_ROOT=media/
            echo STATIC_ROOT=static/
            echo LOG_DIR=logs/
        ) > .env
        echo %GREEN%Arquivo .env basico criado! Edite-o conforme necessario.%NC%
    )
)

REM Criar diretórios necessários
echo %BLUE%Criando diretorios necessarios...%NC%
if not exist logs mkdir logs
if not exist media mkdir media
if not exist static mkdir static

REM Criar diretórios de migrations para cada app
for /d %%d in (apps\*) do (
    if not exist "%%d\migrations" (
        mkdir "%%d\migrations"
        type nul > "%%d\migrations\__init__.py"
    )
)
echo %GREEN%Diretorios criados!%NC%

REM Aplicar migrações
echo %BLUE%Aplicando migracoes do banco de dados...%NC%
python manage.py migrate
if errorlevel 1 (
    echo %RED%Falha ao aplicar migracoes.%NC%
    exit /b 1
)
echo %GREEN%Migracoes aplicadas com sucesso!%NC%

REM Criar superusuário se solicitado
if "%CREATE_SUPERUSER%"=="true" (
    REM Verificar se já existe um superusuário
    python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings'); django.setup(); from django.contrib.auth import get_user_model; User = get_user_model(); print('True' if User.objects.filter(is_superuser=True).exists() else 'False')" > temp.txt
    set /p SUPERUSER_EXISTS=<temp.txt
    del temp.txt
    
    if "!SUPERUSER_EXISTS!"=="True" (
        echo %BLUE%Superusuario ja existe. Pulando criacao.%NC%
    ) else (
        echo %BLUE%Criando superusuario...%NC%
        python manage.py createsuperuser
        if errorlevel 1 (
            echo %YELLOW%Criacao de superusuario cancelada ou falhou.%NC%
        ) else (
            echo %GREEN%Superusuario criado com sucesso!%NC%
        )
    )
)

REM Coletar arquivos estáticos
echo %BLUE%Coletando arquivos estaticos...%NC%
python manage.py collectstatic --noinput
if errorlevel 1 (
    echo %YELLOW%Falha ao coletar arquivos estaticos. Continuando...%NC%
)

REM Iniciar servidor de desenvolvimento
if "%START_SERVER%"=="true" (
    echo %GREEN%Tudo pronto! Iniciando servidor de desenvolvimento...%NC%
    echo %BLUE%=======================================%NC%
    echo %GREEN%O servidor estara disponivel em: http://127.0.0.1:8000/%NC%
    echo %YELLOW%Pressione CTRL+C para encerrar o servidor.%NC%
    echo %BLUE%=======================================%NC%
    python manage.py runserver
) else (
    echo %GREEN%Configuracao concluida! Para iniciar o servidor, execute:%NC%
    echo %BLUE%python manage.py runserver%NC%
    
    echo %BLUE%Para iniciar workers Celery (opcional):%NC%
    echo %BLUE%celery -A prudentia worker -l info%NC%
    echo %BLUE%celery -A prudentia beat -l info%NC%
)

endlocal
