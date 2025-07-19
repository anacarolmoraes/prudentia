#!/bin/bash
# setup_environment.sh - Script para configurar o ambiente de desenvolvimento do prudentIA

# Cores para melhor visualização
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Configurando ambiente para o projeto prudentIA ===${NC}"

# Detectar o sistema operacional
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
else
    OS="Windows/Outro"
fi

echo -e "${YELLOW}Sistema operacional detectado: $OS${NC}"

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 não encontrado. Por favor, instale o Python 3.10 ou superior.${NC}"
    exit 1
fi

# Verificar versão do Python
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${YELLOW}Versão do Python: $PYTHON_VERSION${NC}"

# Verificar se a versão do Python é adequada
if [[ $(echo "$PYTHON_VERSION < 3.10" | bc) -eq 1 ]]; then
    echo -e "${RED}Este projeto requer Python 3.10 ou superior.${NC}"
    echo -e "${RED}Por favor, atualize sua versão do Python.${NC}"
    exit 1
fi

# Criar diretório para o projeto se não existir
if [ ! -d "prudentia" ]; then
    echo -e "${YELLOW}Criando diretório 'prudentia' para o projeto...${NC}"
    mkdir -p prudentia
    echo -e "${GREEN}Diretório 'prudentia' criado com sucesso!${NC}"
fi

# Criar diretório para logs, media e static se não existirem
echo -e "${YELLOW}Criando diretórios para logs, media e arquivos estáticos...${NC}"
mkdir -p logs media static
echo -e "${GREEN}Diretórios criados com sucesso!${NC}"

# Criar e ativar ambiente virtual
echo -e "${YELLOW}Criando ambiente virtual Python...${NC}"
python3 -m venv venv
echo -e "${GREEN}Ambiente virtual criado com sucesso!${NC}"

echo -e "${YELLOW}Ativando ambiente virtual...${NC}"
source venv/bin/activate

# Verificar se o ambiente virtual foi ativado
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${RED}Falha ao ativar o ambiente virtual.${NC}"
    echo -e "${YELLOW}Por favor, ative manualmente com:${NC}"
    echo -e "source venv/bin/activate  # Linux/macOS"
    echo -e "venv\\Scripts\\activate    # Windows"
    exit 1
fi

echo -e "${GREEN}Ambiente virtual ativado com sucesso!${NC}"

# Atualizar pip
echo -e "${YELLOW}Atualizando pip para a versão mais recente...${NC}"
pip install --upgrade pip

# Instalar dependências do requirements.txt
echo -e "${YELLOW}Instalando dependências Python do projeto...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}Dependências instaladas com sucesso!${NC}"
else
    echo -e "${RED}Arquivo requirements.txt não encontrado.${NC}"
    echo -e "${YELLOW}Criando um arquivo requirements.txt básico...${NC}"
    
    # Criar um requirements.txt básico se não existir
    cat > requirements.txt << EOL
# Django e componentes principais
Django==4.2.10
djangorestframework==3.14.0
django-cors-headers==4.3.1
django-filter==23.5
django-allauth==0.61.0
django-environ==0.11.2
django-celery-beat==2.5.0
django-celery-results==2.5.1
django-redis==5.4.0

# Banco de dados
psycopg2-binary==2.9.9
dj-database-url==2.1.0

# Processamento assíncrono
celery==5.3.6
redis==5.0.1

# Web scraping e HTTP
httpx==0.26.0
selectolax==0.3.17
beautifulsoup4==4.12.3
requests==2.31.0

# Processamento de documentos e OCR
pytesseract==0.3.10
Pillow==10.2.0
opencv-python==4.9.0.80
PyPDF2==3.0.1

# Integração com Google Drive
google-api-python-client==2.114.0
google-auth==2.27.0
google-auth-oauthlib==1.2.0

# Servidor web para produção
gunicorn==21.2.0

# Ferramentas de desenvolvimento
python-dotenv==1.0.0
EOL
    
    pip install -r requirements.txt
    echo -e "${GREEN}Arquivo requirements.txt criado e dependências básicas instaladas!${NC}"
fi

# Configurar arquivo .env
echo -e "${YELLOW}Configurando variáveis de ambiente...${NC}"
if [ -f "env.example" ]; then
    if [ ! -f ".env" ]; then
        cp env.example .env
        echo -e "${GREEN}Arquivo .env criado com base no env.example!${NC}"
        echo -e "${YELLOW}Por favor, edite o arquivo .env com suas configurações.${NC}"
    else
        echo -e "${YELLOW}Arquivo .env já existe. Não foi sobrescrito.${NC}"
    fi
else
    echo -e "${YELLOW}Arquivo env.example não encontrado. Criando um arquivo .env básico...${NC}"
    cat > .env << EOL
# Django
DEBUG=True
SECRET_KEY=django-insecure-change-this-in-production-environment
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=prudentia.settings

# Database
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Redis (opcional, comente se não estiver usando)
REDIS_URL=redis://localhost:6379/0
CACHE_URL=redis://localhost:6379/1

# Celery (opcional, comente se não estiver usando)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Diretórios
MEDIA_ROOT=media/
STATIC_ROOT=static/
LOG_DIR=logs/
EOL
    echo -e "${GREEN}Arquivo .env básico criado!${NC}"
    echo -e "${YELLOW}Por favor, edite o arquivo .env com suas configurações.${NC}"
fi

