#!/usr/bin/env python
"""
reorganize_repo.py - Script para reorganizar a estrutura do repositório prudentIA

Este script reorganiza os arquivos do repositório, movendo os arquivos de configuração
do Django para o diretório prudentia/ e configurando a estrutura correta.
"""

import os
import shutil
import subprocess
import sys

# Cores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_colored(text, color):
    """Imprime texto colorido no terminal"""
    print(f"{color}{text}{Colors.END}")

def print_header(text):
    """Imprime um cabeçalho formatado"""
    print("\n" + "=" * 80)
    print_colored(f" {text} ", Colors.BOLD + Colors.BLUE)
    print("=" * 80)

def print_step(text):
    """Imprime um passo da execução"""
    print_colored(f"\n➤ {text}", Colors.YELLOW)

def print_success(text):
    """Imprime uma mensagem de sucesso"""
    print_colored(f"✓ {text}", Colors.GREEN)

def print_error(text):
    """Imprime uma mensagem de erro"""
    print_colored(f"✗ {text}", Colors.RED)

def print_info(text):
    """Imprime uma informação"""
    print(f"  {text}")

def run_command(command):
    """Executa um comando shell e retorna o resultado"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def check_git_repo():
    """Verifica se estamos em um repositório git"""
    print_step("Verificando repositório git...")
    success, output = run_command("git rev-parse --is-inside-work-tree")
    
    if success:
        print_success("Repositório git encontrado.")
        return True
    else:
        print_error("Este diretório não é um repositório git.")
        print_info("Execute este script na raiz do repositório prudentIA.")
        return False

def create_prudentia_dir():
    """Cria o diretório prudentia/ se não existir"""
    print_step("Verificando/criando diretório prudentia/...")
    
    if os.path.exists("prudentia"):
        if os.path.isdir("prudentia"):
            print_success("Diretório prudentia/ já existe.")
        else:
            print_error("prudentia existe, mas não é um diretório!")
            return False
    else:
        try:
            os.mkdir("prudentia")
            print_success("Diretório prudentia/ criado com sucesso.")
        except Exception as e:
            print_error(f"Erro ao criar diretório prudentia/: {e}")
            return False
    
    return True

def create_init_file():
    """Cria o arquivo __init__.py no diretório prudentia/"""
    print_step("Criando arquivo __init__.py...")
    
    init_path = os.path.join("prudentia", "__init__.py")
    
    if os.path.exists(init_path):
        print_success("Arquivo __init__.py já existe.")
    else:
        try:
            with open(init_path, "w") as f:
                f.write("""# Este arquivo torna o diretório prudentia/ um pacote Python
# Import Celery app
try:
    from .celery import app as celery_app
    __all__ = ["celery_app"]
except ImportError:
    # Celery não configurado ainda
    pass
