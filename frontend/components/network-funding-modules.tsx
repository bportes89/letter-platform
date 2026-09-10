"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { BadgeDollarSign, GitBranch, Landmark, LockKeyhole, Plus, ShieldCheck, WalletCards } from "lucide-react";
import { CurrencyFormField } from "@/components/currency-input";
import { api, CommissionEntry, CommissionRule, FundingOpportunity, InvestmentPosition, InvestmentReservation, Invitation, NetworkDownlineMember, NetworkNode, NetworkSummary, MutuoContract, RentabilityCredit, User } from "@/lib/api";

const brl=new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"});
const PARTNER_ROLES=["MASTER_FRANCHISEE","MANAGER","PARTNER","QUOTA_SELLER"];
const OVERSIGHT_ROLES=["MASTER_FRANCHISEE","MANAGER"];
const INVITE_ROLES: Record<string, string[]> = {
  MASTER_FRANCHISEE: ["MANAGER", "PARTNER", "QUOTA_SELLER"],
  MANAGER: ["PARTNER", "QUOTA_SELLER"],
  PARTNER: ["PARTNER", "QUOTA_SELLER"],
  QUOTA_SELLER: ["QUOTA_SELLER"],
};
const ROLE_LABELS: Record<string, string> = {
  MASTER_FRANCHISEE: "Master franqueado",
  MANAGER: "Gerente",
  PARTNER: "Parceiro",
  QUOTA_SELLER: "Vendedor de cotas",
};
const date = (value:string|null) => value ? new Date(value).toLocaleString("pt-BR") : "—";

