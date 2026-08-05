# LETTER Platform

Plataforma fintech modular para marketplace de cotas contempladas, SDC, Flash Credit, funding, MMN, TaxTech, leilões e automações NINA.

## Estrutura

- `backend/`: API FastAPI, banco, autenticação, RBAC, regras e integrações.
- `frontend/`: painel Next.js responsivo para operação e backoffice.
- `docs/`: arquitetura, escopo por módulos e roadmap.

Tudo permanece dentro desta única pasta. As fases futuras ampliam os módulos existentes, sem criar projetos separados.

## Início rápido sem Docker

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000`  
Swagger: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Painel: `http://localhost:3000`

### Acesso de demonstração

- E-mail: `admin@letter.com.br`
- Senha: `Letter@123`

Troque essas credenciais antes de qualquer ambiente compartilhado.

## Estado atual — v0.18.0

Esta versão reúne todos os módulos anteriores e acrescenta uma esteira formal de certificação e go-live dos fornecedores. Cada integração pode executar uma matriz de conformidade, registrar aprovações independentes de Segurança, Jurídico, Compliance e Operações e gerar uma decisão auditável com blockers e hash do snapshot. Produção continua bloqueada até o registro do adaptador oficial e o atendimento integral dos gates.

As fórmulas, premissas e exemplos canônicos estão em `docs/FINANCIAL_RULES.md`. Segurança, integrações e evidências estão em `docs/SECURITY_QUALITY.md`, `docs/HOMOLOGATION_EVIDENCE_MATRIX.md`, `docs/INTEGRATIONS_HOMOLOGATION.md`, `docs/PROVIDER_OPERATIONS.md`, `docs/PROVIDER_ONBOARDING.md` e `docs/PROVIDER_ADAPTERS.md`.

Contas adicionais para testar a dupla aprovação:

- `revisor1@letter.com.br` / `Letter@123`
- `revisor2@letter.com.br` / `Letter@123`
- `investidor@letter.com.br` / `Letter@123`

Consulte `docs/ROADMAP.md` para a sequência de implementação.

## Demo na nuvem (gratuito)

Para clientes testarem pela internet: Neon (Postgres) + Render (API) + Vercel (frontend).  
Guia completo com variáveis prontas: [`deploy/DEMO_CLOUD.md`](deploy/DEMO_CLOUD.md).
