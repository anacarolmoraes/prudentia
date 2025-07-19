#!/bin/bash
# reorganize_repo.sh - Script para reorganizar a estrutura do repositório prudentIA
# Este script reorganiza os arquivos do repositório, movendo os arquivos de configuração
# do Django para o diretório prudentia/ e configurando a estrutura correta.

# Cores para terminal
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Funções para formatação de mensagens
print_header() {
    echo -e "\n${BLUE}${BOLD}========== $1 ==========${NC}"
}

print_step() {
    echo -e "\n${YELLOW}➤ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "  $1"
}

# Verificar se estamos em um repositório git
check_git_repo() {
    print_step "Verificando repositório git..."
    
    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        print_success "Repositório git encontrado."
        return 0
    else
        print_error "Este diretório não é um repositório git."
        print_info "Execute este script na raiz do repositório prudentIA."
        return 1
    fi
}

# Criar diretório prudentia/ se não existir
create_prudentia_dir() {
    print_step "Verificando/criando diretório prudentia/..."
    
    if [ -e "prudentia" ]; then
        if [ -d "prudentia" ]; then
            print_success "Diretório prudentia/ já existe."
        else
            print_error "prudentia existe, mas não é um diretório!"
            return 1
        fi
    else
        mkdir -p prudentia
        if [ $? -eq 0 ]; then
            print_success "Diretório prudentia/ criado com sucesso."
        else
            print_error "Erro ao criar diretório prudentia/."
            return 1
        fi
    fi
    
    return 0
}

# Criar arquivo __init__.py no diretório prudentia/
create_init_file() {
    print_step "Criando arquivo __init__.py..."
    
    if [ -f "prudentia/__init__.py" ]; then
        print_success "Arquivo __init__.py já existe."
    else
        cat > prudentia/__init__.py << EOL
# Este arquivo torna o diretório prudentia/ um pacote Python
# Import Celery app
try:
    from .celery import app as celery_app
    __all__ = ["celery_app"]
except ImportError:
    # Celery não configurado ainda
    pass
EOL
        if [ $? -eq 0 ]; then
            print_success "Arquivo __init__.py criado com sucesso."
        else
            print_error "Erro ao criar arquivo __init__.py."
            return 1
        fi
    fi
    
    return 0
}

# Mover os arquivos de configuração do Django para prudentia/
move_django_files() {
    print_step "Movendo arquivos de configuração do Django..."
    
    files_moved=0
    
    for file in settings.py urls.py wsgi.py asgi.py celery.py; do
        if [ -f "$file" ]; then
            if [ -f "prudentia/$file" ]; then
                print_info "Arquivo $file já existe em prudentia/"
            else
                mv "$file" "prudentia/"
                if [ $? -eq 0 ]; then
                    print_success "Arquivo $file movido com sucesso."
                    files_moved=$((files_moved + 1))
                else
                    print_error "Erro ao mover arquivo $file."
                fi
            fi
        else
            print_info "Arquivo $file não encontrado na raiz."
        fi
    done
    
    if [ $files_moved -eq 0 ]; then
        print_info "Nenhum arquivo precisou ser movido."
    fi
    
    return 0
}

# Verificar se manage.py está configurado corretamente
check_manage_py() {
    print_step "Verificando arquivo manage.py..."
    
    if [ ! -f "manage.py" ]; then
        print_error "Arquivo manage.py não encontrado!"
        return 1
    fi
    
    if grep -q "os.environ.setdefault.*DJANGO_SETTINGS_MODULE.*prudentia.settings" manage.py; then
        print_success "Arquivo manage.py já está configurado corretamente."
    else
        print_info "O arquivo manage.py pode precisar ser atualizado."
        print_info "Verifique se ele contém: os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings')"
    fi
    
    return 0
}

# Criar diretórios para logs, media e static
create_dirs() {
    print_step "Criando diretórios para logs, media e static..."
    
    for dir in logs media static; do
        if [ -e "$dir" ]; then
            if [ -d "$dir" ]; then
                print_info "Diretório $dir/ já existe."
            else
                print_error "$dir existe, mas não é um diretório!"
            fi
        else
            mkdir -p "$dir"
            if [ $? -eq 0 ]; then
                print_success "Diretório $dir/ criado com sucesso."
            else
                print_error "Erro ao criar diretório $dir/."
            fi
        fi
    done
    
    return 0
}