export function NetworkModule(){
  const [users,setUsers]=useState<User[]>([]),[nodes,setNodes]=useState<NetworkNode[]>([]),[rules,setRules]=useState<CommissionRule[]>([]),[wallet,setWallet]=useState<CommissionEntry[]>([]),[invites,setInvites]=useState<Invitation[]>([]),[downline,setDownline]=useState<NetworkDownlineMember[]>([]),[myRole,setMyRole]=useState(""),[message,setMessage]=useState(""),[canAdmin,setCanAdmin]=useState(false),[canInvite,setCanInvite]=useState(false),[canOversight,setCanOversight]=useState(false),[summary,setSummary]=useState<NetworkSummary|null>(null),[sefaz,setSefaz]=useState<{enabled:boolean;provider:string;mode:string;message:string}|null>(null),[fiscalFormKey,setFiscalFormKey]=useState(0);
  const inviteRoles=INVITE_ROLES[myRole]??PARTNER_ROLES;
  const load=useCallback(async()=>{const me=await api<User>("/auth/me");setMyRole(me.role);const admin=me.role==="PLATFORM_ADMIN";const inviteEnabled=PARTNER_ROLES.includes(me.role);const oversight=OVERSIGHT_ROLES.includes(me.role);setCanAdmin(admin);setCanInvite(inviteEnabled);setCanOversight(oversight);const [r,w,s,sefazStatus]=await Promise.all([api<CommissionRule[]>("/commission-rules"),api<CommissionEntry[]>("/wallet/commissions"),api<NetworkSummary>("/network/me/summary"),api<{enabled:boolean;provider:string;mode:string;message:string}>("/wallet/commissions/sefaz/status")]);setRules(r);setWallet(w);setSummary(s);setSefaz(sefazStatus);if(admin){const [u,n]=await Promise.all([api<User[]>("/admin/users"),api<NetworkNode[]>("/network/nodes?tree_type=SALES")]);setUsers(u);setNodes(n);setDownline([])}else if(inviteEnabled){const inviteList=await api<Invitation[]>("/network/invitations");setInvites(inviteList);if(oversight){setDownline(await api<NetworkDownlineMember[]>("/network/me/downline"))}else{setDownline([])}}else{setDownline([])}},[]);useEffect(()=>{load().catch(e=>setMessage(e.message))},[load]);
  async function node(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=new FormData(e.currentTarget);await api("/network/nodes",{method:"POST",body:JSON.stringify({user_id:f.get("user_id"),sponsor_user_id:f.get("sponsor_user_id")||null,tree_type:"SALES"})});setMessage("Participante incluído na árvore comercial.");await load()}
  async function invitePartner(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const f=new FormData(form);const item=await api<Invitation>("/network/invitations",{method:"POST",body:JSON.stringify({email:f.get("email"),role:f.get("role")})});form.reset();const link=typeof window!=="undefined"&&item.token?`${window.location.origin}/convite?token=${encodeURIComponent(item.token)}`:null;setMessage(link?`Convite enviado para ${item.email}. Link de aceite: ${link}`:`Convite enviado para ${item.email}.`);await load()}
  async function rule(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=new FormData(e.currentTarget);await api("/commission-rules",{method:"POST",body:JSON.stringify({product:f.get("product"),commission_type:"SALES",pool_rate_percent:f.get("pool_rate_percent"),base_type:"NET_PAYOUT"})});setMessage("Nova versão da matriz de comissão ativada.");await load()}
  async function allocate(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=new FormData(e.currentTarget);const entries=await api<CommissionEntry[]>("/commissions/allocate",{method:"POST",body:JSON.stringify({originator_id:f.get("originator_id"),reference:f.get("reference"),product:f.get("product"),commission_type:"SALES",calculation_base:f.get("calculation_base")})});setMessage(`${entries.length} níveis provisionados em Hold Fiscal.`);await load()}
  async function fiscal(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=new FormData(e.currentTarget);const accessKey=String(f.get("access_key")||"").trim();const grossAmount=String(f.get("gross_amount")||"").trim();const body:Record<string,string>={reference_month:String(f.get("reference_month")),document_content:String(f.get("document_content"))};if(accessKey)body.access_key=accessKey;if(grossAmount)body.gross_amount=grossAmount;const result=await api<{available_balance:string;access_key:string;status:string;wallet_credit?:{credited:boolean;amount:string;wallet_balance?:string;message?:string}}>("/wallet/commissions/release-fiscal",{method:"POST",body:JSON.stringify(body)});setMessage(result.wallet_credit?.credited?`SEFAZ ${result.status}: NF-e ${result.access_key} validada. ${result.wallet_credit.message??""} BANK: ${brl.format(Number(result.wallet_credit.wallet_balance??result.wallet_credit.amount))}.`:`SEFAZ ${result.status}: NF-e ${result.access_key} validada. Saldo disponível: ${brl.format(Number(result.available_balance))}.`);e.currentTarget.reset();setFiscalFormKey(k=>k+1);await load()}
  const available=wallet.filter(x=>x.status==="AVAILABLE").reduce((s,x)=>s+Number(x.amount),0),held=wallet.filter(x=>x.status==="PENDING_FISCAL").reduce((s,x)=>s+Number(x.amount),0),credited=wallet.filter(x=>x.status==="CREDITED_TO_WALLET").reduce((s,x)=>s+Number(x.amount),0);
  const nfSample='<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><chNFe>35250801234567890123456789012345678901234567</chNFe><xNome>Parceiro Demonstracao</xNome></NFe>';
  return <><Heading title="Rede e comissões" text={canOversight?"Cadastre sua equipe, acompanhe parceiros da rede e visualize propostas e pendências da sua downline.":"Árvore comercial auditável, cinco níveis de split, regras versionadas e comissões com hold fiscal."} icon={<GitBranch/>}/>{message&&<div className="notice"><ShieldCheck/>{message}</div>}{sefaz&&<div className="notice"><LockKeyhole/>Robô SEFAZ ({sefaz.mode} · {sefaz.provider}){sefaz.enabled?"":" — INATIVO"}: {sefaz.message}</div>}<div className="network-metrics"><Metric label={canAdmin?"Participantes":canOversight?"Parceiros na rede":"Rede agregada"} value={String(canAdmin?nodes.length:canOversight?downline.length:summary?.total_downline??0)}/>{canOversight&&<Metric label="Propostas pendentes" value={String(summary?.pending_proposals??0)}/>}{canOversight&&<Metric label="Leads em aberto" value={String(summary?.open_leads??0)}/>}<Metric label="Matrizes ativas" value={String(rules.filter(r=>r.active).length)}/><Metric label="Disponível" value={brl.format(available)}/><Metric label="Hold Fiscal" value={brl.format(held)}/></div>{canInvite&&!canAdmin&&<section className="panel"><h2><GitBranch/>Convidar para a rede</h2><p style={{marginTop:0,color:"var(--muted)",fontSize:"0.875rem"}}>{canOversight?"Cadastre gerentes e parceiros sob sua responsabilidade. Contrato digital obrigatório apenas para parceiro e vendedor de cotas.":"Envie convite para parceiro ou vendedor de cotas. Ao aceitar, entra na sua rede comercial."}</p><form className="stack-form" onSubmit={invitePartner}><input name="email" type="email" placeholder="E-mail do convidado" required/><select name="role" required>{inviteRoles.map(r=><option key={r} value={r}>{ROLE_LABELS[r]??r}</option>)}</select><button><Plus/>Gerar convite</button></form></section>}{canInvite&&!canAdmin&&invites.length>0&&<section className="panel identity-table"><h2>Meus convites</h2>{invites.map(i=><div className="session-row" key={i.id}><div><b>{i.email}</b><small>{ROLE_LABELS[i.role]??i.role} · expira {date(i.expires_at)}</small></div><span className={`pill pill-${i.status.toLowerCase()}`}>{i.status}</span></div>)}</section>}{canAdmin?<><div className="admin-grid three"><section className="panel"><h2><GitBranch/>Incluir na árvore</h2><form className="stack-form" onSubmit={node}><select name="user_id">{users.filter(u=>!nodes.some(n=>n.user_id===u.id)).map(u=><option value={u.id} key={u.id}>{u.name}</option>)}</select><select name="sponsor_user_id"><option value="">Raiz</option>{nodes.map(n=><option value={n.user_id} key={n.id}>{users.find(u=>u.id===n.user_id)?.name}</option>)}</select><button><Plus/>Adicionar participante</button></form></section><section className="panel"><h2><BadgeDollarSign/>Matriz de comissão</h2><form className="stack-form" onSubmit={rule}><select name="product"><option>MARKETPLACE</option><option>SDC</option><option>FLASH_CREDIT</option><option>QUITCON</option></select><input name="pool_rate_percent" type="number" step="0.01" placeholder="Verba total (%)" required/><button>Criar nova versão</button></form></section><section className="panel"><h2><WalletCards/>Provisionar split</h2><form className="stack-form" onSubmit={allocate}><select name="originator_id">{nodes.map(n=><option value={n.user_id} key={n.id}>{users.find(u=>u.id===n.user_id)?.name}</option>)}</select><select name="product"><option>MARKETPLACE</option><option>SDC</option><option>FLASH_CREDIT</option><option>QUITCON</option></select><input name="reference" placeholder="Referência única" required/><CurrencyFormField name="calculation_base" placeholder="Base líquida (R$)" required/><button>Calcular cinco níveis</button></form></section></div><section className="panel identity-table"><h2>Árvore comercial</h2>{nodes.map(n=><div className="session-row" key={n.id}><div><b>{users.find(u=>u.id===n.user_id)?.name}</b><small>{n.referral_code} · patrocinador: {users.find(u=>u.id===n.sponsor_user_id)?.name||"Raiz"}</small></div><span className="pill pill-approved">{n.status}</span></div>)}</section></>:canOversight?<section className="panel identity-table"><h2>Parceiros sob sua responsabilidade</h2><p style={{marginTop:0,color:"var(--muted)",fontSize:"0.875rem"}}>Propostas e leads dos parceiros abaixo aparecem nos módulos CRM e Propostas.</p>{downline.length===0?<p>Nenhum membro cadastrado na sua rede ainda. Use o formulário acima para convidar gerentes ou parceiros.</p>:downline.map(m=><div className="session-row" key={m.user_id}><div><b>{m.name}</b><small>{ROLE_LABELS[m.role]??m.role} · nível {m.level} · {m.email}{m.sponsor_name?` · patrocinador: ${m.sponsor_name}`:""}</small></div><span className="pill pill-approved">{m.status}</span></div>)}</section>:<section className="panel privacy-summary"><h2>Visão agregada da rede</h2><p>Contagem por nível da sua downline comercial. Detalhes de parceiros de outros ramos permanecem protegidos.</p><div>{Object.entries(summary?.levels??{}).map(([level,count])=><span key={level}><b>Nível {level}</b>{count} participantes</span>)}</div></section>}<section className="panel fiscal-panel"><div><h2><LockKeyhole/>Liberação fiscal via SEFAZ</h2><p>Envie o XML da NF-e ou a chave de 44 dígitos. O robô consulta a SEFAZ e credita automaticamente na <strong>BANK</strong> do parceiro se a nota estiver autorizada.</p></div><form key={fiscalFormKey} className="stack-form" onSubmit={fiscal}><input name="reference_month" type="month" required/><input name="access_key" placeholder="Chave NF-e (44 dígitos, opcional se estiver no XML)" maxLength={44}/><CurrencyFormField name="gross_amount" placeholder="Valor bruto da NF (R$, opcional)"/><textarea name="document_content" defaultValue={nfSample} required rows={5}/><button>Validar na SEFAZ e liberar</button></form></section></>
}

