"use client";

import { Check, CheckCircle2, Clock3, Download, FileText, LockKeyhole, Plus, RefreshCw, Search, Unlock, Users, WalletCards, XCircle } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Administrator, api, Calculation, CommercialClient, Contract, downloadApi, Lead, Proposal, Quota, Reservation, User } from "@/lib/api";
import { FLASH_CAPITAL_SOURCES, productLabel, SDC_CAPITAL_SOURCES } from "@/lib/products";
import { SdcQuitConProjectionTable } from "@/components/sdc-quitcon-card";
import { CurrencyInput, CurrencyFormField } from "@/components/currency-input";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function LeadsModule() {
  const [items,setItems]=useState<Lead[]>([]); const [error,setError]=useState(""); const [highlightId,setHighlightId]=useState<string|null>(null);
  const load=()=>api<Lead[]>("/leads").then(setItems).catch(e=>setError(e.message));
  useEffect(()=>{void load(); if(typeof window!=="undefined"){const id=new URLSearchParams(window.location.search).get("lead_id"); if(id)setHighlightId(id)}},[]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await api("/leads",{method:"POST",body:JSON.stringify({name:fd.get("name"),phone:fd.get("phone"),product_interest:fd.get("product_interest"),source:"DASHBOARD"})});form.reset();load()}
  async function advance(lead:Lead){const next:Record<string,string>={NEW:"CONTACTED",CONTACTED:"QUALIFIED",QUALIFIED:"PROPOSAL",PROPOSAL:"CONVERTED"};await api(`/leads/${lead.id}`,{method:"PATCH",body:JSON.stringify({status:next[lead.status]??"QUALIFIED"})});load()}
  return <OperationalLayout title="CRM e originação" subtitle="Cadastre leads e avance a jornada comercial com histórico auditável." icon={<Users/>}>
    <form className="quick-form" onSubmit={submit}><input name="name" placeholder="Nome do cliente" required minLength={2}/><input name="phone" placeholder="WhatsApp" required minLength={8}/><select name="product_interest"><option value="MARKETPLACE">Marketplace</option><option value="SDC">SDC</option><option value="FLASH_CREDIT">Flash Capital</option></select><button><Plus/>Adicionar lead</button></form>
    {error&&<div className="error">{error}</div>}<DataTable headers={["Cliente","Contato","Interesse","SCR/Bacen","Status","Ação"]}>{items.map(x=><tr key={x.id} style={highlightId===x.id?{background:"#f2faf6"}:undefined}><td><b>{x.name}</b><small>{x.source}</small></td><td>{x.phone}</td><td>{productLabel(x.product_interest)}</td><td><small>{x.scr_reference ?? "—"}</small><br/><span className="pill">{x.scr_status ?? "PENDENTE"}</span></td><td><Pill value={x.status}/></td><td><button className="table-action" onClick={()=>advance(x)}>Avançar</button></td></tr>)}</DataTable>
  </OperationalLayout>
}

