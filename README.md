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

## Estado atual — v0.24.0

Esta versão preserva todos os módulos anteriores e acrescenta o roteamento fiduciário NINA: políticas demográficas versionadas, resgate de pautas de risco somente com garantia imobiliária, filtro de prenotações, bifurcação Fundos/Pool, evidência TAPAF, vistoria física obrigatória, aprovação de comitê e Valid-Stamp sem autorização automática de payout. Cobranças, Pix, repasses, leilões, estornos e efeitos patrimoniais reais seguem desativados.

As novas frentes estão documentadas em `docs/NINA_ROUTING_GOVERNANCE.md`.

Contas adicionais para testar a dupla aprovação:

- `revisor1@letter.com.br` / `Letter@123`
- `revisor2@letter.com.br` / `Letter@123`
- `investidor@letter.com.br` / `Letter@123`

Consulte `docs/ROADMAP.md` para a sequência de implementação.
