@echo off
REM reorganize_repo.bat - Script para reorganizar a estrutura do repositório prudentIA
REM Este script reorganiza os arquivos do repositório, movendo os arquivos de configuração
REM do Django para o diretório prudentia/ e configurando a estrutura correta.

echo ========== REORGANIZACAO DO REPOSITORIO PRUDENTIA ==========
echo.
echo Este script reorganiza a estrutura do repositorio para o padrao Django.
echo.

REM Verificar se estamos em um repositório git
echo [PASSO 1] Verificando repositorio git...
git rev-parse --is-inside-work-tree > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Este diretorio nao e um repositorio git.
    echo        Execute este script na raiz do repositorio prudentIA.
    exit /b 1
)
echo [OK] Repositorio git encontrado.
echo.

REM Criar diretório prudentia/ se não existir
echo [PASSO 2] Verificando/criando diretorio prudentia/...
if exist prudentia (
    if exist prudentia\NUL (
        echo [OK] Diretorio prudentia/ ja existe.
    ) else (
        echo [ERRO] prudentia existe, mas nao e um diretorio!
        exit /b 1
    )
) else (
    mkdir prudentia
    if %errorlevel% equ 0 (
        echo [OK] Diretorio prudentia/ criado com sucesso.
    ) else (
        echo [ERRO] Erro ao criar diretorio prudentia/.
        exit /b 1
    )
)
echo.

REM Criar arquivo __init__.py no diretório prudentia/
echo [PASSO 3] Criando arquivo __init__.py...
if exist prudentia\__init__.py (
    echo [OK] Arquivo __init__.py ja existe.
) else (
    echo # Este arquivo torna o diretorio prudentia/ um pacote Python > prudentia\__init__.py
    echo # Import Celery app >> prudentia\__init__.py
    echo try: >> prudentia\__init__.py
    echo     from .celery import app as celery_app >> prudentia\__init__.py
    echo     __all__ = ["celery_app"] >> prudentia\__init__.py
    echo except ImportError: >> prudentia\__init__.py
    echo     # Celery nao configurado ainda >> prudentia\__init__.py
    echo     pass >> prudentia\__init__.py
    
    if %errorlevel% equ 0 (
        echo [OK] Arquivo __init__.py criado com sucesso.
    ) else (
        echo [ERRO] Erro ao criar arquivo __init__.py.
        exit /b 1
    )
)
echo.

REM Mover os arquivos de configuração do Django para prudentia/
echo [PASSO 4] Movendo arquivos de configuracao do Django...

set files_moved=0

REM Verificar e mover settings.py
if exist settings.py (
    if exist prudentia\settings.py (
        echo       Arquivo settings.py ja existe em prudentia/
    ) else (
        move settings.py prudentia\ > nul
        if %errorlevel% equ 0 (
            echo [OK] Arquivo settings.py movido com sucesso.
            set /a files_moved+=1
        ) else (
            echo [ERRO] Erro ao mover arquivo settings.py.
        )
    )
) else (
    echo       Arquivo settings.py nao encontrado na raiz.
)

REM Verificar e mover urls.py
if exist urls.py (
    if exist prudentia\urls.py (
        echo       Arquivo urls.py ja existe em prudentia/
    ) else (
        move urls.py prudentia\ > nul
        if %errorlevel% equ 0 (
            echo [OK] Arquivo urls.py movido com sucesso.
            set /a files_moved+=1
        ) else (
            echo [ERRO] Erro ao mover arquivo urls.py.
        )
    )
) else (
    echo       Arquivo urls.py nao encontrado na raiz.
)

REM Verificar e mover wsgi.py
if exist wsgi.py (
    if exist prudentia\wsgi.py (
        echo       Arquivo wsgi.py ja existe em prudentia/
    ) else (
        move wsgi.py prudentia\ > nul
        if %errorlevel% equ 0 (
            echo [OK] Arquivo wsgi.py movido com sucesso.
            set /a files_moved+=1
        ) else (
            echo [ERRO] Erro ao mover arquivo wsgi.py.
        )
    )
) else (
    echo       Arquivo wsgi.py nao encontrado na raiz.
)

REM Verificar e mover asgi.py
if exist asgi.py (
    if exist prudentia\asgi.py (
        echo       Arquivo asgi.py ja existe em prudentia/
    ) else (
        move asgi.py prudentia\ > nul
        if %errorlevel% equ 0 (
            echo [OK] Arquivo asgi.py movido com sucesso.
            set /a files_moved+=1
        ) else (
            echo [ERRO] Erro ao mover arquivo asgi.py.
        )
    )
) else (
    echo       Arquivo asgi.py nao encontrado na raiz.
)

REM Verificar e mover celery.py
if exist celery.py (
    if exist prudentia\celery.py (
        echo       Arquivo celery.py ja existe em prudentia/
    ) else (
        move celery.py prudentia\ > nul
        if %errorlevel% equ 0 (
            echo [OK] Arquivo celery.py movido com sucesso.
            set /a files_moved+=1
        ) else (
            echo [ERRO] Erro ao mover arquivo celery.py.
        )
    )
) else (
    echo       Arquivo celery.py nao encontrado na raiz.
)

