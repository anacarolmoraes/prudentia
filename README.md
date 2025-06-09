# prudentIA - Software Jurídico Inteligente

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.x-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18.x-blue.svg)](https://reactjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**prudentIA** é um sistema de gestão SaaS (Software as a Service) completo e inteligente, projetado especificamente para advogados e escritórios de advocacia brasileiros. Ele visa otimizar a rotina jurídica, automatizar tarefas repetitivas e fornecer ferramentas poderosas para uma gestão eficiente de processos, clientes e finanças.

## Índice

*   [Sobre o Projeto](#sobre-o-projeto)
    *   [Objetivo](#objetivo)
    *   [Público-Alvo](#público-alvo)
*   [Principais Funcionalidades](#principais-funcionalidades)
*   [Tecnologias Utilizadas](#tecnologias-utilizadas)
*   [Pré-requisitos](#pré-requisitos)
*   [Instalação](#instalação)
*   [Como Rodar](#como-rodar)
*   [Estrutura do Projeto](#estrutura-do-projeto)
*   [Contribuição](#contribuição)
*   [Licença](#licença)

## Sobre o Projeto

### Objetivo

O objetivo principal do prudentIA é transformar a maneira como os profissionais do direito gerenciam seu trabalho, oferecendo uma plataforma centralizada que integra todas as ferramentas necessárias para o dia a dia. Buscamos aumentar a produtividade, reduzir erros, melhorar a comunicação com clientes e garantir a segurança das informações.

### Público-Alvo

*   Advogados autônomos
*   Pequenos e médios escritórios de advocacia no Brasil

## Principais Funcionalidades

O prudentIA é um sistema robusto que engloba as funcionalidades do Astrea, além de recursos inovadores:

1.  **Gestão Completa de Processos e Casos**: Cadastro, acompanhamento de fases, organização de documentos e partes envolvidas.
2.  **Monitoramento Automático do PJe**: Robôs para buscar e atualizar andamentos processuais e publicações do PJe (`https://comunica.pje.jus.br/consulta`) e outros tribunais.
3.  **Gestão Inteligente de Prazos e Tarefas**: Agenda integrada, alertas automáticos, delegação de tarefas e visualização em Kanban.
4.  **Controle Financeiro Avançado**: Emissão de boletos com PIX, gestão de honorários, fluxo de caixa e relatórios financeiros.
5.  **Comunicação Eficiente com Clientes**: Portal do cliente, integração com WhatsApp para notificações e compartilhamento de informações.
6.  **Assinatura Digital com Blockchain**: Crie, envie e gerencie documentos para assinatura digital com validade jurídica e segurança reforçada pela tecnologia blockchain. Suporte a múltiplos signatários.
7.  **Integração com Google Drive**: Sincronização automática de documentos, backups e compartilhamento seguro.
8.  **Processamento Automatizado de Documentos**:
    *   OCR para extração de texto de PDFs e imagens.
    *   Extração automática de dados de documentos de identificação (RG, CPF, CNH, OAB, Comprovante de Residência) para preenchimento de cadastros.
    *   Geração automática de documentos (procurações, contratos) a partir de modelos e dados de clientes.
9.  **Formulários Externos Inteligentes**:
    *   Criação de formulários personalizados (ou integração com Google Forms) para coleta de dados de clientes.
    *   Preenchimento automático de documentos a partir das respostas dos formulários.
10. **Inteligência Artificial Aplicada**: Resumo de informações jurídicas, sugestões de tarefas e insights.
11. **Dashboard e Indicadores de Desempenho**: Visualização clara de métricas do escritório.
12. **Aplicativo Móvel**: Acesso às funcionalidades em qualquer lugar.
13. **Segurança e Compliance**: Criptografia, conformidade com LGPD e logs de auditoria.

Para uma lista detalhada, consulte o arquivo [Funcionalidades Completas](./docs/project_specs/funcionalidades_completas.md).

## Tecnologias Utilizadas

*   **Backend**: Python 3.10+, Django 4.x, Django REST Framework
*   **Frontend**: React 18.x (ou outro framework moderno como Vue.js/Angular)
*   **Banco de Dados**: PostgreSQL
*   **Cache**: Redis
*   **Filas de Tarefas**: Celery com RabbitMQ (ou Redis)
*   **Assinatura Digital**: Interação com uma rede Blockchain (ex: Hyperledger Fabric ou Ethereum privado)
*   **OCR e Processamento de Imagem**: Tesseract, OpenCV, PyMuPDF, pdf2image
*   **NLP**: spaCy, NLTK
*   **Containers**: Docker, Docker Compose (opcional, mas recomendado)
*   **Web Scraping**: `httpx`, `selectolax`
*   **Servidor Web (Produção)**: Gunicorn/Uvicorn + Nginx

## Pré-requisitos

Antes de começar, garanta que você tenha instalado em sua máquina:

*   Python 3.10 ou superior
*   Pip (gerenciador de pacotes Python)
*   Git
*   PostgreSQL (ou Docker para rodar uma instância)
*   Redis (ou Docker para rodar uma instância)
*   Node.js e npm/yarn (se for desenvolver o frontend separadamente)
*   Tesseract OCR (com o idioma Português: `por`)
*   LibreOffice (para conversão de DOCX para PDF, opcional)

## Instalação

Siga os passos abaixo para configurar o ambiente de desenvolvimento:

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/seu-usuario/prudentia_project.git
    cd prudentia_project
    ```

2.  **Crie e ative um ambiente virtual Python:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate    # Windows
    ```

3.  **Instale as dependências Python:**
    Use o `Pipfile` (se estiver usando `pipenv`):
    ```bash
    pipenv install --dev
    pipenv shell
    ```
    Ou, se estiver usando `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```
    *(Nota: O arquivo `requirements.txt` ou `Pipfile` será criado nos próximos passos)*

4.  **Configure as variáveis de ambiente:**
    Copie o arquivo `.env.example` para `.env` e preencha com suas configurações locais:
    ```bash
    cp .env.example .env
    ```
    Edite o arquivo `.env` com as configurações do banco de dados, chaves de API, etc.

5.  **Configure o banco de dados PostgreSQL:**
    Crie um banco de dados para o prudentIA e atualize as credenciais no arquivo `.env`.

6.  **Aplique as migrações do banco de dados:**
    ```bash
    python manage.py migrate
    ```

7.  **Crie um superusuário (administrador):**
    ```bash
    python manage.py createsuperuser
    ```

8.  **(Opcional) Instale dependências do Frontend:**
    Se o frontend for um projeto separado (ex: React), navegue até o diretório do frontend e instale as dependências:
    ```bash
    # cd frontend_directory
    # npm install
    # ou
    # yarn install
    ```

## Como Rodar

1.  **Inicie o servidor de desenvolvimento Django:**
    ```bash
    python manage.py runserver
    ```
    A aplicação estará disponível em `http://127.0.0.1:8000/`.

2.  **(Opcional) Inicie os workers Celery (para tarefas assíncronas como monitoramento PJe):**
    Em um novo terminal (com o ambiente virtual ativado):
    ```bash
    celery -A prudentia worker -l info
    ```
    E o Celery Beat (para tarefas agendadas):
    ```bash
    celery -A prudentia beat -l info
    ```

3.  **(Opcional) Inicie o servidor de desenvolvimento do Frontend:**
    Se aplicável, em outro terminal:
    ```bash
    # cd frontend_directory
    # npm start
    # ou
    # yarn start
    ```

## Estrutura do Projeto

Para uma visão detalhada da organização dos diretórios e arquivos, consulte o documento [Estrutura do Projeto](./docs/architecture/estrutura_projeto.md).

## Contribuição

Contribuições são bem-vindas! Se você deseja contribuir com o prudentIA, por favor siga estas diretrizes:

1.  **Reportando Bugs**:
    *   Verifique se o bug já não foi reportado na seção "Issues" do repositório.
    *   Abra uma nova issue detalhando o bug, incluindo passos para reproduzir, comportamento esperado e o que de fato aconteceu. Inclua screenshots se relevante.

2.  **Sugerindo Funcionalidades**:
    *   Abra uma nova issue descrevendo a funcionalidade sugerida, sua utilidade e possíveis casos de uso.

3.  **Desenvolvimento**:
    *   Faça um fork do repositório.
    *   Crie uma nova branch para sua feature ou correção de bug (`git checkout -b feature/nome-da-feature` ou `git checkout -b fix/descricao-do-bug`).
    *   Siga os padrões de código e linting do projeto (a serem definidos, ex: Black, Flake8).
    *   Escreva testes para suas alterações.
    *   Faça commits claros e concisos, seguindo o padrão de [Commits Semânticos](https://www.conventionalcommits.org/).
    *   Envie um Pull Request para a branch `main` (ou `develop`) do repositório original.

## Licença

Este projeto é licenciado sob a Licença MIT. Veja o arquivo `LICENSE` para mais detalhes (a ser adicionado).

---

Desenvolvido com ❤️ para a comunidade jurídica brasileira.
