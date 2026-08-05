# Deploy demo gratuito — Neon + Render + Vercel

Objetivo: vários clientes testarem a plataforma inteira pela internet, sem cPanel.

Tempo estimado: 20–40 minutos (primeira vez).

## Arquitetura

```
Cliente  →  Vercel (Next.js)  →  Render (FastAPI)  →  Neon (Postgres)
```

| Peça | Serviço | Plano |
|------|---------|-------|
| Frontend | [vercel.com](https://vercel.com) | Hobby (grátis) |
| API | [render.com](https://render.com) | Free Web Service |
| Banco | [neon.tech](https://neon.tech) | Free Postgres |

**Avisos do free tier**
- No Render a API “dorme” após ~15 min sem uso. O 1º acesso pode levar 30–60s.
- Storage local no Render é efêmero (uploads podem sumir no redeploy). Ok para demo.
- `LETTER_FINANCIAL_TRANSACTIONS_ENABLED=false` — sem dinheiro real.

## Pré-requisitos

1. Conta no GitHub com este repositório (ou fork).
2. Contas gratuitas: Neon, Render, Vercel.
3. Defina uma senha de demo forte (ex.: `TroqueEstaSenha@Demo2026`).

---

## 1) Neon — criar o banco

1. Acesse https://console.neon.tech e crie um projeto (região próxima, ex. São Paulo se disponível).
2. Copie a **connection string** URI (deve ter `sslmode=require`).
3. Guarde como `LETTER_DATABASE_URL`.

Exemplo (não use este):

```text
postgresql://user:pass@ep-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require
```

A API converte automaticamente para `postgresql+psycopg://` no startup.

---

## 2) Render — subir a API

### Opção A — Blueprint (recomendado)

1. Render → **New** → **Blueprint**.
2. Conecte o repositório e selecione `deploy/render.yaml`.
3. Preencha as variáveis marcadas como `sync: false`:

| Variável | Valor |
|----------|--------|
| `LETTER_DATABASE_URL` | URI do Neon |
| `LETTER_CORS_ORIGINS` | URL da Vercel (passo 3). Se ainda não tiver, use `https://placeholder.vercel.app` e atualize depois |
| `LETTER_DEMO_PASSWORD` | Senha forte compartilhada com os clientes |

4. Deploy. Anote a URL: `https://letter-api-xxxx.onrender.com`.
5. Teste: `https://letter-api-xxxx.onrender.com/api/v1/health` → `{"status":"ok",...}`  
   Swagger: `https://letter-api-xxxx.onrender.com/docs`

### Opção B — Web Service manual

1. **New** → **Web Service** → repositório.
2. Configuração:

| Campo | Valor |
|-------|--------|
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `bash scripts/start_cloud.sh` |
| Plan | Free |
| Health Check Path | `/api/v1/health` |
| Env `PYTHON_VERSION` | `3.12.10` (obrigatório — 3.14 quebra o build do pydantic) |

3. Cole as variáveis de `deploy/env.cloud.example` (seção Render).
4. Deploy.

O start script já roda: `alembic upgrade head` → `python -m app.seed` → `uvicorn`.

---

## 3) Vercel — subir o frontend

1. https://vercel.com → **Add New Project** → importe o repositório.
2. Configure:

| Campo | Valor |
|-------|--------|
| Root Directory | `frontend` |
| Framework | Next.js |
| Build Command | `npm run build` (padrão) |
| Install Command | `npm install` |

3. Environment Variable:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | `https://letter-api-xxxx.onrender.com/api/v1` |

(use a URL real do Render, **com** `/api/v1` no final)

4. Deploy. Anote a URL: `https://seu-app.vercel.app`.

---

## 4) Fechar o CORS

No Render → letter-api → Environment:

```text
LETTER_CORS_ORIGINS=https://seu-app.vercel.app
```

Se tiver domínio customizado na Vercel, inclua ambos separados por vírgula:

```text
LETTER_CORS_ORIGINS=https://seu-app.vercel.app,https://demo.letter.app.br
```

Salve e faça **Manual Deploy** da API (para recarregar env).

---

## 5) Contas de demonstração

Criadas no primeiro seed (`LETTER_DEMO_PASSWORD`):

| Papel | E-mail | Uso |
|-------|--------|-----|
| Admin | `admin@letter.com.br` | Acesso total |
| Revisor 1 | `revisor1@letter.com.br` | Dupla aprovação |
| Revisor 2 | `revisor2@letter.com.br` | Dupla aprovação |
| Investidor | `investidor@letter.com.br` | Funding / perfil investidor |
| Parceiro | `parceiro@letter.com.br` | Rede / CRM |

**Senha:** a que você colocou em `LETTER_DEMO_PASSWORD` (não use `Letter@123` em ambiente compartilhado).

> O seed é idempotente: se o admin já existe, não recria usuários. Para resetar a demo, apague o banco no Neon (ou crie um branch novo) e redeploy a API.

---

## 6) Texto pronto para enviar aos clientes

```text
Olá! Segue o ambiente de demonstração da LETTER Platform:

URL: https://seu-app.vercel.app

Contas de teste (mesma senha em todas):
- Admin: admin@letter.com.br
- Revisor 1: revisor1@letter.com.br
- Revisor 2: revisor2@letter.com.br
- Investidor: investidor@letter.com.br

Senha: <LETTER_DEMO_PASSWORD>

Observações:
1) Ambiente de demonstração — sem transações financeiras reais.
2) No primeiro acesso do dia a API pode demorar até 1 minuto para “acordar”.
3) Dados podem ser resetados entre rodadas de teste.
```

---

## Checklist rápido

- [ ] Neon URI com `sslmode=require`
- [ ] Render health `/api/v1/health` = 200
- [ ] Swagger `/docs` abre
- [ ] Vercel com `NEXT_PUBLIC_API_URL` apontando para Render `/api/v1`
- [ ] `LETTER_CORS_ORIGINS` = URL da Vercel
- [ ] `LETTER_DEMO_PASSWORD` forte
- [ ] `LETTER_FINANCIAL_TRANSACTIONS_ENABLED=false`
- [ ] Login no frontend com `admin@letter.com.br`

---

## Problemas comuns

| Sintoma | Causa provável | Correção |
|---------|----------------|----------|
| Frontend carrega, APIs falham (CORS) | Origem Vercel não está no CORS | Atualize `LETTER_CORS_ORIGINS` e redeploy API |
| Timeout no 1º login | Cold start do Render free | Aguarde e tente de novo |
| 500 na API ao subir | URL do Neon inválida / sem SSL | Confira URI e `sslmode=require` |
| Login “credenciais inválidas” | Seed antigo com outra senha | Novo banco Neon ou limpar dados e redeploy |
| `/docs` em branco | CSP (já tratado no código) | Hard refresh; se persistir, abra `/openapi.json` |

---

## Arquivos deste pacote

- `deploy/render.yaml` — blueprint Render
- `deploy/env.cloud.example` — variáveis para copiar
- `deploy/DEMO_CLOUD.md` — este guia
- `backend/scripts/start_cloud.sh` — migrate + seed + uvicorn
- `frontend/vercel.json` — hint de build Next.js