# Criar diretórios de migrations para os apps Django
create_migrations_dirs() {
    print_step "Criando diretórios de migrations para os apps..."
    
    if [ ! -d "apps" ]; then
        print_info "Diretório apps/ não encontrado. Pulando criação de migrations."
        return 0
    fi
    
    # Listar todos os apps
    apps=$(find apps -maxdepth 1 -mindepth 1 -type d -not -name "__*" -exec basename {} \;)
    
    if [ -z "$apps" ]; then
        print_info "Nenhum app Django encontrado."
        return 0
    fi
    
    print_info "Apps encontrados: $(echo $apps | tr '\n' ', ' | sed 's/,$//')"
    
    # Criar diretório migrations e __init__.py para cada app
    for app in $apps; do
        migrations_dir="apps/$app/migrations"
        
        if [ ! -d "$migrations_dir" ]; then
            mkdir -p "$migrations_dir"
            if [ $? -eq 0 ]; then
                print_success "Diretório migrations/ criado para o app $app."
            else
                print_error "Erro ao criar diretório migrations/ para $app."
                continue
            fi
        fi
        
        init_file="$migrations_dir/__init__.py"
        if [ ! -f "$init_file" ]; then
            touch "$init_file"
            if [ $? -eq 0 ]; then
                print_success "Arquivo __init__.py criado em migrations/ para o app $app."
            else
                print_error "Erro ao criar __init__.py para $app."
            fi
        fi
    done
    
    return 0
}

# Fazer commit das alterações
commit_changes() {
    print_step "Verificando alterações para commit..."
    
    changes=$(git status --porcelain)
    
    if [ -z "$changes" ]; then
        print_info "Não há alterações para commit."
        return 0
    fi
    
    echo -e "As seguintes alterações foram detectadas:\n$changes"
    
    read -p "Deseja fazer commit dessas alterações? (s/N): " response
    response=$(echo "$response" | tr '[:upper:]' '[:lower:]')
    
    if [ "$response" != "s" ]; then
        print_info "Commit cancelado pelo usuário."
        return 0
    fi
    
    # Adicionar arquivos
    git add prudentia/ settings.py urls.py wsgi.py asgi.py celery.py 2>/dev/null
    
    # Fazer commit
    git commit -m "refactor: reorganize Django files into prudentia/ package"
    
    if [ $? -eq 0 ]; then
        print_success "Commit realizado com sucesso!"
    else
        print_error "Erro ao fazer commit."
        return 1
    fi
    
    return 0
}

# Função principal
main() {
    print_header "REORGANIZAÇÃO DO REPOSITÓRIO PRUDENTIA"
    print_info "Este script reorganiza a estrutura do repositório para o padrão Django."
    
    # Verificar se estamos em um repositório git
    check_git_repo || return 1
    
    # Criar diretório prudentia/
    create_prudentia_dir || return 1
    
    # Criar arquivo __init__.py
    create_init_file || return 1
    
    # Mover arquivos de configuração
    move_django_files || return 1
    
    # Verificar manage.py
    check_manage_py || return 1
    
    # Criar diretórios para logs, media e static
    create_dirs || return 1
    
    # Criar diretórios de migrations
    create_migrations_dirs || return 1
    
    # Fazer commit das alterações
    commit_changes || return 1
    
    print_header "REORGANIZAÇÃO CONCLUÍDA COM SUCESSO"
    print_info "A estrutura do repositório foi reorganizada para o padrão Django."
    print_info "Próximos passos:"
    print_info "1. Configure o ambiente virtual e instale as dependências"
    print_info "2. Configure o arquivo .env"
    print_info "3. Configure o banco de dados"
    print_info "4. Execute as migrações e crie um superusuário"
    print_info "5. Inicie o servidor de desenvolvimento"
    
    return 0
}

# Executar função principal
main
exit $?