export function FundingModule(){
  const [items,setItems]=useState<FundingOpportunity[]>([]);
  const [reservations,setReservations]=useState<InvestmentReservation[]>([]);
  const [positions,setPositions]=useState<InvestmentPosition[]>([]);
  const [credits,setCredits]=useState<RentabilityCredit[]>([]);
  const [mutuos,setMutuos]=useState<MutuoContract[]>([]);
  const [users,setUsers]=useState<User[]>([]);
  const [message,setMessage]=useState("");
  const [canAdmin,setCanAdmin]=useState(false);
  const [formKey,setFormKey]=useState(0);
  const [reserveAmount,setReserveAmount]=useState<Record<string,string>>({});
  const load=useCallback(()=>Promise.all([
    api<User>("/auth/me"),
    api<FundingOpportunity[]>("/funding/opportunities"),
    api<InvestmentReservation[]>("/funding/reservations"),
    api<InvestmentPosition[]>("/funding/positions"),
    api<RentabilityCredit[]>("/funding/rentability-credits").catch(()=>[] as RentabilityCredit[]),
    api<MutuoContract[]>("/funding/mutuo/contracts").catch(()=>[] as MutuoContract[]),
  ]).then(async ([me,o,r,p,c,m])=>{
    setCanAdmin(me.role==="PLATFORM_ADMIN"||me.role==="INTERNAL_STAFF");
    setItems(o);setReservations(r);setPositions(p);setCredits(c);setMutuos(m);
    if(me.role==="PLATFORM_ADMIN"||me.role==="INTERNAL_STAFF"){
      try{setUsers(await api<User[]>("/admin/users"));}catch{setUsers([]);}
    }
  }),[]);
  useEffect(()=>{load().catch(e=>setMessage(e.message));},[load]);

  async function create(e:FormEvent<HTMLFormElement>){
    e.preventDefault();
    const form=e.currentTarget;const f=new FormData(form);
    await api("/funding/opportunities",{method:"POST",body:JSON.stringify({
      title:f.get("title"),
      product:f.get("product"),
      capital_source:f.get("capital_source"),
      instrument_type:f.get("instrument_type"),
      target_amount:f.get("target_amount"),
      min_investment:f.get("min_investment")||null,
      token_unit_price:f.get("token_unit_price")||"100",
      property_ref:f.get("property_ref")||null,
      annual_return_reference:f.get("annual_return_reference")||null,
    })});
    form.reset();setFormKey(k=>k+1);setMessage("Captacao publicada (tokens a partir de R$ 100; mutuo a partir de R$ 10.000).");await load();
  }
  async function linkProperty(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const f=new FormData(e.currentTarget);
    const id=String(f.get("opportunity_id")||"");
    await api(`/funding/opportunities/${id}/property`,{method:"PATCH",body:JSON.stringify({property_ref:f.get("property_ref")||null})});
    setMessage("Imovel/matricula vinculado a captacao.");await load();
  }
  async function reserve(id:string, fallbackMin:string){
    try{
      const amount=reserveAmount[id]||fallbackMin;
      await api(`/funding/opportunities/${id}/reserve`,{method:"POST",body:JSON.stringify({amount})});
      setMessage("Reserva criada. Aguarde a confirmacao do backoffice.");await load();
    }catch(err){setMessage(err instanceof Error?err.message:"Perfil nao habilitado");}
  }
  async function confirm(id:string){await api(`/funding/reservations/${id}/mock-confirm`,{method:"POST"});setMessage("Aporte confirmado e posicao criada.");await load();}
  async function manualInvest(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const form=e.currentTarget;const f=new FormData(form);
    await api("/funding/manual-investments",{method:"POST",body:JSON.stringify({
      opportunity_id:f.get("opportunity_id"),
      investor_id:f.get("investor_id"),
      amount:f.get("amount"),
      instrument_type:f.get("instrument_type")||null,
      property_ref:f.get("property_ref")||null,
      notes:f.get("notes")||null,
    })});
    form.reset();setMessage("Investimento lancado manualmente.");await load();
  }
  async function manualRent(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const form=e.currentTarget;const f=new FormData(form);
    await api("/funding/manual-rentability",{method:"POST",body:JSON.stringify({
      position_id:f.get("position_id"),
      amount:f.get("amount"),
      reference_month:f.get("reference_month"),
      notes:f.get("notes")||null,
    })});
    form.reset();setMessage("Rentabilidade lancada manualmente.");await load();
  }

  async function createMutuo(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const form=e.currentTarget;const f=new FormData(form);
    await api("/funding/mutuo/contracts",{method:"POST",body:JSON.stringify({
      principal:f.get("principal"),
      settlement_option:f.get("settlement_option"),
      opportunity_id:f.get("opportunity_id")||null,
      locality:f.get("locality")||null,
    })});
    form.reset();setMessage("Contrato de mutuo criado. Aceite e assine para seguir.");await load();
  }
  async function mutuoAction(id:string, path:string, body?:Record<string,unknown>, ok?:string){
    await api(`/funding/mutuo/contracts/${id}/${path}`,{method:"POST",body:JSON.stringify(body??{})});
    setMessage(ok||"Etapa do mutuo atualizada.");await load();
  }

  const total=useMemo(()=>positions.reduce((s,p)=>s+Number(p.principal),0),[positions]);
  const investors=users.filter(u=>["RETAIL_INVESTOR","INSTITUTIONAL_FUND","CLIENT","PLATFORM_ADMIN"].includes(u.role));

  return <>
    <Heading title="Flash Invest" text="Captacao via tokens (a partir de R$ 100). A partir de R$ 10.000 tambem pode usar mutuo financeiro. Imovel vinculado manualmente; investimento e rentabilidade podem ser lancados a mao." icon={<Landmark/>}/>
    {message&&<div className="notice"><ShieldCheck/>{message}</div>}
    <div className="network-metrics">
      <Metric label="Captacoes" value={String(items.length)}/>
      <Metric label="Reservas" value={String(reservations.length)}/>
      <Metric label="Posicoes" value={String(positions.length)}/>
      <Metric label="Capital confirmado" value={brl.format(total)}/>
    </div>

    <section className="panel">
      {canAdmin&&(
        <form key={formKey} className="quick-form funding-form" onSubmit={e=>void create(e).catch(err=>setMessage(err.message))}>
          <input name="title" placeholder="Titulo da captacao" required/>
          <select name="product"><option>FLASH_INVEST</option><option>SDC</option><option>FLASH_CREDIT</option><option>QUITCON</option></select>
          <select name="capital_source"><option value="RETAIL">Varejo</option><option value="INSTITUTIONAL">Institucional</option></select>
          <select name="instrument_type"><option value="TOKEN">Token (min. R$ 100)</option><option value="MUTUO">Mutuo (&gt;= R$ 10.000)</option></select>
          <CurrencyFormField name="target_amount" placeholder="Meta (R$)" required/>
          <CurrencyFormField name="min_investment" placeholder="Minimo (opcional)"/>
          <input name="token_unit_price" type="number" step="0.01" defaultValue={100} placeholder="Face do token"/>
          <input name="property_ref" placeholder="Imovel / matricula (manual)"/>
          <input name="annual_return_reference" type="number" step="0.01" placeholder="Retorno ref. a.a. (opc.)"/>
          <button><Plus/>Publicar captacao</button>
        </form>
      )}
      <div className="funding-grid">{items.map(x=>{
        const pct=Math.min(100,Number(x.funded_amount)/Number(x.target_amount)*100);
        const unit=Number(x.token_unit_price||100);
        return <article className="funding-card" key={x.id}>
          <div>
            <span className={`pill pill-${x.status.toLowerCase()}`}>{x.status}</span>
            <small>{x.instrument_type||"TOKEN"} · {x.product} · {x.capital_source}</small>
          </div>
          <h3>{x.title}</h3>
          <strong>{brl.format(Number(x.target_amount))}</strong>
          <div className="funding-progress"><i style={{width:`${pct}%`}}/></div>
          <small>{brl.format(Number(x.funded_amount))} confirmado · min. {brl.format(Number(x.min_investment))}{(x.instrument_type||"TOKEN")==="TOKEN"?` · token ${brl.format(unit)}`:""}</small>
          {x.property_ref?<small>Imovel: {x.property_ref}</small>:<small>Imovel ainda nao vinculado</small>}
          {!canAdmin&&x.status==="OPEN"&&(
            <div style={{display:"grid",gap:8,marginTop:8}}>
              <input type="number" min="100" step="100" placeholder="Valor do aporte (R$)" value={reserveAmount[x.id]||""} onChange={ev=>setReserveAmount(s=>({...s,[x.id]:ev.target.value}))}/>
              <button type="button" onClick={()=>void reserve(x.id,x.min_investment)}>Reservar aporte</button>
            </div>
          )}
        </article>;
      })}</div>
    </section>

    {canAdmin&&(
      <div className="admin-grid three">
        <section className="panel">
          <h2>Vincular imovel (manual)</h2>
          <form className="stack-form" onSubmit={e=>void linkProperty(e).catch(err=>setMessage(err.message))}>
            <select name="opportunity_id" required>
              <option value="">Captacao</option>
              {items.map(o=><option key={o.id} value={o.id}>{o.title}</option>)}
            </select>
            <input name="property_ref" placeholder="Matricula / endereco / ref. do imovel" required/>
            <button>Salvar vinculo</button>
          </form>
        </section>
        <section className="panel">
          <h2>Lancar investimento manual</h2>
          <form className="stack-form" onSubmit={e=>void manualInvest(e).catch(err=>setMessage(err.message))}>
            <select name="opportunity_id" required>
              <option value="">Captacao</option>
              {items.map(o=><option key={o.id} value={o.id}>{o.title} · {o.instrument_type||"TOKEN"}</option>)}
            </select>
            <select name="investor_id" required>
              <option value="">Investidor</option>
              {investors.map(u=><option key={u.id} value={u.id}>{u.name} · {u.email}</option>)}
            </select>
            <CurrencyFormField name="amount" placeholder="Valor (R$)" required/>
            <select name="instrument_type">
              <option value="">Herdar da captacao</option>
              <option value="TOKEN">TOKEN</option>
              <option value="MUTUO">MUTUO</option>
            </select>
            <input name="property_ref" placeholder="Imovel (opcional)"/>
            <input name="notes" placeholder="Observacao"/>
            <button>Lancar investimento</button>
          </form>
        </section>
        <section className="panel">
          <h2>Lancar rentabilidade manual</h2>
          <form className="stack-form" onSubmit={e=>void manualRent(e).catch(err=>setMessage(err.message))}>
            <select name="position_id" required>
              <option value="">Posicao</option>
              {positions.map(p=>{
                const opp=items.find(o=>o.id===p.opportunity_id);
                return <option key={p.id} value={p.id}>{opp?.title||p.opportunity_id} · {brl.format(Number(p.principal))}</option>;
              })}
            </select>
            <CurrencyFormField name="amount" placeholder="Rentabilidade (R$)" required/>
            <input name="reference_month" type="month" required/>
            <input name="notes" placeholder="Motivo / observacao"/>
            <button>Lancar rentabilidade</button>
          </form>
        </section>
      </div>
    )}

    <section className="panel identity-table">
      <h2>Reservas</h2>
      {reservations.map(r=><div className="session-row" key={r.id}>
        <div><b>{brl.format(Number(r.amount))}</b><small>{items.find(x=>x.id===r.opportunity_id)?.title} · {r.instrument_type||"TOKEN"}</small></div>
        <div className="actions-cell">
          <span className={`pill pill-${r.status.toLowerCase()}`}>{r.status}</span>
          {canAdmin&&r.status==="RESERVED"&&<button className="table-action" onClick={()=>void confirm(r.id)}>Confirmar</button>}
        </div>
      </div>)}
    </section>

    <section className="panel identity-table">
      <h2>Posicoes</h2>
      {positions.length===0?<p className="muted">Nenhuma posicao ainda.</p>:positions.map(p=><div className="session-row" key={p.id}>
        <div>
          <b>{brl.format(Number(p.principal))}</b>
          <small>
            {items.find(x=>x.id===p.opportunity_id)?.title} · {p.instrument_type||"TOKEN"} · {p.source||"PLATFORM"}
            {p.tokens_qty!=null?` · ${p.tokens_qty} tokens`:""}
            {p.property_ref?` · imovel ${p.property_ref}`:""}
          </small>
          <small>Rentabilidade acumulada: {brl.format(Number(p.accrued_return))}</small>
        </div>
        <span className={`pill pill-${p.status.toLowerCase()}`}>{p.status}</span>
      </div>)}
    </section>

    <section className="panel">
      <h2>Mutuo financeiro (&gt;= R$ 10.000)</h2>
      <p className="muted" style={{marginTop:0}}>
        Na contratacao escolha Opcao A (1,6% a.m. na Wallet) ou Opcao B (bullet com juros simples 1,6% a.m. no final dos 36 meses).
        No vencimento o resgate e obrigatorio. Se a LETTER nao devolver apos o pedido de resgate, libera conversao em equity.
      </p>
      <form className="stack-form" onSubmit={(e)=>void createMutuo(e).catch(err=>setMessage(err.message))} style={{marginBottom:16}}>
        <CurrencyFormField name="principal" placeholder="Aporte (R$ >= 10.000)" required/>
        <select name="settlement_option" required>
          <option value="A">Opcao A — juros mensais 1,6% na Wallet</option>
          <option value="B">Opcao B — bullet juros simples no final</option>
        </select>
        <select name="opportunity_id">
          <option value="">Captacao (opcional)</option>
          {items.map(o=><option key={o.id} value={o.id}>{o.title} · {o.instrument_type||"TOKEN"}</option>)}
        </select>
        <input name="locality" placeholder="Localidade (padrao Teixeira de Freitas/BA)"/>
        <button type="submit"><Plus/>Contratar mutuo</button>
      </form>
      {mutuos.length===0?<p className="muted">Nenhum contrato de mutuo ainda.</p>:mutuos.map(c=><div className="session-row" key={c.id} style={{alignItems:"flex-start"}}>
        <div>
          <b>{brl.format(Number(c.principal))} · {c.settlement_option_label||c.settlement_option}</b>
          <small>Status: {c.status} · meses juros: {c.interest_months_posted}/36</small>
          <small>Pago A: {brl.format(Number(c.paid_interest_total))} · Acumulado B: {brl.format(Number(c.accrued_interest))}</small>
          <small>Vencimento: {c.maturity_at?new Date(c.maturity_at).toLocaleDateString("pt-BR"):"—"} · devido no resgate: {c.redemption_due_amount?brl.format(Number(c.redemption_due_amount)): "—"}</small>
          {c.signature_url&&<small><a href={c.signature_url} target="_blank" rel="noreferrer">Abrir assinatura ZapSign</a></small>}
        </div>
        <div className="actions-cell" style={{display:"flex",flexDirection:"column",gap:6}}>
          <span className={`pill pill-${c.status.toLowerCase()}`}>{c.status}</span>
          {(c.status==="DRAFT"||c.status==="AWAITING_SIGNATURE")&&<>
            <button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"accept-sign",{accepted:true},"Aceite registrado · assinatura enviada.").catch(err=>setMessage(err.message))}>Aceitar + assinar</button>
            {c.status==="AWAITING_SIGNATURE"&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"mock-complete-signature",{},"Assinatura concluida.").catch(err=>setMessage(err.message))}>Concluir assinatura</button>}
          </>}
          {canAdmin&&c.status==="SIGNED"&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"settle",{},"Aporte liquidado · contrato ACTIVE.").catch(err=>setMessage(err.message))}>Liquidar aporte</button>}
          {canAdmin&&c.status==="ACTIVE"&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"post-interest",{},"Juros do mes lancados.").catch(err=>setMessage(err.message))}>Lancar juros do mes</button>}
          {canAdmin&&c.status==="ACTIVE"&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"admin-accelerate-maturity",{},"Vencimento antecipado para teste de resgate.").catch(err=>setMessage(err.message))}>Homologar vencimento</button>}
          {c.status==="ACTIVE"&&c.maturity_reached&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"request-redemption",{},"Resgate obrigatorio solicitado.").catch(err=>setMessage(err.message))}>Solicitar resgate</button>}
          {canAdmin&&c.status==="REDEMPTION_REQUESTED"&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"confirm-redemption",{},"Resgate pago.").catch(err=>setMessage(err.message))}>Confirmar devolucao</button>}
          {c.equity_conversion_ready&&<button className="table-action" type="button" onClick={()=>void mutuoAction(c.id,"request-equity-conversion",{},"Conversao em equity registrada.").catch(err=>setMessage(err.message))}>Converter em equity</button>}
        </div>
      </div>)}
    </section>

    {credits.length>0&&<section className="panel identity-table">
      <h2>Rentabilidades lancadas</h2>
      {credits.map(c=><div className="session-row" key={c.id}>
        <div><b>{brl.format(Number(c.amount))}</b><small>{c.reference_month} · {c.source}{c.notes?` · ${c.notes}`:""}</small></div>
        <span className={`pill pill-${c.status.toLowerCase()}`}>{c.status}</span>
      </div>)}
    </section>}
  </>;
}


function Heading({title,text,icon}:{title:string;text:string;icon:React.ReactNode}){return <div className="page-heading"><div><span className="eyebrow dark">ECOSSISTEMA LETTER</span><h1>{title}</h1><p>{text}</p></div><div className="operational-icon">{icon}</div></div>}
function Metric({label,value}:{label:string;value:string}){return <article><small>{label}</small><strong>{value}</strong></article>}