# Instalar dependências do sistema operacional
echo -e "${YELLOW}Verificando dependências do sistema operacional...${NC}"

if [[ "$OS" == "Linux" ]]; then
    echo -e "${YELLOW}Para instalar dependências do sistema no Linux (Ubuntu/Debian), execute:${NC}"
    echo -e "sudo apt-get update"
    echo -e "sudo apt-get install -y postgresql postgresql-contrib libpq-dev"
    echo -e "sudo apt-get install -y redis-server"
    echo -e "sudo apt-get install -y tesseract-ocr tesseract-ocr-por"
    echo -e "sudo apt-get install -y libjpeg-dev zlib1g-dev libopencv-dev"
    
elif [[ "$OS" == "macOS" ]]; then
    echo -e "${YELLOW}Para instalar dependências do sistema no macOS, execute:${NC}"
    echo -e "brew install postgresql"
    echo -e "brew install redis"
    echo -e "brew install tesseract"
    echo -e "brew install tesseract-lang  # Inclui português"
    
else
    echo -e "${YELLOW}Para Windows, instale manualmente:${NC}"
    echo -e "1. PostgreSQL: https://www.postgresql.org/download/windows/"
    echo -e "2. Redis: https://github.com/microsoftarchive/redis/releases"
    echo -e "3. Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki"
fi

# Verificar instalação
echo -e "${YELLOW}Verificando instalação de pacotes Python...${NC}"
python -c "import django; print(f'Django {django.__version__} instalado com sucesso!')" || echo -e "${RED}Django não está instalado corretamente.${NC}"
python -c "import rest_framework; print('Django REST Framework instalado com sucesso!')" || echo -e "${RED}Django REST Framework não está instalado corretamente.${NC}"
python -c "import celery; print(f'Celery {celery.__version__} instalado com sucesso!')" || echo -e "${YELLOW}Celery não está instalado ou não pode ser importado.${NC}"
python -c "import PIL; print(f'Pillow {PIL.__version__} instalado com sucesso!')" || echo -e "${YELLOW}Pillow não está instalado ou não pode ser importado.${NC}"

# Verificar se o diretório prudentia está configurado corretamente
if [ ! -d "prudentia" ]; then
    echo -e "${RED}O diretório 'prudentia' não foi encontrado ou está vazio.${NC}"
    echo -e "${YELLOW}Certifique-se de que a estrutura do projeto está correta.${NC}"
else
    # Verificar se __init__.py existe no diretório prudentia
    if [ ! -f "prudentia/__init__.py" ]; then
        echo -e "${YELLOW}Criando arquivo __init__.py no diretório prudentia...${NC}"
        touch prudentia/__init__.py
        echo -e "${GREEN}Arquivo __init__.py criado com sucesso!${NC}"
    fi
    
    # Verificar se os arquivos principais do Django estão no diretório correto
    if [ -f "settings.py" ] && [ ! -f "prudentia/settings.py" ]; then
        echo -e "${YELLOW}Movendo settings.py para o diretório prudentia...${NC}"
        mv settings.py prudentia/
        echo -e "${GREEN}settings.py movido com sucesso!${NC}"
    fi
    
    if [ -f "urls.py" ] && [ ! -f "prudentia/urls.py" ]; then
        echo -e "${YELLOW}Movendo urls.py para o diretório prudentia...${NC}"
        mv urls.py prudentia/
        echo -e "${GREEN}urls.py movido com sucesso!${NC}"
    fi
    
    if [ -f "wsgi.py" ] && [ ! -f "prudentia/wsgi.py" ]; then
        echo -e "${YELLOW}Movendo wsgi.py para o diretório prudentia...${NC}"
        mv wsgi.py prudentia/
        echo -e "${GREEN}wsgi.py movido com sucesso!${NC}"
    fi
    
    if [ -f "asgi.py" ] && [ ! -f "prudentia/asgi.py" ]; then
        echo -e "${YELLOW}Movendo asgi.py para o diretório prudentia...${NC}"
        mv asgi.py prudentia/
        echo -e "${GREEN}asgi.py movido com sucesso!${NC}"
    fi
    
    if [ -f "celery.py" ] && [ ! -f "prudentia/celery.py" ]; then
        echo -e "${YELLOW}Movendo celery.py para o diretório prudentia...${NC}"
        mv celery.py prudentia/
        echo -e "${GREEN}celery.py movido com sucesso!${NC}"
    fi
fi

echo -e "${GREEN}=== Configuração do ambiente concluída! ===${NC}"
echo -e "${YELLOW}Próximos passos:${NC}"
echo -e "1. Edite o arquivo .env com suas configurações específicas"
echo -e "2. Configure o banco de dados (PostgreSQL recomendado para produção)"
echo -e "3. Execute as migrações: python manage.py migrate"
echo -e "4. Crie um superusuário: python manage.py createsuperuser"
echo -e "5. Inicie o servidor de desenvolvimento: python manage.py runserver"
echo -e "6. (Opcional) Inicie o Celery worker: celery -A prudentia worker -l info"
echo -e "7. (Opcional) Inicie o Celery beat: celery -A prudentia beat -l info"

echo -e "${BLUE}Para ativar o ambiente virtual em sessões futuras:${NC}"
echo -e "source venv/bin/activate  # Linux/macOS"
echo -e "venv\\Scripts\\activate    # Windows"

echo -e "${GREEN}Boa codificação!${NC}"