""")
            print_success("Arquivo __init__.py criado com sucesso.")
        except Exception as e:
            print_error(f"Erro ao criar arquivo __init__.py: {e}")
            return False
    
    return True

def move_django_files():
    """Move os arquivos de configuração do Django para prudentia/"""
    print_step("Movendo arquivos de configuração do Django...")
    
    django_files = ["settings.py", "urls.py", "wsgi.py", "asgi.py", "celery.py"]
    moved_files = []
    
    for file in django_files:
        if os.path.exists(file):
            dest_path = os.path.join("prudentia", file)
            
            # Verificar se o arquivo já existe no destino
            if os.path.exists(dest_path):
                print_info(f"Arquivo {file} já existe em prudentia/")
                continue
                
            try:
                shutil.move(file, dest_path)
                moved_files.append(file)
                print_success(f"Arquivo {file} movido com sucesso.")
            except Exception as e:
                print_error(f"Erro ao mover arquivo {file}: {e}")
        else:
            print_info(f"Arquivo {file} não encontrado na raiz.")
    
    if not moved_files:
        print_info("Nenhum arquivo precisou ser movido.")
    
    return True

def update_manage_py():
    """Verifica se manage.py está configurado corretamente"""
    print_step("Verificando arquivo manage.py...")
    
    if not os.path.exists("manage.py"):
        print_error("Arquivo manage.py não encontrado!")
        return False
    
    try:
        with open("manage.py", "r") as f:
            content = f.read()
        
        # Verificar se já está configurado corretamente
        if "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings')" in content or \
           'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "prudentia.settings")' in content:
            print_success("Arquivo manage.py já está configurado corretamente.")
            return True
        
        # Se não estiver configurado corretamente, alertar o usuário
        print_info("O arquivo manage.py pode precisar ser atualizado.")
        print_info("Verifique se ele contém: os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prudentia.settings')")
        
    except Exception as e:
        print_error(f"Erro ao verificar arquivo manage.py: {e}")
    
    return True

def update_imports():
    """Atualiza as importações nos arquivos movidos"""
    print_step("Atualizando importações nos arquivos...")
    
    files_to_check = [
        os.path.join("prudentia", "settings.py"),
        os.path.join("prudentia", "urls.py"),
        os.path.join("prudentia", "wsgi.py"),
        os.path.join("prudentia", "asgi.py"),
        os.path.join("prudentia", "celery.py")
    ]
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, "r") as f:
                content = f.read()
            
            # Substituir importações absolutas por relativas
            updated_content = content
            
            # Exemplo: from settings import XYZ -> from .settings import XYZ
            for module in ["settings", "urls", "wsgi", "asgi", "celery"]:
                updated_content = updated_content.replace(
                    f"from {module} import", 
                    f"from .{module} import"
                )
                updated_content = updated_content.replace(
                    f"import {module}", 
                    f"import .{module}"
                )
            
            if updated_content != content:
                with open(file_path, "w") as f:
                    f.write(updated_content)
                print_success(f"Importações atualizadas em {file_path}")
            else:
                print_info(f"Nenhuma atualização necessária em {file_path}")
                
        except Exception as e:
            print_error(f"Erro ao atualizar importações em {file_path}: {e}")
    
    return True

def commit_changes():
    """Faz commit das alterações"""
    print_step("Verificando alterações para commit...")
    
    success, output = run_command("git status --porcelain")
    
    if not success:
        print_error("Erro ao verificar status do git.")
        return False
    
    if not output.strip():
        print_info("Não há alterações para commit.")
        return True
    
    print_info("As seguintes alterações foram detectadas:")
    print(output)
    
    response = input("\nDeseja fazer commit dessas alterações? (s/N): ").strip().lower()
    
    if response != 's':
        print_info("Commit cancelado pelo usuário.")
        return True
    
    # Adicionar arquivos
    success, _ = run_command("git add prudentia/ settings.py urls.py wsgi.py asgi.py celery.py")
    
    if not success:
        print_error("Erro ao adicionar arquivos ao stage.")
        return False
    
    # Fazer commit
    commit_message = "refactor: reorganize Django files into prudentia/ package"
    success, _ = run_command(f'git commit -m "{commit_message}"')
    
    if not success:
        print_error("Erro ao fazer commit.")
        return False
    
    print_success("Commit realizado com sucesso!")
    return True

def create_logs_media_dirs():
    """Cria diretórios para logs e media"""
    print_step("Criando diretórios para logs e media...")
    
    dirs_to_create = ["logs", "media", "static"]
    
    for dir_name in dirs_to_create:
        if os.path.exists(dir_name):
            if os.path.isdir(dir_name):
                print_info(f"Diretório {dir_name}/ já existe.")
            else:
                print_error(f"{dir_name} existe, mas não é um diretório!")
        else:
            try:
                os.mkdir(dir_name)
                print_success(f"Diretório {dir_name}/ criado com sucesso.")
            except Exception as e:
                print_error(f"Erro ao criar diretório {dir_name}/: {e}")
    
    return True

def create_migrations_dirs():
    """Cria diretórios de migrations para os apps Django"""
    print_step("Criando diretórios de migrations para os apps...")
    
    if not os.path.exists("apps"):
        print_info("Diretório apps/ não encontrado. Pulando criação de migrations.")
        return True
    
    # Listar todos os apps
    apps = []
    for item in os.listdir("apps"):
        app_dir = os.path.join("apps", item)
        if os.path.isdir(app_dir) and not item.startswith("__"):
            apps.append(item)
    
    if not apps:
        print_info("Nenhum app Django encontrado.")
        return True
    
    print_info(f"Apps encontrados: {', '.join(apps)}")
    
    # Criar diretório migrations e __init__.py para cada app
    for app in apps:
        migrations_dir = os.path.join("apps", app, "migrations")
        
        if not os.path.exists(migrations_dir):
            try:
                os.mkdir(migrations_dir)
                print_success(f"Diretório migrations/ criado para o app {app}.")
            except Exception as e:
                print_error(f"Erro ao criar diretório migrations/ para {app}: {e}")
                continue
        
        init_file = os.path.join(migrations_dir, "__init__.py")
        if not os.path.exists(init_file):
            try:
                with open(init_file, "w") as f:
                    pass  # Criar arquivo vazio
                print_success(f"Arquivo __init__.py criado em migrations/ para o app {app}.")
            except Exception as e:
                print_error(f"Erro ao criar __init__.py para {app}: {e}")
    
    return True

def main():
    """Função principal"""
    print_header("REORGANIZAÇÃO DO REPOSITÓRIO PRUDENTIA")
    print_info("Este script reorganiza a estrutura do repositório para o padrão Django.")
    
    # Verificar se estamos em um repositório git
    if not check_git_repo():
        return 1
    
    # Criar diretório prudentia/
    if not create_prudentia_dir():
        return 1
    
    # Criar arquivo __init__.py
    if not create_init_file():
        return 1
    
    # Mover arquivos de configuração
    if not move_django_files():
        return 1
    
    # Verificar manage.py
    if not update_manage_py():
        return 1
    
    # Atualizar importações
    if not update_imports():
        return 1
    
    # Criar diretórios para logs, media e static
    if not create_logs_media_dirs():
        return 1
    
    # Criar diretórios de migrations
    if not create_migrations_dirs():
        return 1
    
    # Fazer commit das alterações
    if not commit_changes():
        return 1
    
    print_header("REORGANIZAÇÃO CONCLUÍDA COM SUCESSO")
    print_info("A estrutura do repositório foi reorganizada para o padrão Django.")
    print_info("Próximos passos:")
    print_info("1. Configure o ambiente virtual e instale as dependências")
    print_info("2. Configure o arquivo .env")
    print_info("3. Configure o banco de dados")
    print_info("4. Execute as migrações e crie um superusuário")
    print_info("5. Inicie o servidor de desenvolvimento")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