if %files_moved% equ 0 (
    echo       Nenhum arquivo precisou ser movido.
)
echo.

REM Verificar se manage.py está configurado corretamente
echo [PASSO 5] Verificando arquivo manage.py...
if not exist manage.py (
    echo [ERRO] Arquivo manage.py nao encontrado!
    exit /b 1
)

findstr /C:"os.environ.setdefault" /C:"DJANGO_SETTINGS_MODULE" /C:"prudentia.settings" manage.py > nul
if %errorlevel% equ 0 (
    echo [OK] Arquivo manage.py parece estar configurado corretamente.
) else (
    echo [AVISO] O arquivo manage.py pode precisar ser atualizado.
    echo         Verifique se ele contem: os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings')
)
echo.

REM Criar diretórios para logs, media e static
echo [PASSO 6] Criando diretorios para logs, media e static...

REM Verificar e criar diretório logs
if exist logs (
    if exist logs\NUL (
        echo       Diretorio logs/ ja existe.
    ) else (
        echo [ERRO] logs existe, mas nao e um diretorio!
    )
) else (
    mkdir logs
    if %errorlevel% equ 0 (
        echo [OK] Diretorio logs/ criado com sucesso.
    ) else (
        echo [ERRO] Erro ao criar diretorio logs/.
    )
)

REM Verificar e criar diretório media
if exist media (
    if exist media\NUL (
        echo       Diretorio media/ ja existe.
    ) else (
        echo [ERRO] media existe, mas nao e um diretorio!
    )
) else (
    mkdir media
    if %errorlevel% equ 0 (
        echo [OK] Diretorio media/ criado com sucesso.
    ) else (
        echo [ERRO] Erro ao criar diretorio media/.
    )
)

REM Verificar e criar diretório static
if exist static (
    if exist static\NUL (
        echo       Diretorio static/ ja existe.
    ) else (
        echo [ERRO] static existe, mas nao e um diretorio!
    )
) else (
    mkdir static
    if %errorlevel% equ 0 (
        echo [OK] Diretorio static/ criado com sucesso.
    ) else (
        echo [ERRO] Erro ao criar diretorio static/.
    )
)
echo.

REM Criar diretórios de migrations para os apps Django
echo [PASSO 7] Criando diretorios de migrations para os apps...
if not exist apps (
    echo       Diretorio apps/ nao encontrado. Pulando criacao de migrations.
    goto SkipMigrations
)

REM Listar todos os subdiretórios em apps
set "app_count=0"
for /d %%D in (apps\*) do (
    set /a app_count+=1
    
    REM Criar diretório migrations se não existir
    if not exist "%%D\migrations" (
        mkdir "%%D\migrations"
        if %errorlevel% equ 0 (
            echo [OK] Diretorio migrations/ criado para o app %%~nxD.
        ) else (
            echo [ERRO] Erro ao criar diretorio migrations/ para %%~nxD.
        )
    )
    
    REM Criar arquivo __init__.py se não existir
    if not exist "%%D\migrations\__init__.py" (
        type nul > "%%D\migrations\__init__.py"
        if %errorlevel% equ 0 (
            echo [OK] Arquivo __init__.py criado em migrations/ para o app %%~nxD.
        ) else (
            echo [ERRO] Erro ao criar __init__.py para %%~nxD.
        )
    )
)

if %app_count% equ 0 (
    echo       Nenhum app Django encontrado.
)

:SkipMigrations
echo.

REM Fazer commit das alterações
echo [PASSO 8] Verificando alteracoes para commit...
git status --porcelain > temp_changes.txt
set /p changes=<temp_changes.txt
del temp_changes.txt

if "%changes%"=="" (
    echo       Nao ha alteracoes para commit.
    goto SkipCommit
)

echo As seguintes alteracoes foram detectadas:
git status --short
echo.

set /p response="Deseja fazer commit dessas alteracoes? (s/N): "
if /i not "%response%"=="s" (
    echo       Commit cancelado pelo usuario.
    goto SkipCommit
)

REM Adicionar arquivos
git add prudentia/ settings.py urls.py wsgi.py asgi.py celery.py 2>nul

REM Fazer commit
git commit -m "refactor: reorganize Django files into prudentia/ package"
if %errorlevel% equ 0 (
    echo [OK] Commit realizado com sucesso!
) else (
    echo [ERRO] Erro ao fazer commit.
    exit /b 1
)

:SkipCommit
echo.

echo ========== REORGANIZACAO CONCLUIDA COM SUCESSO ==========
echo.
echo A estrutura do repositorio foi reorganizada para o padrao Django.
echo.
echo Proximos passos:
echo 1. Configure o ambiente virtual e instale as dependencias
echo 2. Configure o arquivo .env
echo 3. Configure o banco de dados
echo 4. Execute as migracoes e crie um superusuario
echo 5. Inicie o servidor de desenvolvimento
echo.
echo Pressione qualquer tecla para sair...
pause > nul
