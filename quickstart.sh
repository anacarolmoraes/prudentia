#!/bin/bash
# quickstart.sh - Script para inicialização rápida do projeto prudentIA
# Uso: ./quickstart.sh [--no-superuser] [--no-server]

# Cores para melhor visualização
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para exibir mensagens de erro e sair
error_exit() {
    echo -e "${RED}ERRO: $1${NC}" >&2
    exit 1
}

# Função para exibir mensagens de sucesso
success_msg() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Função para exibir mensagens informativas
info_msg() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Função para exibir mensagens de alerta
warning_msg() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Processar argumentos
CREATE_SUPERUSER=true
START_SERVER=true

for arg in "$@"; do
    case $arg in
        --no-superuser)
            CREATE_SUPERUSER=false
            shift
            ;;
        --no-server)
            START_SERVER=false
            shift
            ;;
        --help)
            echo "Uso: ./quickstart.sh [opções]"
            echo "Opções:"
            echo "  --no-superuser    Não solicita criação de superusuário"
            echo "  --no-server       Não inicia o servidor de desenvolvimento"
            echo "  --help            Exibe esta mensagem de ajuda"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}   prudentIA - Inicialização Rápida    ${NC}"
echo -e "${BLUE}=======================================${NC}"

# Verificar se o diretório prudentia existe
if [ ! -d "prudentia" ]; then
    warning_msg "Diretório 'prudentia/' não encontrado. Verificando arquivos de configuração..."
    
    # Verificar se arquivos de configuração estão na raiz
    if [ -f "settings.py" ] && [ -f "urls.py" ] && [ -f "wsgi.py" ]; then
        warning_msg "Arquivos de configuração encontrados na raiz do projeto."
        info_msg "Criando diretório prudentia/ e movendo arquivos..."
        
        # Criar diretório prudentia e mover arquivos
        mkdir -p prudentia
        touch prudentia/__init__.py
        cp settings.py prudentia/
        cp urls.py prudentia/
        cp wsgi.py prudentia/
        [ -f "asgi.py" ] && cp asgi.py prudentia/
        [ -f "celery.py" ] && cp celery.py prudentia/
        
        success_msg "Arquivos movidos para prudentia/. Estrutura corrigida!"
    else
        error_exit "Estrutura de arquivos incorreta. Verifique se você está no diretório raiz do projeto."
    fi
fi

# Verificar se o ambiente virtual existe
if [ ! -d "venv" ]; then
    info_msg "Ambiente virtual não encontrado. Criando..."
    python3 -m venv venv || error_exit "Falha ao criar ambiente virtual. Verifique se python3-venv está instalado."
    success_msg "Ambiente virtual criado com sucesso!"
fi

# Ativar o ambiente virtual
info_msg "Ativando ambiente virtual..."
source venv/bin/activate || error_exit "Falha ao ativar o ambiente virtual."
success_msg "Ambiente virtual ativado!"

# Verificar se o requirements.txt existe e instalar dependências
if [ -f "requirements.txt" ]; then
    info_msg "Verificando dependências..."
    
    # Verificar se o Django está instalado
    if ! python -c "import django" &> /dev/null; then
        warning_msg "Django não encontrado. Instalando dependências..."
        pip install -r requirements.txt || error_exit "Falha ao instalar dependências."
        success_msg "Dependências instaladas com sucesso!"
    else
        success_msg "Dependências já instaladas!"
    fi
else
    error_exit "Arquivo requirements.txt não encontrado. Verifique se você está no diretório raiz do projeto."
fi

# Verificar se o arquivo .env existe
if [ ! -f ".env" ]; then
    warning_msg "Arquivo .env não encontrado."
    if [ -f "env.example" ]; then
        info_msg "Copiando env.example para .env..."
        cp env.example .env
        success_msg "Arquivo .env criado! Por favor, edite-o com suas configurações."
    else
        warning_msg "Arquivo env.example não encontrado. Criando .env básico..."
        cat > .env << EOL
# Django Core Settings
DEBUG=True
SECRET_KEY=django-insecure-$(openssl rand -base64 32)
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=prudentia.settings

# Database Configuration (SQLite for quick development)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Directories
MEDIA_ROOT=media/
STATIC_ROOT=static/
LOG_DIR=logs/
EOL
        success_msg "Arquivo .env básico criado! Edite-o conforme necessário."
    fi
fi

# Criar diretórios necessários
info_msg "Criando diretórios necessários..."
mkdir -p logs media static
for app_dir in apps/*/; do
    if [ -d "$app_dir" ]; then
        mkdir -p "${app_dir}migrations"
        touch "${app_dir}migrations/__init__.py"
    fi
done
success_msg "Diretórios criados!"

# Aplicar migrações
info_msg "Aplicando migrações do banco de dados..."
python manage.py migrate || error_exit "Falha ao aplicar migrações."
success_msg "Migrações aplicadas com sucesso!"

# Criar superusuário se solicitado
if [ "$CREATE_SUPERUSER" = true ]; then
    # Verificar se já existe um superusuário
    SUPERUSER_EXISTS=$(python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
print(User.objects.filter(is_superuser=True).exists())
" 2>/dev/null)

    if [ "$SUPERUSER_EXISTS" = "True" ]; then
        info_msg "Superusuário já existe. Pulando criação."
    else
        info_msg "Criando superusuário..."
        python manage.py createsuperuser
        if [ $? -eq 0 ]; then
            success_msg "Superusuário criado com sucesso!"
        else
            warning_msg "Criação de superusuário cancelada ou falhou."
        fi
    fi
fi

# Coletar arquivos estáticos
info_msg "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput || warning_msg "Falha ao coletar arquivos estáticos. Continuando..."

# Iniciar servidor de desenvolvimento
if [ "$START_SERVER" = true ]; then
    success_msg "Tudo pronto! Iniciando servidor de desenvolvimento..."
    echo -e "${BLUE}=======================================${NC}"
    echo -e "${GREEN}O servidor estará disponível em: http://127.0.0.1:8000/${NC}"
    echo -e "${YELLOW}Pressione CTRL+C para encerrar o servidor.${NC}"
    echo -e "${BLUE}=======================================${NC}"
    python manage.py runserver
else
    success_msg "Configuração concluída! Para iniciar o servidor, execute:"
    echo -e "${BLUE}python manage.py runserver${NC}"
    
    info_msg "Para iniciar workers Celery (opcional):"
    echo -e "${BLUE}celery -A prudentia worker -l info${NC}"
    echo -e "${BLUE}celery -A prudentia beat -l info${NC}"
fi