export function InventoryModule() {
  const [items,setItems]=useState<Quota[]>([]);const [admins,setAdmins]=useState<Administrator[]>([]);const [reservations,setReservations]=useState<Reservation[]>([]);const [suppliers,setSuppliers]=useState<{source_key:string;name:string;markup_percent:string}[]>([]);const [error,setError]=useState("");const [notice,setNotice]=useState("");const [formKey,setFormKey]=useState(0);
  const load=()=>Promise.all([api<Quota[]>("/quotas"),api<Administrator[]>("/administrators"),api<Reservation[]>("/reservations"),api<{source_key:string;name:string;markup_percent:string;active:boolean}[]>("/marketplace/suppliers?active_only=true").catch(()=>[])]).then(([q,a,r,s])=>{setItems(q);setAdmins(a);setReservations(r);setSuppliers(s.filter(x=>x.active!==false))}).catch(e=>setError(e.message));useEffect(()=>{void load()},[]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await api("/quotas",{method:"POST",body:JSON.stringify({administrator_id:fd.get("administrator_id"),group_code:fd.get("group_code"),quota_code:fd.get("quota_code"),category:fd.get("category"),credit_value:fd.get("credit_value"),outstanding_balance:fd.get("outstanding_balance")||"0",premium_value:fd.get("premium_value")||"0",installment_value:fd.get("installment_value")||"0",installment_due_date:fd.get("installment_due_date")||null,remaining_installments:fd.get("remaining_installments")?Number(fd.get("remaining_installments")):null,supplier_source:fd.get("supplier_source")||null})});form.reset();setFormKey(k=>k+1);setNotice("Cota cadastrada no inventário.");load()}
  async function ninaScan(quota:Quota){setError("");try{const result=await api<{message:string}>("/quotas/"+quota.id+"/nina-scan",{method:"POST"});setNotice(result.message);load()}catch(e){setError(e instanceof Error?e.message:"Varredura Nina reprovada.")}}
  async function reserve(quota:Quota){setError("");try{await api("/reservations",{method:"POST",body:JSON.stringify({quota_id:quota.id,ttl_minutes:60})});setNotice(`Cota ${quota.group_code}/${quota.quota_code} travada por 60 minutos.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha na trava")}}
  async function release(quota:Quota){const res=reservations.find(r=>r.quota_id===quota.id&&r.status==="ACTIVE");if(res){await api(`/reservations/${res.id}/release`,{method:"POST"});load()}}
  async function approveQuota(quota:Quota){setError("");try{await api(`/marketplace/quotas/${quota.id}/approve`,{method:"POST"});setNotice(`Cota ${quota.group_code}/${quota.quota_code} aprovada — disponível no estoque.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha ao aprovar cota")}}
  async function rejectQuota(quota:Quota){const reason=window.prompt("Motivo da recusa (compliance):");if(!reason)return;setError("");try{await api(`/marketplace/quotas/${quota.id}/reject`,{method:"POST",body:JSON.stringify({reason})});setNotice(`Cota ${quota.group_code}/${quota.quota_code} recusada.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha ao recusar cota")}}
  async function downloadQuotaStatement(quota:Quota){try{await downloadApi(`/marketplace/quotas/${quota.id}/statement`,quota.statement_filename||`extrato-${quota.group_code}-${quota.quota_code}.pdf`)}catch(e){setError(e instanceof Error?e.message:"Extrato indisponível")}}
  const pendingSupplier=items.filter(x=>x.status==="PENDING_REVIEW"&&Boolean(x.supplier_source));
  const fmtDate=(value?:string|null)=>value?new Date(value+"T12:00:00").toLocaleDateString("pt-BR"):"—";
  return <OperationalLayout title="Inventário (admin)" subtitle="Cadastro interno de cotas, compliance de fornecedores (extrato), varredura Nina e trava de 60 min." icon={<WalletCards/>}>
    <div className="notice"><Clock3/>Fluxo: <b>1.</b> Fornecedor ou admin cadastra cota + extrato · <b>2.</b> Compliance aprova em Inventário · <b>3.</b> Varredura Nina · <b>4.</b> Trava 60 min · <b>5.</b> Proposta · Ofertas do site em <b>Compliance — Vender cota</b></div>
    {pendingSupplier.length>0&&<div className="notice"><CheckCircle2/>{pendingSupplier.length} cota(s) de fornecedor aguardando compliance (revise o extrato antes de aprovar).</div>}
    <form key={formKey} className="quick-form quota-form" onSubmit={submit}><select name="administrator_id" required>{admins.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select><input name="group_code" placeholder="Grupo" required/><input name="quota_code" placeholder="Cota" required/><select name="category"><option value="REAL_ESTATE">Imóvel</option><option value="VEHICLE">Veículo</option></select><CurrencyFormField name="credit_value" placeholder="Crédito (R$)" required/><CurrencyFormField name="premium_value" placeholder="Entrada/ágio (R$)"/><CurrencyFormField name="installment_value" placeholder="Parcela (R$)"/><CurrencyFormField name="outstanding_balance" placeholder="Saldo devedor (R$)"/><input name="installment_due_date" type="date" placeholder="Vencimento parcela" required title="Vencimento da parcela"/><input name="remaining_installments" type="number" min="0" placeholder="Parcelas restantes"/><select name="supplier_source"><option value="">Fornecedor API</option>{suppliers.length?suppliers.map(s=><option key={s.source_key} value={s.source_key}>{s.name} (+{s.markup_percent}%)</option>):(<><option value="FRAGA">Fraga (+3%)</option><option value="BITTELO">Bittelo (+3%)</option><option value="LANCE">Lance (+3%)</option><option value="UNI_CONTEMPLADOS">Uni Contemplados (+10%)</option><option value="CONTEMPLADO_SP">Contemplado SP (+10%)</option><option value="LUME">Lume (+10%)</option></>)}</select><button><Plus/>Cadastrar cota</button></form>
    {notice&&<div className="notice"><CheckCircle2/>{notice}</div>}{error&&<div className="error">{error}</div>}<DataTable headers={["Identificação","Categoria","Crédito","Parcela","Ágio","Vencimento","Extrato","Nina","Status","Ações"]}>{items.map(x=><tr key={x.id}><td><b>Grupo {x.group_code}</b><small>Cota {x.quota_code}{x.supplier_source?` · ${x.supplier_source}`:""}</small>{x.compliance_rejection_reason?<small style={{color:"#a33"}}>Recusa: {x.compliance_rejection_reason}</small>:null}</td><td>{x.category==="REAL_ESTATE"?"Imóvel":"Veículo"}</td><td>{brl.format(Number(x.credit_value))}</td><td>{brl.format(Number(x.installment_value||0))}</td><td>{brl.format(Number(x.premium_value))}</td><td>{fmtDate(x.installment_due_date)}</td><td>{x.statement_document_id?<button className="table-action" onClick={()=>void downloadQuotaStatement(x)}><Download/>{x.statement_filename||"Baixar"}</button>:<small className="muted">Pendente</small>}</td><td><Pill value={x.nina_scan_status??"PENDENTE"}/></td><td><Pill value={x.status}/></td><td className="actions-cell">{x.status==="PENDING_REVIEW"?<><button className="table-action" onClick={()=>approveQuota(x)} disabled={!x.statement_document_id}><Check/>Aprovar</button><button className="table-action" onClick={()=>rejectQuota(x)}><XCircle/>Recusar</button></>:x.status==="AVAILABLE"?<><button className="table-action" onClick={()=>ninaScan(x)} disabled={!x.installment_due_date}><RefreshCw/>Varredura Nina</button><button className="table-action lock" onClick={()=>reserve(x)} disabled={x.nina_scan_status!=="CLEARED"}><LockKeyhole/>Travar 60 min</button></>:x.status==="RESERVED"?<button className="table-action" onClick={()=>release(x)}><Unlock/>Liberar</button>:x.status==="SOLD"?"Vendida":"—"}</td></tr>)}</DataTable>
  </OperationalLayout>
}

type MarketplaceMatch = {
  quota_ids: string[];
  total_credit: string;
  total_entrada?: string | null;
  deviation_percent: string;
  entrada_deviation_percent?: string | null;
  score: number;
  administrator_id: string;
  administrator_name?: string;
  explanation: string;
  message?: string;
  lane?: string | null;
  rollover_applied?: boolean;
  markup_amount?: string | null;
  remaining_installments?: number | null;
  quotas: {
    quota_id: string;
    group_code: string;
    quota_code: string;
    category: string;
    credit_value: string;
    premium_value: string;
    entrada_final?: string | null;
    installment_value?: string;
    installment_due_date?: string | null;
    remaining_installments?: number | null;
    supplier_source?: string | null;
    markup_percent?: string | null;
    rollover_applied?: boolean;
    administrator_name?: string;
    status: string;
    nina_scan_status?: string | null;
  }[];
};

type MarketplaceEsteira1Result = {
  esteira: string;
  eligible: boolean;
  quota: MarketplaceMatch["quotas"][0];
  blockers: string[];
  alternatives: MarketplaceMatch[];
  message: string;
};

type MarketplaceEsteira2Result = {
  esteira: string;
  eligible: boolean;
  blockers: string[];
  matches: MarketplaceMatch[];
  credit_matches?: MarketplaceMatch[];
  entrada_matches?: MarketplaceMatch[];
  band_percent?: string;
  message: string;
};

const ESTEIRA_SEARCH_BAND = 0.05;

function parseMoney(value: string): number {
  const n = Number(String(value || "").replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function withinSearchBand(actual: number, target: number): boolean {
  if (target <= 0) return true;
  return Math.abs(actual - target) / target <= ESTEIRA_SEARCH_BAND;
}

function quotaEntrada(q: Quota): number {
  return Number(q.entrada_final ?? q.premium_value ?? 0);
}

function quotaCatalogLabel(q: Quota): string {
  const cat = q.category === "REAL_ESTATE" ? "Imóvel" : "Veículo";
  return `${q.group_code} · ${q.quota_code} · ${cat} · crédito ${brl.format(Number(q.credit_value))} · entrada ${brl.format(quotaEntrada(q))} · parc. ${brl.format(Number(q.installment_value || 0))}`;
}

/** Oculta fornecedor/sync na tela comercial de propostas (mesmo quando o usuário é admin). */
function partnerSafeQuotaIdentity(q: Quota): string {
  const gc = (q.group_code || "").trim();
  const qc = (q.quota_code || "").trim();
  const looksSupplier =
    /sync/i.test(gc) ||
    /sync/i.test(qc) ||
    gc.includes("/") ||
    qc.includes("/") ||
    /bradesco|porto|lume|fraga|bittelo|uni_contemplados/i.test(`${gc} ${qc}`);
  if (!looksSupplier && gc === "Letter" && qc.startsWith("Ref ")) return `${gc} · ${qc}`;
  if (!looksSupplier && gc.startsWith("Letter") && !gc.includes("_")) return `${gc} · ${qc}`;
  const ref = q.id.replace(/-/g, "").slice(-6).toUpperCase();
  return `Letter · Ref ${ref}`;
}

function proposalQuotaListLabel(q: Quota): string {
  const cat = q.category === "REAL_ESTATE" ? "Imóvel" : "Veículo";
  const due = q.installment_due_date
    ? ` · venc. ${new Date(q.installment_due_date + "T12:00:00").toLocaleDateString("pt-BR")}`
    : "";
  return `${partnerSafeQuotaIdentity(q)} · ${cat} · ${brl.format(Number(q.credit_value))}${due} · ${q.status}`;
}

function profileValidationMessage(prefix: "e1" | "e2", cat: string, profile: Record<string, string>): string | null {
  if (!parseMoney(profile[`${prefix}_income`])) return "Informe a renda mensal comprovada.";
  if (!parseMoney(profile[`${prefix}_asset`])) return "Informe o valor do bem.";
  if (cat === "VEHICLE" && !String(profile[`${prefix}_year`] || "").trim()) return "Informe o ano do bem (veículo).";
  return null;
}

function ClientProfileFields({prefix,values,flags,onChange,onFlag,category}:{prefix:string;values:Record<string,string>;flags:Record<string,boolean>;onChange:(k:string,v:string)=>void;onFlag:(k:string,v:boolean)=>void;category?:string}) {
  const showYear=category==="VEHICLE";
  return <div className="marketplace-profile-fields">
    <label className="marketplace-field">Renda mensal comprovada (R$)<CurrencyInput value={values[`${prefix}_income`]} onChange={v=>onChange(`${prefix}_income`,v)} required/></label>
    <label className="marketplace-field">Valor do bem (R$)<CurrencyInput value={values[`${prefix}_asset`]} onChange={v=>onChange(`${prefix}_asset`,v)} required/></label>
    {showYear&&<label className="marketplace-field marketplace-field-compact">Ano do bem<input type="number" min="1980" max="2100" value={values[`${prefix}_year`]} onChange={e=>onChange(`${prefix}_year`,e.target.value)} required/></label>}
    <label className="marketplace-field marketplace-field-compact" style={{display:"flex",alignItems:"center",gap:8}}><input type="checkbox" checked={!!flags[`${prefix}_dirty`]} onChange={e=>onFlag(`${prefix}_dirty`,e.target.checked)}/>Restrição SPC/Serasa</label>
    <label className="marketplace-field marketplace-field-compact" style={{display:"flex",alignItems:"center",gap:8}}><input type="checkbox" checked={!!flags[`${prefix}_zero`]} onChange={e=>onFlag(`${prefix}_zero`,e.target.checked)}/>Bem zero km</label>
  </div>;
}

export function MarketplaceModule() {
  const [quotas,setQuotas]=useState<Quota[]>([]);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [tab,setTab]=useState<"esteira1"|"esteira2">("esteira1");
  const [profile,setProfile]=useState({e1_income:"",e1_asset:"",e1_year:"",e2_income:"",e2_asset:"",e2_year:""});
  const [flags,setFlags]=useState({e1_dirty:false,e1_zero:false,e2_dirty:false,e2_zero:false});
  const [selectedQuota,setSelectedQuota]=useState("");
  const [e1Category,setE1Category]=useState<"REAL_ESTATE"|"VEHICLE">("REAL_ESTATE");
  const [e1FilterCredit,setE1FilterCredit]=useState("");
  const [e1FilterEntrada,setE1FilterEntrada]=useState("");
  const [targetAmount,setTargetAmount]=useState("");
  const [targetEntrada,setTargetEntrada]=useState("");
  const [category,setCategory]=useState("REAL_ESTATE");
  const [result1,setResult1]=useState<MarketplaceEsteira1Result|null>(null);
  const [result2,setResult2]=useState<MarketplaceEsteira2Result|null>(null);
  const load=()=>api<Quota[]>("/quotas").then(setQuotas).catch(e=>setError(e.message));
  useEffect(()=>{void load()},[]);
  const available=useMemo(()=>quotas.filter(q=>q.status==="AVAILABLE"||q.status==="RESERVED"),[quotas]);
  const e1Catalog=useMemo(()=>{
    const creditTarget=parseMoney(e1FilterCredit);
    const entradaTarget=parseMoney(e1FilterEntrada);
    return available
      .filter(q=>q.category===e1Category)
      .filter(q=>{
        const credit=Number(q.credit_value);
        const entrada=quotaEntrada(q);
        return withinSearchBand(credit,creditTarget)&&withinSearchBand(entrada,entradaTarget);
      })
      .sort((a,b)=>Number(a.credit_value)-Number(b.credit_value));
  },[available,e1Category,e1FilterCredit,e1FilterEntrada]);
  const profilePayload=(prefix:"e1"|"e2",cat:string)=>{
    const year=profile[`${prefix}_year`];
    const assetYear=cat==="VEHICLE"&&year?Number(year):new Date().getFullYear();
    return {
      monthly_income:String(parseMoney(profile[`${prefix}_income`])),
      asset_value:String(parseMoney(profile[`${prefix}_asset`])),
      asset_year:assetYear,
      has_credit_restriction:flags[`${prefix}_dirty`],
      asset_is_zero_km:flags[`${prefix}_zero`],
    };
  };
  async function assessEsteira1(e:FormEvent){e.preventDefault();setError("");setNotice("");const validation=profileValidationMessage("e1",e1Category,profile);if(validation){setError(validation);return}if(!selectedQuota){setError("Selecione uma carta na lista.");return}try{const data=await api<MarketplaceEsteira1Result>("/marketplace/esteira-1/assess",{method:"POST",body:JSON.stringify({quota_id:selectedQuota,...profilePayload("e1",e1Category)})});setResult1(data);setNotice(data.message)}catch(err){setError(err instanceof Error?err.message:"Falha na Esteira 1")}}
  async function matchEsteira2(e:FormEvent){e.preventDefault();setError("");setNotice("");const validation=profileValidationMessage("e2",category,profile);if(validation){setError(validation);return}if(!parseMoney(targetAmount)){setError("Informe o crédito desejado.");return}if(!parseMoney(targetEntrada)){setError("Informe a entrada desejada.");return}try{const data=await api<MarketplaceEsteira2Result>("/marketplace/esteira-2/match",{method:"POST",body:JSON.stringify({target_amount:String(parseMoney(targetAmount)),target_entrada:String(parseMoney(targetEntrada)),category,...profilePayload("e2",category)})});setResult2(data);setNotice(data.message)}catch(err){setError(err instanceof Error?err.message:"Falha na Esteira 2")}}
  async function reserveQuota(quotaId:string){setError("");try{await api("/reservations",{method:"POST",body:JSON.stringify({quota_id:quotaId,ttl_minutes:60})});setNotice("Cota travada por 60 minutos. Prossiga em Propostas.");load()}catch(err){setError(err instanceof Error?err.message:"Falha na trava")}}
  function MatchCard({match,onReserve}:{match:MarketplaceMatch;onReserve:(id:string)=>void}) {
    return <article className="backlog-item"><div><strong>{match.administrator_name??"Administradora"} · crédito {brl.format(Number(match.total_credit))}{match.total_entrada?` · entrada ${brl.format(Number(match.total_entrada))}`:""}</strong><p>{match.explanation}{match.message?` — ${match.message}`:""}</p><small>Lane {match.lane??"—"} · Score {match.score} · Desvio crédito {match.deviation_percent}%{match.entrada_deviation_percent!=null?` · Desvio entrada ${match.entrada_deviation_percent}%`:""}{match.rollover_applied?" · Rollover 7d":""}</small><div>{match.quotas.map(q=><label key={q.quota_id} style={{display:"block",marginTop:"0.5rem"}}><span>{q.group_code} · {q.quota_code} · crédito {brl.format(Number(q.credit_value))} · entrada {brl.format(Number(q.entrada_final??q.premium_value))} · parcela {brl.format(Number(q.installment_value||0))}{q.rollover_applied?" · rollover":""} · Nina {q.nina_scan_status??"PENDENTE"}</span>{q.status==="AVAILABLE"&&q.nina_scan_status==="CLEARED"?<button type="button" className="table-action lock" style={{marginLeft:"0.75rem"}} onClick={()=>onReserve(q.quota_id)}><LockKeyhole/>Travar 60 min</button>:null}</label>)}</div></div></article>;
  }
  return <OperationalLayout title="Marketplace — Cartas contempladas" subtitle="Esteira 2 (robô): 1 opção na banda de 5% para crédito e 1 para entrada, rollover 7 dias e markup do fornecedor. Regras Bacen via approval_rules sincronizadas." icon={<WalletCards/>}>
    <div className="notice"><Clock3/>Admin cadastra cotas (fornecedor + prazo restante) em <b>Inventário</b>. Sync Bacen em <b>Administradoras</b> alimenta approval_rules usadas no matching. Finalize a venda em <b>Propostas</b>.</div>
    <div className="marketplace-tabs">
      <button type="button" className={`marketplace-tab${tab==="esteira1"?" active":""}`} onClick={()=>setTab("esteira1")}>Esteira 1 — Escolha do parceiro</button>
      <button type="button" className={`marketplace-tab${tab==="esteira2"?" active":""}`} onClick={()=>setTab("esteira2")}>Esteira 2 — Robô Nina</button>
    </div>
    {notice&&<div className="notice"><CheckCircle2/>{notice}</div>}{error&&<div className="error">{error}</div>}
    {tab==="esteira1"&&<form className="marketplace-form" onSubmit={assessEsteira1}>
      <div className="marketplace-subtabs">
        <button type="button" className={`marketplace-tab${e1Category==="REAL_ESTATE"?" active":""}`} onClick={()=>{setE1Category("REAL_ESTATE");setSelectedQuota("")}}>Imóvel</button>
        <button type="button" className={`marketplace-tab${e1Category==="VEHICLE"?" active":""}`} onClick={()=>{setE1Category("VEHICLE");setSelectedQuota("")}}>Veículo</button>
      </div>
      <div className="marketplace-form-row">
        <label className="marketplace-field"><span className="marketplace-field-label"><Search size={14}/> Buscar por crédito (R$)</span><CurrencyInput value={e1FilterCredit} onChange={setE1FilterCredit} placeholder="Ex.: 250.000"/></label>
        <label className="marketplace-field"><span className="marketplace-field-label"><Search size={14}/> Buscar por entrada (R$)</span><CurrencyInput value={e1FilterEntrada} onChange={setE1FilterEntrada} placeholder="Ex.: 80.000"/></label>
        <small className="marketplace-hint">Filtro com tolerância de ±5% quando você informa um valor.</small>
      </div>
      <div className="marketplace-form-row">
        <label className="marketplace-field marketplace-field-wide">Carta disponível<select value={selectedQuota} onChange={e=>setSelectedQuota(e.target.value)} required><option value="">{e1Catalog.length?`Selecione (${e1Catalog.length} opção(ões))`:"Nenhuma carta neste filtro"}</option>{e1Catalog.map(q=><option key={q.id} value={q.id}>{quotaCatalogLabel(q)}</option>)}</select></label>
        <ClientProfileFields prefix="e1" category={e1Category} values={profile} flags={flags} onChange={(k,v)=>setProfile(p=>({...p,[k]:v}))} onFlag={(k,v)=>setFlags(p=>({...p,[k]:v}))}/>
        <button type="submit" className="marketplace-submit" disabled={!e1Catalog.length}><RefreshCw/>Analisar com Nina</button>
      </div>
    </form>}
    {tab==="esteira2"&&<form className="marketplace-form" onSubmit={matchEsteira2}>
      <div className="marketplace-form-row">
        <label className="marketplace-field">Crédito desejado (R$)<CurrencyInput value={targetAmount} onChange={setTargetAmount} required/></label>
        <label className="marketplace-field">Entrada desejada (R$)<CurrencyInput value={targetEntrada} onChange={setTargetEntrada} required/></label>
        <label className="marketplace-field marketplace-field-compact">Categoria<select value={category} onChange={e=>setCategory(e.target.value)}><option value="REAL_ESTATE">Imóvel</option><option value="VEHICLE">Veículo</option></select></label>
        <ClientProfileFields prefix="e2" category={category} values={profile} flags={flags} onChange={(k,v)=>setProfile(p=>({...p,[k]:v}))} onFlag={(k,v)=>setFlags(p=>({...p,[k]:v}))}/>
        <button type="submit" className="marketplace-submit"><RefreshCw/>Buscar opções robô</button>
      </div>
    </form>}
    {result1&&tab==="esteira1"&&<section className="panel"><div className="panel-title"><h2>Resultado Esteira 1</h2></div><div className="notice">{result1.message}</div>{result1.blockers.length>0&&<div className="error">{result1.blockers.map(b=><div key={b}>{b}</div>)}</div>}<p><Pill value={result1.eligible?"CLEARED":"BLOCKED"}/> {result1.quota.group_code} · {result1.quota.quota_code} · crédito {brl.format(Number(result1.quota.credit_value))} · entrada {brl.format(Number(result1.quota.entrada_final??result1.quota.premium_value))} · parcela {brl.format(Number(result1.quota.installment_value||0))}</p>{result1.eligible&&result1.quota.status==="AVAILABLE"&&result1.quota.nina_scan_status==="CLEARED"?<button className="table-action lock" onClick={()=>reserveQuota(result1.quota.quota_id)}><LockKeyhole/>Travar 60 min</button>:null}{result1.alternatives.length>0&&<><h3>Alternativas Nina</h3>{result1.alternatives.map(m=><MatchCard key={m.quota_ids.join("-")} match={m} onReserve={reserveQuota}/>)}</>}</section>}
    {result2&&tab==="esteira2"&&<section className="panel"><div className="panel-title"><h2>Opções robô Esteira 2 (régua {result2.band_percent??"5"}%)</h2></div><div className="notice">{result2.message}</div>{result2.blockers.map(b=><div className="error" key={b}>{b}</div>)}{(result2.credit_matches?.length??0)>0&&<h3>Lane crédito</h3>}{(result2.credit_matches??[]).map(m=><MatchCard key={`c-${m.quota_ids.join("-")}`} match={m} onReserve={reserveQuota}/>)}{(result2.entrada_matches?.length??0)>0&&<h3>Lane entrada</h3>}{(result2.entrada_matches??[]).map(m=><MatchCard key={`e-${m.quota_ids.join("-")}`} match={m} onReserve={reserveQuota}/>)}{!(result2.credit_matches?.length||result2.entrada_matches?.length)&&result2.matches.map(m=><MatchCard key={m.quota_ids.join("-")} match={m} onReserve={reserveQuota}/>)}</section>}
  </OperationalLayout>
}

export function ProposalsModule() {
  const [items,setItems]=useState<Proposal[]>([]);const [leads,setLeads]=useState<Lead[]>([]);const [quotas,setQuotas]=useState<Quota[]>([]);const [contracts,setContracts]=useState<Contract[]>([]);const [clients,setClients]=useState<CommercialClient[]>([]);const [isCommercial,setIsCommercial]=useState(false);const [selected,setSelected]=useState<string[]>([]);const [notice,setNotice]=useState("");const [proposalError,setProposalError]=useState("");
  const [newProduct,setNewProduct]=useState("MARKETPLACE");
  const [requestedAmount,setRequestedAmount]=useState("");
  const [duration,setDuration]=useState(12);const [sdcCapitalSource,setSdcCapitalSource]=useState("POOL");const [poolInvestmentAmount,setPoolInvestmentAmount]=useState("");const [sdcPoolInvestorRate,setSdcPoolInvestorRate]=useState("");const [assetValue,setAssetValue]=useState("");const [capitalSource,setCapitalSource]=useState("RETAIL");const [flashPoolInvestorRate,setFlashPoolInvestorRate]=useState("");const [term,setTerm]=useState(36);const [lastCalculation,setLastCalculation]=useState<Calculation|null>(null);const [flashIpcaAnnual,setFlashIpcaAnnual]=useState("4.5");
  useEffect(()=>{api<{default_ipca_projected_percent?:string}>("/finops/flash-capital/simulation-params").then(p=>{if(p.default_ipca_projected_percent)setFlashIpcaAnnual(p.default_ipca_projected_percent)}).catch(()=>undefined)},[]);
  const poolRatePreview=useMemo(()=>{const amount=Number(poolInvestmentAmount);if(!amount||amount<=0)return null;return {rate:"1,6"}},[poolInvestmentAmount]);
  const load=()=>Promise.all([api<User>("/auth/me"),api<Proposal[]>("/proposals"),api<Lead[]>("/leads"),api<Quota[]>("/quotas"),api<Contract[]>("/contracts")]).then(async([me,p,l,q,c])=>{setItems(p);setLeads(l);setQuotas(q);setContracts(c);const commercial=["MASTER_FRANCHISEE","MANAGER","PARTNER","QUOTA_SELLER"].includes(me.role);setIsCommercial(commercial);if(commercial){try{setClients(await api<CommercialClient[]>("/commercial/clients"))}catch{setClients([])}}else{setClients([])}});useEffect(()=>{void load()},[]);
  const available=useMemo(()=>quotas.filter(q=>q.status==="AVAILABLE"||q.status==="RESERVED"),[quotas]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setProposalError("");setNotice("");const form=e.currentTarget;const fd=new FormData(form);const amount=parseMoney(requestedAmount);if(!amount){setProposalError("Informe o valor solicitado (R$).");return}const leadId=String(fd.get("lead_id")||"").trim();if(!leadId){setProposalError(leads.length?"Selecione o cliente (lead) no campo acima.":"Cadastre um lead no CRM antes de criar a proposta.");return}const clientId=String(fd.get("client_user_id")||"");const product=String(fd.get("product")||"MARKETPLACE");try{await api("/proposals",{method:"POST",body:JSON.stringify({lead_id:leadId,product,requested_amount:String(amount),client_user_id:clientId||undefined,sale_channel:isCommercial?"PARTNER_OFFICE":undefined,terms:{channel:isCommercial?"PARTNER_OFFICE":"SELF_SERVICE"}})});form.reset();setRequestedAmount("");setNewProduct(product);setNotice("Proposta criada. Na tabela abaixo, ajuste os parâmetros se precisar e clique em Simular.");void load()}catch(err){setProposalError(err instanceof Error?err.message:"Não foi possível criar a proposta.")}}
  async function calculate(p:Proposal){setNotice("");try{let path=`/proposals/${p.id}/calculate`;let payload:Record<string,unknown>={quota_ids:selected,fee_percent:"10",start_fee:"1500"};if(p.product==="SDC"){path=`/proposals/${p.id}/calculate-sdc`;payload={quota_ids:selected,duration_months:duration,capital_source:sdcCapitalSource};if(sdcCapitalSource==="POOL"){if(poolInvestmentAmount)payload.pool_investment_amount=poolInvestmentAmount;if(sdcPoolInvestorRate)payload.pool_investor_rate_percent=sdcPoolInvestorRate}}if(p.product==="FLASH_CREDIT"){path=`/proposals/${p.id}/calculate-flash-credit`;const fundSource=capitalSource==="INSTITUTIONAL";payload={asset_value:assetValue,capital_source:capitalSource,term_months:term,ipca_annual_percent:fundSource?flashIpcaAnnual:"0"};if(capitalSource==="RETAIL"){if(poolInvestmentAmount)payload.pool_investment_amount=poolInvestmentAmount;if(flashPoolInvestorRate)payload.pool_investor_rate_percent=flashPoolInvestorRate}}const calc=await api<Calculation>(path,{method:"POST",body:JSON.stringify(payload)});setLastCalculation(calc);setNotice(`Memória ${calc.formula_version} criada com sucesso.`);setSelected([]);load()}catch(e){setNotice(e instanceof Error?e.message:"Falha no cálculo")}}
  async function contract(p:Proposal){const calcs=await api<{id:string}[]>(`/proposals/${p.id}/calculations`);if(!calcs.length){setNotice("Calcule a proposta antes de gerar o contrato.");return}await api(`/proposals/${p.id}/contracts`,{method:"POST",body:JSON.stringify({calculation_memory_id:calcs[0].id})});setNotice("Contrato gerado com hash de integridade.");load()}
  return <OperationalLayout title="Propostas e simulações" subtitle="Cadastro comercial unificado para parceiros: Marketplace, SDC e Flash Capital. Simule, gere contrato e registre a venda." icon={<FileText/>}>
    <div className="notice"><Clock3/><div><b>Compliance automático por produto</b><small style={{display:"block",marginTop:"0.35rem",lineHeight:1.5}}><b>Passo 1</b> — Selecione o cliente (lead), produto e valor; clique em <em>Nova proposta</em> (a linha aparece na tabela).<br/><b>Passo 2</b> — Ajuste parâmetros (cotas, pool, Flash/SDC) e clique <em>Simular</em> para memória versionada.<br/><b>Passo 3</b> — <em>Gerar contrato</em> registra a venda; Marketplace exige cotas travadas no inventário.<br/><b>SDC</b> — mesa em <Link href="/modules/sdc">SDC — Capital de Giro</Link>.<br/><b>Flash Capital</b> — mesa em <Link href="/modules/flash-capital">Flash Capital</Link> (fundo usa IPCA projetado na simulação).<br/><b>QuitCon</b> — mesa em <Link href="/modules/quitcon">QuitCon</Link>.</small></div></div>
    <form className="quick-form" onSubmit={submit}>{isCommercial&&clients.length>0&&<select name="client_user_id"><option value="">Cliente no escritório (opcional)</option>{clients.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>}<select name="lead_id" required aria-label="Cliente (lead)"><option value="">{leads.length?"Selecione o cliente (lead)":"Nenhum lead — cadastre no CRM"}</option>{leads.map(l=><option value={l.id} key={l.id}>{l.name}</option>)}</select><select name="product" value={newProduct} onChange={e=>setNewProduct(e.target.value)}><option value="MARKETPLACE">Marketplace</option><option value="SDC">SDC</option><option value="FLASH_CREDIT">Flash Capital</option></select><CurrencyInput value={requestedAmount} onChange={setRequestedAmount} placeholder="Valor solicitado (R$)" required/><button type="submit"><Plus/>Nova proposta</button></form>
    {proposalError&&<div className="error">{proposalError}</div>}
    <div className="product-parameters"><div><b>Parâmetros documentais</b><small>SDC: 4,5% total · Flash Capital: fruição fixa 2,5% a.m. (Tabela Price, sem 14% + IPCA) · Pool investidor: 1,6% a.m.</small></div><label>SDC — duração<input type="number" min="1" max="60" value={duration} onChange={e=>setDuration(Number(e.target.value))}/></label><label>SDC — origem<select value={sdcCapitalSource} onChange={e=>setSdcCapitalSource(e.target.value)}>{SDC_CAPITAL_SOURCES.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>{sdcCapitalSource==="POOL"&&<><label>Pool — valor aplicado (R$)<CurrencyInput value={poolInvestmentAmount} onChange={setPoolInvestmentAmount}/><small>Rentabilidade pool: 1,6% a.m. para qualquer valor aplicado.</small></label>{poolRatePreview&&<div className="notice"><RefreshCw/>Rentabilidade pool: {poolRatePreview.rate}% a.m. (livre de imposto)</div>}<label>SDC — override campanha (% a.m., opcional)<input type="number" min="0" max="4.5" step="0.1" value={sdcPoolInvestorRate} onChange={e=>setSdcPoolInvestorRate(e.target.value)} placeholder="Deixe vazio para 1,6% padrão"/></label></>}<label>Valor do bem<CurrencyInput value={assetValue} onChange={setAssetValue}/></label><label>Flash Capital — origem<select value={capitalSource} onChange={e=>setCapitalSource(e.target.value)}>{FLASH_CAPITAL_SOURCES.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>{capitalSource==="INSTITUTIONAL"&&<div className="notice"><small>Origem fundo: IPCA anual projetado {flashIpcaAnnual}% aplicado na memória de cálculo (fruição 2,5% a.m. inalterada).</small></div>}{capitalSource==="RETAIL"&&<><label>Pool — valor aplicado (R$)<CurrencyInput value={poolInvestmentAmount} onChange={setPoolInvestmentAmount}/><small>Rentabilidade pool: 1,6% a.m. para qualquer valor aplicado.</small></label>{poolRatePreview&&<div className="notice"><RefreshCw/>Rentabilidade pool: {poolRatePreview.rate}% a.m. (livre de imposto)</div>}<label>Flash — override campanha (% a.m., opcional)<input type="number" min="0" max="2.5" step="0.1" value={flashPoolInvestorRate} onChange={e=>setFlashPoolInvestorRate(e.target.value)} placeholder="Deixe vazio para 1,6% padrão"/></label></>}<label>Prazo<select value={term} onChange={e=>setTerm(Number(e.target.value))}><option value={36}>36 meses</option><option value={60}>60 meses + balão</option></select></label></div>
    {newProduct!=="FLASH_CREDIT"&&<div className="selection-box"><div><b>Passo 2 — Cotas para simulação ({newProduct==="SDC"?"SDC":"Marketplace"})</b><small>Depois de criar a proposta, marque uma ou mais cotas <b>disponíveis ou travadas</b> para você. Na tabela, clique <em>Simular</em> na linha da proposta. Para Marketplace, trave a cota no inventário antes do contrato. Identificação das cotas é interna (sem nome de fornecedor).</small></div><div>{available.length?available.map(q=><label key={q.id}><input type="checkbox" checked={selected.includes(q.id)} onChange={e=>setSelected(v=>e.target.checked?[...v,q.id]:v.filter(id=>id!==q.id))}/>{proposalQuotaListLabel(q)}</label>):<p className="muted">Nenhuma cota disponível no inventário no momento.</p>}</div></div>}
    {notice&&<div className="notice"><RefreshCw/>{notice}</div>}{lastCalculation&&<CalculationResult calculation={lastCalculation}/>}<DataTable headers={["Produto","Valor","Canal","Comissão","Parceiro","Status","Workflow"]}>{items.map(p=>{const hasContract=contracts.some(c=>c.proposal_id===p.id);const needsQuota=p.product!=="FLASH_CREDIT";return <tr key={p.id}><td><b>{productLabel(p.product)}</b><small>{p.lead_name??leads.find(l=>l.id===p.lead_id)?.name}</small></td><td>{brl.format(Number(p.requested_amount))}</td><td><small>{p.sale_channel??"—"}</small></td><td><b>{p.commission_originator_name??"—"}</b></td><td><b>{p.owner_name??"—"}</b><small>{p.served_by_name?`Atend.: ${p.served_by_name}`:p.owner_role??""}</small></td><td><Pill value={p.status}/></td><td className="actions-cell"><button className="table-action" disabled={needsQuota&&!selected.length} onClick={()=>calculate(p)}>Simular</button><button className="table-action" disabled={hasContract} onClick={()=>contract(p)}>{hasContract?"Contrato criado":"Gerar contrato"}</button></td></tr>})}</DataTable>
  </OperationalLayout>
}

function CalculationResult({calculation}:{calculation:Calculation}){const labels:Record<string,string>={principal:"Principal (nominal)",total_interest:"Juros totais",investor_interest:"Investidores",platform_spread:"Spread LETTER",maturity_total:"Total no vencimento",start_fee_total:"Taxa de Start",start_fee_milestone_1:"Marco 1",start_fee_milestone_2:"Marco 2",intermediation_fee:"Fee 10%",capital_commission:"Captação 1%",asset_value:"Valor do bem",ltv_percent:"LTV (%)",monthly_payment:"Parcela",balloon_payment:"Parcela balão",management_fee_total:"Gestão 0,5%",itbi_provision:"Provisão ITBI",platform_fee:"Fee plataforma",structuring_fee:"Fee plataforma",partner_commission_base:"Base comissão rede",net_payout:"Payout líquido",total_contract:"Total do contrato",pool_investor_rate_percent:"Rentabilidade pool (% a.m.)",pool_investor_tier_label:"Faixa pool",pool_investor_tax_status:"Status fiscal pool",investor_rate_percent:"Rentabilidade investidor (% a.m.)",platform_spread_rate_percent:"Spread plataforma (% a.m.)"};const entries=Object.entries(calculation.output).filter(([key,value])=>labels[key]&&value!==null);const notes=[calculation.output.partner_commission_basis_note,calculation.output.interest_basis_note,calculation.output.pool_investor_tax_note].filter(x=>typeof x==="string");const quitconContext=calculation.formula_version.startsWith("sdc-")&&calculation.quitcon_sdc?{proposalId:calculation.proposal_id,calculationMemoryId:calculation.id,mesesRestantes:Number(calculation.output.duration_months??calculation.input.duration_months??0)||undefined}:undefined;return <div className="calculation-result"><div><span className="eyebrow dark">MEMÓRIA VERSIONADA</span><b>{calculation.formula_version}</b></div>{notes.map((note,i)=><small key={i}>{String(note)}</small>)}<div>{entries.map(([key,value])=><article key={key}><small>{labels[key]}</small><strong>{key.includes("percent")||key==="pool_investor_rate_percent"?`${value}%`:key==="pool_investor_tax_status"?"Livre de imposto (sem retenção)":key.includes("tier")?String(value):brl.format(Number(value))}</strong></article>)}</div>{calculation.quitcon_sdc&&<SdcQuitConProjectionTable data={calculation.quitcon_sdc} context={quitconContext}/>}</div>}

function OperationalLayout({title,subtitle,icon,children}:{title:string;subtitle:string;icon:React.ReactNode;children:React.ReactNode}){return <><div className="page-heading"><div><span className="eyebrow dark">OPERAÇÃO ATIVA</span><h1>{title}</h1><p>{subtitle}</p></div><div className="operational-icon">{icon}</div></div><section className="panel operational-panel">{children}</section></>}
function DataTable({headers,children}:{headers:string[];children:React.ReactNode}){return <div className="table-wrap"><table className="data-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>}
function Pill({value}:{value:string}){return <span className={`pill pill-${value.toLowerCase()}`}>{value.replaceAll("_"," ")}</span>}
