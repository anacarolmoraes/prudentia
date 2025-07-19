# prudentIA – Reorganização da Estrutura do Projeto

Este guia explica **por que** existem scripts de reorganização no repositório e **como utilizá-los**.  
O objetivo é adequar a estrutura dos arquivos de configuração ao padrão oficial do Django, onde todos eles ficam dentro de um pacote (diretório) chamado **`prudentia/`**.

---

## 1. Por que é necessário?

Atualmente, seus arquivos de configuração estão na raiz:

```
settings.py
urls.py
wsgi.py
asgi.py
celery.py
manage.py
```

O `manage.py` procura por `prudentia.settings`, portanto esses arquivos **precisam** residir em `prudentia/`.  
Os scripts automatizam:

1. Criação (ou validação) do diretório `prudentia/`.
2. Criação de `prudentia/__init__.py` (torna o diretório um *package* e faz *bootstrap* do Celery).
3. Movimentação dos arquivos de configuração para o local correto.
4. Criação de pastas auxiliares (`logs/`, `media/`, `static/`).
5. Geração de diretórios de **migrations** com `__init__.py` para todos os apps em `apps/`.
6. Exibição das alterações e oferta de **commit** automático com Git (`refactor: reorganize Django files into prudentia/ package`).

---

## 2. Scripts disponíveis

| Sistema operacional | Script | Linguagem | Uso recomendado |
|---------------------|--------|-----------|-----------------|
| Linux / macOS       | `reorganize_repo.sh` | Bash      | Executar direto no terminal |
| Windows             | `reorganize_repo.bat`| Batch     | Executar em PowerShell/CMD |
| Qualquer            | `reorganize_repo.py` | Python 3 | Fallback universal (requer Python ≥ 3.8) |

Todos os scripts realizam **exatamente** as mesmas etapas; escolha o mais conveniente.

---

## 3. Execução passo a passo

1. Abra um terminal na **raiz** do repositório (onde está `manage.py`).
2. **Opcional**: crie uma branch de segurança antes de rodar:

   ```bash
   git checkout -b chore/reorganize-structure
   ```

3. Execute o script correspondente:

   ### Linux / macOS

   ```bash
   chmod +x reorganize_repo.sh
   ./reorganize_repo.sh
   ```

   ### Windows

   ```powershell
   reorganize_repo.bat
   ```

   ### Qualquer (Python)

   ```bash
   python reorganize_repo.py
   ```

4. O script mostrará cada ação e, ao final, listará mudanças pendentes.  
   Você poderá digitar **`s`** para confirmar o *commit* automático ou **`N`** para revisar manualmente.

---

## 4. O que **não** é feito

* Instalar dependências (use `setup_environment.sh`/`.bat` ou `pip install -r requirements.txt`).
* Criar/editar `.env`.
* Executar migrações ou iniciar servidor.
* Dar *push* para o GitHub – isso continua sob seu controle.

---

## 5. Checklist pós-execução

1. Ative seu **venv** e execute:

   ```bash
   pip install -r requirements.txt
   ```

2. Copie e edite o `.env`:

   ```bash
   cp env.example .env
   ```

3. Rode migrações e crie um superusuário:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. Inicie o servidor:

   ```bash
   python manage.py runserver
   ```

5. (Opcional) Inicie Celery e Redis conforme necessidade.

---

## 6. Solução rápida de problemas

| Mensagem / Sintoma | Possível causa & solução |
|--------------------|--------------------------|
| `ModuleNotFoundError: prudentia.settings` | Certifique-se de que `prudentia/__init__.py` existe e que os arquivos foram movidos. |
| `fatal: not a git repository`             | Execute o script na pasta onde está o repositório clonad​o. |
| Script sem permissão (Linux/macOS)        | Rode `chmod +x reorganize_repo.sh` antes de executar. |
| Git reclama de arquivos não rastreados    | Revise com `git status`, depois `git add` manual ou use a opção de commit automático. |

---

**Pronto!** Com a estrutura reorganizada, seu projeto seguirá as melhores práticas do Django e evitará erros de importação. Se precisar de ajuda adicional, abra uma *issue* ou consulte a documentação na pasta `docs/`.  
Boas implementações! 🚀
