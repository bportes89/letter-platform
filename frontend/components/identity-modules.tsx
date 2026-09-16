"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, KeyRound, Plus, RefreshCw, ShieldCheck, UserPlus, Users } from "lucide-react";
import { api, AuthSession, Branch, Invitation, KycCase, User } from "@/lib/api";
import { AdminUserForm } from "@/components/admin-user-form";
import { MfaSetupPanel } from "@/components/mfa-setup-panel";

const roles = ["PLATFORM_ADMIN","INTERNAL_STAFF","MASTER_FRANCHISEE","MANAGER","PARTNER","CLIENT","QUOTA_SELLER","RETAIL_INVESTOR","INSTITUTIONAL_FUND","AUDITOR"];
const date = (value:string|null) => value ? new Date(value).toLocaleString("pt-BR") : "—";

function inviteLink(token: string) {
  return `${window.location.origin}/convite?token=${encodeURIComponent(token)}`;
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const area = document.createElement("textarea");
  area.value = value;
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  document.body.removeChild(area);
}

export function IdentityModule() {
  const [users, setUsers] = useState<User[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [message, setMessage] = useState("");
  const [apiError, setApiError] = useState("");
  const [usersError, setUsersError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [lastInviteLink, setLastInviteLink] = useState("");

  const loadBranches = useCallback(async () => api<Branch[]>("/admin/branches"), []);
  const loadInvites = useCallback(async () => api<Invitation[]>("/admin/invitations"), []);
  const loadUsers = useCallback(async () => api<User[]>("/admin/users"), []);

  const load = useCallback(async () => {
    setLoading(true);
    const [usersResult, branchesResult, invitesResult] = await Promise.allSettled([
      loadUsers(),
      loadBranches(),
      loadInvites(),
    ]);
    const errors: string[] = [];

    if (branchesResult.status === "fulfilled") {
      setBranches(branchesResult.value);
    } else {
      errors.push("filiais");
    }

    if (invitesResult.status === "fulfilled") {
      setInvites(invitesResult.value);
    } else {
      errors.push("convites");
    }

    if (usersResult.status === "fulfilled") {
      setUsers(usersResult.value);
      setUsersError("");
    } else {
      setUsers([]);
      setUsersError(
        usersResult.reason instanceof Error
          ? usersResult.reason.message
          : "Não foi possível carregar a lista de usuários.",
      );
      errors.push("usuários");
    }

    if (errors.length === 3) {
      const first = [usersResult, branchesResult, invitesResult].find((item) => item.status === "rejected") as PromiseRejectedResult;
      setApiError(first.reason instanceof Error ? first.reason.message : "Falha ao carregar identidade.");
    } else {
      setApiError(errors.length ? `Alguns dados não carregaram (${errors.join(", ")}). Clique em Atualizar.` : "");
    }

    setLoading(false);
  }, [loadBranches, loadInvites, loadUsers]);

  useEffect(() => {
    void load();
  }, [load]);

  async function branch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    setMessage("");
    try {
      const created = await api<Branch>("/admin/branches", {
        method: "POST",
        body: JSON.stringify({
          name: f.get("name"),
          code: f.get("code"),
          region: f.get("region") || null,
        }),
      });
      form.reset();
      setBranches((prev) => {
        const next = [...prev.filter((item) => item.id !== created.id), created];
        return next.sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
      });
      setMessage(`Filial "${created.name}" criada (${created.code}) e salva no sistema.`);
      setApiError("");
      try {
        setBranches(await loadBranches());
      } catch {
        /* mantém lista otimista se o reload falhar */
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Não foi possível criar a filial.");
    } finally {
      setBusy(false);
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const f = new FormData(form);
    const branchId = String(f.get("branch_id") || "").trim();
    setBusy(true);
    setMessage("");
    try {
      const item = await api<Invitation>("/admin/invitations", {
        method: "POST",
        body: JSON.stringify({
          email: f.get("email"),
          role: f.get("role"),
          branch_id: branchId || null,
        }),
      });
      form.reset();
      const link = typeof window !== "undefined" && item.token ? inviteLink(item.token) : "";
      setLastInviteLink(link);
      const emailed = item.email_delivery_status === "DELIVERED";
      setMessage(
        link
          ? emailed
            ? `Convite criado para ${item.email}. E-mail enviado — se não chegar em alguns minutos, copie o link abaixo.`
            : `Convite criado para ${item.email}. O envio automático por e-mail ainda não está ativo no servidor — copie o link abaixo e envie ao convidado.`
          : `Convite criado para ${item.email}.`,
      );
      setApiError("");
      try {
        setInvites(await loadInvites());
      } catch {
        setInvites((prev) => [item, ...prev.filter((row) => row.id !== item.id)]);
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Não foi possível gerar o convite.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Heading
        icon={<Users />}
        eyebrow="IDENTIDADE E REDE"
        title="Pessoas, filiais e convites"
        text="Administração multiunidade com papéis, vínculo regional e ciclo de entrada controlado."
      />
      {apiError && (
        <div className="notice" style={{ borderColor: "#f5c2c0", background: "#fff5f5" }}>
          <ShieldCheck />
          {apiError} Aguarde até 1 minuto e clique em <b>Atualizar</b>.
        </div>
      )}
      {message && <div className="notice"><ShieldCheck />{message}</div>}
      {lastInviteLink && (
        <div className="notice">
          <ShieldCheck />
          Link do convite: <code style={{ wordBreak: "break-all" }}>{lastInviteLink}</code>
          <button type="button" style={{ marginLeft: 12 }} onClick={() => void copyText(lastInviteLink).then(() => setMessage("Link copiado."))}>
            Copiar link
          </button>
        </div>
      )}
      <div className="admin-grid">
        <section className="panel">
          <div className="panel-title">
            <h2><Building2 /> Nova filial</h2>
            <button type="button" onClick={() => void load()} disabled={loading || busy}>
              <RefreshCw />Atualizar
            </button>
          </div>
          <form className="stack-form" onSubmit={branch}>
            <input name="name" placeholder="Nome da filial" required disabled={busy} />
            <input name="code" placeholder="Código" required disabled={busy} />
            <input name="region" placeholder="Região" disabled={busy} />
            <button disabled={busy}><Plus />{busy ? "Salvando…" : "Criar filial"}</button>
          </form>
          <div style={{ marginTop: 16 }}>
            <small style={{ display: "block", color: "var(--muted)", marginBottom: 8 }}>
              Filiais cadastradas ({branches.length})
            </small>
            {loading ? (
              <small className="muted">Carregando filiais…</small>
            ) : branches.length === 0 ? (
              <small className="muted">Nenhuma filial ainda. Crie acima ou atualize após a API voltar.</small>
            ) : (
              branches.map((b) => (
                <div className="session-row" key={b.id}>
                  <div>
                    <b>{b.name}</b>
                    <small>{b.code}{b.region ? ` · ${b.region}` : ""}</small>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
        <section className="panel">
          <AdminUserForm
            branches={branches}
            busy={busy || loading}
            onCreated={(user) => {
              setUsers((prev) => [user, ...prev.filter((row) => row.id !== user.id)]);
              setMessage(`Administrador "${user.name}" criado com sucesso.`);
              setApiError("");
            }}
            onError={(msg) => setMessage(msg)}
          />
        </section>
        <section className="panel">
          <h2><UserPlus /> Convidar usuário</h2>
          <form className="stack-form" onSubmit={invite}>
            <input name="email" type="email" placeholder="E-mail" required disabled={busy} />
            <select name="role" disabled={busy}>
              {roles.map((r) => <option key={r}>{r}</option>)}
            </select>
            <select name="branch_id" disabled={busy || branches.length === 0}>
              <option value="">Sem filial (Matriz)</option>
              {branches.map((b) => (
                <option value={b.id} key={b.id}>{b.name} ({b.code})</option>
              ))}
            </select>
            <button disabled={busy}><UserPlus />{busy ? "Gerando…" : "Gerar convite"}</button>
          </form>
          <small className="muted" style={{ display: "block", marginTop: 12 }}>
            Com SMTP ou Resend configurado no Render, o convite é enviado por e-mail. Caso contrário, copie o link gerado e envie manualmente.
          </small>
        </section>
      </div>
      <section className="panel identity-table">
        <div className="panel-title">
          <h2>Usuários ({users.length})</h2>
          <span>{branches.length} filiais</span>
        </div>
        {usersError && (
          <small className="muted" style={{ display: "block", marginBottom: 12, color: "#b42318" }}>
            {usersError}
          </small>
        )}
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Papel</th>
                <th>Filial</th>
                <th>MFA</th>
                <th>Último acesso</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td><b>{u.name}</b><small>{u.email}</small></td>
                  <td>{u.role}</td>
                  <td>{branches.find((b) => b.id === u.branch_id)?.name ?? "Matriz"}</td>
                  <td><span className={`pill ${u.mfa_enabled ? "pill-approved" : ""}`}>{u.mfa_enabled ? "ATIVO" : "PENDENTE"}</span></td>
                  <td>{date(u.last_login_at)}</td>
                  <td>{u.active ? "Ativo" : "Inativo"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel identity-table">
        <h2>Convites recentes</h2>
        {invites.map((i) => (
          <div className="session-row" key={i.id}>
            <div>
              <b>{i.email}</b>
              <small>{i.role} · expira {date(i.expires_at)}</small>
            </div>
            <span className={`pill pill-${i.status.toLowerCase()}`}>{i.status}</span>
          </div>
        ))}
      </section>
    </>
  );
}

export function SecurityModule(){
  const [sessions,setSessions]=useState<AuthSession[]>([]),[message,setMessage]=useState("");
  const load=useCallback(()=>api<AuthSession[]>("/auth/sessions").then(setSessions),[]);useEffect(()=>{load().catch(e=>setMessage(e.message))},[load]);
  async function revoke(id:string){await api(`/auth/sessions/${id}`,{method:"DELETE"});setMessage("Sessão revogada.");await load()}
  async function stepUp(event:FormEvent<HTMLFormElement>){event.preventDefault();const f=new FormData(event.currentTarget);await api("/auth/step-up",{method:"POST",body:JSON.stringify({password:f.get("password"),otp:f.get("otp")||null})});setMessage("Autenticação reforçada válida por 10 minutos.");await load()}
  return <><Heading icon={<KeyRound/>} eyebrow="SEGURANÇA" title="Sessões e autenticação reforçada" text="MFA TOTP, rotação de refresh token, revogação de sessões e step-up para ações financeiras."/>{message&&<div className="notice"><ShieldCheck/>{message}</div>}<div className="admin-grid"><MfaSetupPanel compact /><section className="panel"><h2>Step-up financeiro</h2><form className="stack-form" onSubmit={stepUp}><input name="password" type="password" placeholder="Confirme sua senha" required/><input name="otp" inputMode="numeric" placeholder="MFA, se ativado"/><button><ShieldCheck/>Autorizar por 10 minutos</button></form></section></div><section className="panel identity-table"><div className="panel-title"><h2>Sessões</h2><button onClick={()=>load()}><RefreshCw/>Atualizar</button></div>{sessions.map(s=><div className="session-row" key={s.id}><div><b>{s.user_agent||"Cliente desconhecido"}</b><small>{s.ip_address||"IP indisponível"} · vista {date(s.last_seen_at)} · expira {date(s.expires_at)}</small></div><div className="actions-cell"><span className={`pill ${s.active?"pill-approved":"pill-cancelled"}`}>{s.active?"ATIVA":"REVOGADA"}</span>{s.active&&<button className="table-action" onClick={()=>revoke(s.id)}>Revogar</button>}</div></div>)}</section></>
}

export function ComplianceModule(){
  const [cases,setCases]=useState<KycCase[]>([]),[message,setMessage]=useState("");const load=useCallback(()=>api<KycCase[]>("/kyc/cases").then(setCases),[]);useEffect(()=>{load().catch(e=>setMessage(e.message))},[load]);
  async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const f=new FormData(form);await api("/kyc/cases",{method:"POST",body:JSON.stringify({subject_type:f.get("subject_type"),subject_id:f.get("subject_id")})});form.reset();setMessage("Verificação iniciada no provedor simulado.");await load()}
  async function decide(id:string,status:string){await api(`/kyc/cases/${id}/mock-decision`,{method:"POST",body:JSON.stringify({status,risk_level:status==="APPROVED"?"LOW":"HIGH",notes:"Decisão registrada no ambiente de desenvolvimento"})});await load()}
  return <><Heading icon={<ShieldCheck/>} eyebrow="COMPLIANCE" title="Central KYC e KYB" text="Esteira auditável de validação de pessoas e empresas, pronta para troca do adaptador simulado por um fornecedor homologado."/>{message&&<div className="notice"><ShieldCheck/>{message}</div>}<section className="panel"><form className="quick-form kyc-form" onSubmit={create}><select name="subject_type"><option value="PERSON">Pessoa física</option><option value="BUSINESS">Pessoa jurídica</option></select><input name="subject_id" placeholder="ID interno do cliente/empresa" required/><button><Plus/>Iniciar verificação</button></form><div className="table-wrap"><table className="data-table"><thead><tr><th>Objeto</th><th>Provedor</th><th>Risco</th><th>Status</th><th>Revisão</th></tr></thead><tbody>{cases.map(c=><tr key={c.id}><td><b>{c.subject_type}</b><small>{c.subject_id}</small></td><td>{c.provider}</td><td>{c.risk_level||"Pendente"}</td><td><span className={`pill pill-${c.status.toLowerCase()}`}>{c.status}</span></td><td className="actions-cell">{c.status==="PENDING"&&<><button className="table-action" onClick={()=>decide(c.id,"APPROVED")}>Aprovar</button><button className="table-action" onClick={()=>decide(c.id,"REJECTED")}>Rejeitar</button></>}</td></tr>)}</tbody></table></div></section></>
}

function Heading({icon,eyebrow,title,text}:{icon:React.ReactNode;eyebrow:string;title:string;text:string}){return <div className="page-heading"><div><span className="eyebrow dark">{eyebrow}</span><h1>{title}</h1><p>{text}</p></div><div className="operational-icon">{icon}</div></div>}
