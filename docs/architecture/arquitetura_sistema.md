# Arquitetura do Sistema – prudentIA SaaS

PrudentIA é uma plataforma SaaS em Python para gestão de processos jurídicos, monitoramento de publicações do PJe e assinatura digital baseada em blockchain. A arquitetura segue princípios **modulares** e **orientados a serviços** para garantir escalabilidade, segurança e facilidade de manutenção.

---

## 1. Visão Geral

```
[Cliente Web] ─► [API Gateway] ─► [Serviços Backend]
                               │
                               ├─► Auth Service
                               ├─► Case Management Service
                               ├─► PJe Scraper Worker
                               ├─► Signature Service (Blockchain)
                               ├─► Notification Service
                               └─► Finance Service
```

* **Frontend SPA** (React + Tailwind com paleta #FFC145) consome REST/GraphQL.
* **API Gateway** (FastAPI) centraliza roteamento, versionamento e segurança.
* Microsserviços especializados comunicam-se por HTTP (síncrono) e AMQP/RabbitMQ (assíncrono).
* Tarefas intensivas (scraping, assinatura, emissão de boletos) executam em workers Celery.

---

## 2. Tecnologias Principais

| Camada | Tecnologia | Motivo |
|--------|------------|--------|
| Frontend | React 18, Vite, Tailwind CSS | SPA rápida, fácil de themar com palette |
| Gateway & Serviços | **Python 3.12**, FastAPI | Tipagem, async, docs automáticas |
| ORMs | SQLAlchemy 2.0 | Abstração DB, migrations via Alembic |
| Message Broker | RabbitMQ | Filas para scraping & assinatura |
| Task Queue | Celery 5 | Execução distribuída de tarefas |
| Banco Relacional | PostgreSQL 15 | ACID para dados jurídicos sensíveis |
| Cache / Locking | Redis 7 | Sessões, rate-limit, locks de scraping |
| Storage de Arquivos | MinIO / S3 | Petições, documentos assinados |
| Blockchain | Hyperledger Fabric OU Rede Ethereum privada | Imutabilidade & verificação pública |
| Contêineres | Docker, Kubernetes | Deploy e escalabilidade |
| CI/CD | GitHub Actions | Testes, lint, build & push imagens |

---

## 3. Componentes e Relações

### 3.1 API Gateway
* Autenticação JWT, rate-limit, CORS.
* Redireciona chamadas para serviços internos.
* Envia eventos a RabbitMQ para tarefas assíncronas.

### 3.2 Auth Service
* Registro OAB, login (email/OAuth), MFA.
* Tabelas `users`, `lawyers`, `permissions`.

### 3.3 Case Management Service
* CRUD de **Processos**, **Prazos**, **Tarefas**.
* Webhooks interna ↔️ Notification Service para alertas.
* Índices em PostgreSQL para busca rápida por número CNJ.

### 3.4 PJe Scraper Worker
* _Celery beat_ agenda varreduras (cron configurável por usuário).
* Usa **httpx + asyncio** para GET em 
  `https://comunica.pje.jus.br/consulta?numeroOab=...&ufOab=...&dataDisponibilizacaoInicio=...&dataDisponibilizacaoFim=...`
* Parser `selectolax` extrai publicações → grava em `publications` + dispara evento.

### 3.5 Signature Service
* Gera hash SHA-256 do PDF, registra na **Blockchain** (smart-contract `SignRegistry`).
* Fluxo:
  1. Uploader → Gateway (documento)
  2. Signature Service cria transação e armazena ID on-chain
  3. PDF recebe _campo de assinatura_ (PyPDF2) e link de verificação
  4. Multi-sign: cada signatário assina; ao final hash final é gravado on-chain.
* API REST: `/signatures`, `/verify/{docId}`.

### 3.6 Notification Service
* Dispara emails (Amazon SES), WhatsApp (Meta API) e in-app.
* Templates i18n com Jinja2.

### 3.7 Finance Service
* Emissão de boletos com PIX (Gerencianet API).
* Tabelas `invoices`, `payments`.

---

## 4. Fluxos Principais

### 4.1 Cadastro de Processo
1. Usuário cria processo no SPA → Gateway → Case Management.
2. Service grava DB, devolve objeto; SPA atualiza UI.

### 4.2 Monitoramento Automático
1. Celery beat envia job ao Scraper Worker.
2. Worker faz request PJe, compara publicações novas.
3. Novidade → salva DB → publica msg `publication.new`.
4. Notification Service consome e avisa usuário.

### 4.3 Assinatura Digital
1. Advogado faz upload de contrato.
2. Seleciona signatários → Signature Service cria **workflow**.
3. Cada signatário recebe link (token) → assina.
4. Após último, hash final gravado em blockchain.
5. Documento carimbado + certificado JSON disponível para download.

---

## 5. Segurança & Compliance

* Criptografia em repouso (AES-256) e em trânsito (TLS1.3).
* LGPD: segregação de dados, logs de acesso, consentimento.
* Rate limiting no Gateway e CSRF tokens no SPA.
* Blockchain garante integridade das assinaturas.

---

## 6. Escalabilidade

* Serviços stateless em pods Kubernetes com HPA.
* Worker pools independentes (scraping, assinatura, notificações).
* PostgreSQL em cluster (Patroni) e Redis com sentinels.
* Observabilidade: Prometheus + Grafana, ELK para logs.

---

## 7. Deploy & CI/CD

1. **GitHub Actions**: lint (ruff), testes (pytest), build Docker.
2. Push para registry → ArgoCD atualiza K8s (dev/stage/prod).
3. Migrations autogeridas via Alembic job.

---

## 8. Roadmap de Implementação

| Fase | Entregas | Duração |
|------|----------|---------|
| 1 | Setup repo, CI/CD, Gateway + Auth | 2 sprints |
| 2 | Case Management core + UI | 3 sprints |
| 3 | Scraper Worker MVP | 2 sprints |
| 4 | Signature Service (single signer) | 2 sprints |
| 5 | Multi-signer + Blockchain integ. | 2 sprints |
| 6 | Finance + Notifications | 2 sprints |
| 7 | Hardening, testes de carga | 1 sprint |
| 8 | Go-live & monitoramento | – |

---

### Conclusão
Esta arquitetura modular em Python oferece **agilidade**, **segurança jurídica** e **inovação** (blockchain), alinhando-se às necessidades dos advogados brasileiros para gestão de processos e assinaturas digitais confiáveis. 
