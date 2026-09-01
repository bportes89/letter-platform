"use client";

import { Check, CheckCircle2, Clock3, FileText, LockKeyhole, Plus, RefreshCw, Unlock, Users, WalletCards } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Administrator, api, Calculation, Contract, Lead, Proposal, Quota, Reservation } from "@/lib/api";
import { FLASH_CAPITAL_SOURCES, productLabel, SDC_CAPITAL_SOURCES } from "@/lib/products";
import { SdcQuitConProjectionTable } from "@/components/sdc-quitcon-card";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function LeadsModule() {
  const [items,setItems]=useState<Lead[]>([]); const [error,setError]=useState("");
  const load=()=>api<Lead[]>("/leads").then(setItems).catch(e=>setError(e.message));
  useEffect(()=>{void load()},[]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await api("/leads",{method:"POST",body:JSON.stringify({name:fd.get("name"),phone:fd.get("phone"),product_interest:fd.get("product_interest"),source:"DASHBOARD"})});form.reset();load()}
  async function advance(lead:Lead){const next:Record<string,string>={NEW:"CONTACTED",CONTACTED:"QUALIFIED",QUALIFIED:"PROPOSAL",PROPOSAL:"CONVERTED"};await api(`/leads/${lead.id}`,{method:"PATCH",body:JSON.stringify({status:next[lead.status]??"QUALIFIED"})});load()}
  return <OperationalLayout title="CRM e originação" subtitle="Cadastre leads e avance a jornada comercial com histórico auditável." icon={<Users/>}>
    <form className="quick-form" onSubmit={submit}><input name="name" placeholder="Nome do cliente" required minLength={2}/><input name="phone" placeholder="WhatsApp" required minLength={8}/><select name="product_interest"><option value="MARKETPLACE">Marketplace</option><option value="SDC">SDC</option><option value="FLASH_CREDIT">Flash Capital</option></select><button><Plus/>Adicionar lead</button></form>
    {error&&<div className="error">{error}</div>}<DataTable headers={["Cliente","Contato","Interesse","SCR/Bacen","Status","Ação"]}>{items.map(x=><tr key={x.id}><td><b>{x.name}</b><small>{x.source}</small></td><td>{x.phone}</td><td>{productLabel(x.product_interest)}</td><td><small>{x.scr_reference ?? "—"}</small><br/><span className="pill">{x.scr_status ?? "PENDENTE"}</span></td><td><Pill value={x.status}/></td><td><button className="table-action" onClick={()=>advance(x)}>Avançar</button></td></tr>)}</DataTable>
  </OperationalLayout>
}

export function InventoryModule() {
  const [items,setItems]=useState<Quota[]>([]);const [admins,setAdmins]=useState<Administrator[]>([]);const [reservations,setReservations]=useState<Reservation[]>([]);const [error,setError]=useState("");const [notice,setNotice]=useState("");
  const load=()=>Promise.all([api<Quota[]>("/quotas"),api<Administrator[]>("/administrators"),api<Reservation[]>("/reservations")]).then(([q,a,r])=>{setItems(q);setAdmins(a);setReservations(r)}).catch(e=>setError(e.message));useEffect(()=>{void load()},[]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await api("/quotas",{method:"POST",body:JSON.stringify({administrator_id:fd.get("administrator_id"),group_code:fd.get("group_code"),quota_code:fd.get("quota_code"),category:fd.get("category"),credit_value:fd.get("credit_value"),outstanding_balance:fd.get("outstanding_balance")||"0",premium_value:fd.get("premium_value")||"0",installment_due_date:fd.get("installment_due_date")||null})});form.reset();setNotice("Cota cadastrada no inventário.");load()}
  async function ninaScan(quota:Quota){setError("");try{const result=await api<{message:string}>("/quotas/"+quota.id+"/nina-scan",{method:"POST"});setNotice(result.message);load()}catch(e){setError(e instanceof Error?e.message:"Varredura Nina reprovada.")}}
  async function reserve(quota:Quota){setError("");try{await api("/reservations",{method:"POST",body:JSON.stringify({quota_id:quota.id,ttl_minutes:60})});setNotice(`Cota ${quota.group_code}/${quota.quota_code} travada por 60 minutos.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha na trava")}}
  async function release(quota:Quota){const res=reservations.find(r=>r.quota_id===quota.id&&r.status==="ACTIVE");if(res){await api(`/reservations/${res.id}/release`,{method:"POST"});load()}}
  const fmtDate=(value?:string|null)=>value?new Date(value+"T12:00:00").toLocaleDateString("pt-BR"):"—";
  return <OperationalLayout title="Inventário (admin)" subtitle="Cadastro interno de cotas, varredura Nina e trava de 60 min — estrutura operacional, não é a jornada comercial do parceiro." icon={<WalletCards/>}>
    <div className="notice"><Clock3/>Fluxo: <b>1.</b> Cadastro (admin) · <b>2.</b> Varredura Nina · <b>3.</b> Trava 60 min · <b>4.</b> Proposta em SDC/Marketplace · <b>5.</b> Contrato registra a venda</div>
    <form className="quick-form quota-form" onSubmit={submit}><select name="administrator_id" required>{admins.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select><input name="group_code" placeholder="Grupo" required/><input name="quota_code" placeholder="Cota" required/><select name="category"><option value="REAL_ESTATE">Imóvel</option><option value="VEHICLE">Veículo</option></select><input name="credit_value" type="number" min="1" step="0.01" placeholder="Crédito" required/><input name="premium_value" type="number" min="0" step="0.01" placeholder="Ágio"/><input name="outstanding_balance" type="number" min="0" step="0.01" placeholder="Saldo devedor"/><input name="installment_due_date" type="date" placeholder="Vencimento parcela" required title="Vencimento da parcela"/><button><Plus/>Cadastrar cota</button></form>
    {notice&&<div className="notice"><CheckCircle2/>{notice}</div>}{error&&<div className="error">{error}</div>}<DataTable headers={["Identificação","Categoria","Crédito","Ágio","Vencimento","Nina","Status","Ações"]}>{items.map(x=><tr key={x.id}><td><b>Grupo {x.group_code}</b><small>Cota {x.quota_code}</small></td><td>{x.category==="REAL_ESTATE"?"Imóvel":"Veículo"}</td><td>{brl.format(Number(x.credit_value))}</td><td>{brl.format(Number(x.premium_value))}</td><td>{fmtDate(x.installment_due_date)}</td><td><Pill value={x.nina_scan_status??"PENDENTE"}/></td><td><Pill value={x.status}/></td><td className="actions-cell">{x.status==="AVAILABLE"?<><button className="table-action" onClick={()=>ninaScan(x)} disabled={!x.installment_due_date}><RefreshCw/>Varredura Nina</button><button className="table-action lock" onClick={()=>reserve(x)} disabled={x.nina_scan_status!=="CLEARED"}><LockKeyhole/>Travar 60 min</button></>:x.status==="RESERVED"?<button className="table-action" onClick={()=>release(x)}><Unlock/>Liberar</button>:x.status==="SOLD"?"Vendida":"—"}</td></tr>)}</DataTable>
  </OperationalLayout>
}

type MarketplaceMatch = {
  quota_ids: string[];
  total_credit: string;
  deviation_percent: string;
  score: number;
  administrator_id: string;
  administrator_name?: string;
  explanation: string;
  message?: string;
  quotas: { quota_id: string; group_code: string; quota_code: string; category: string; credit_value: string; premium_value: string; installment_due_date?: string | null; administrator_name?: string; status: string; nina_scan_status?: string | null }[];
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
  message: string;
};

function ClientProfileFields({prefix,values,onChange}:{prefix:string;values:Record<string,string>;onChange:(k:string,v:string)=>void}) {
  return <>
    <label>Renda mensal (R$)<input type="number" min="1" step="0.01" value={values[`${prefix}_income`]} onChange={e=>onChange(`${prefix}_income`,e.target.value)} required/></label>
    <label>Comprometimento atual (R$)<input type="number" min="0" step="0.01" value={values[`${prefix}_commitment`]} onChange={e=>onChange(`${prefix}_commitment`,e.target.value)}/></label>
    <label>Valor do bem (R$)<input type="number" min="1" step="0.01" value={values[`${prefix}_asset`]} onChange={e=>onChange(`${prefix}_asset`,e.target.value)} required/></label>
    <label>Ano do bem<input type="number" min="1980" max="2100" value={values[`${prefix}_year`]} onChange={e=>onChange(`${prefix}_year`,e.target.value)} required/></label>
  </>;
}

export function MarketplaceModule() {
  const [quotas,setQuotas]=useState<Quota[]>([]);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [tab,setTab]=useState<"esteira1"|"esteira2">("esteira1");
  const [profile,setProfile]=useState({e1_income:"30000",e1_commitment:"3000",e1_asset:"600000",e1_year:"2020",e2_income:"30000",e2_commitment:"3000",e2_asset:"600000",e2_year:"2020"});
  const [selectedQuota,setSelectedQuota]=useState("");
  const [targetAmount,setTargetAmount]=useState("800000");
  const [category,setCategory]=useState("REAL_ESTATE");
  const [result1,setResult1]=useState<MarketplaceEsteira1Result|null>(null);
  const [result2,setResult2]=useState<MarketplaceEsteira2Result|null>(null);
  const load=()=>api<Quota[]>("/quotas").then(setQuotas).catch(e=>setError(e.message));
  useEffect(()=>{void load()},[]);
  const available=useMemo(()=>quotas.filter(q=>q.status==="AVAILABLE"||q.status==="RESERVED"),[quotas]);
  const profilePayload=(prefix:"e1"|"e2")=>({monthly_income:profile[`${prefix}_income`],monthly_commitment:profile[`${prefix}_commitment`]||"0",asset_value:profile[`${prefix}_asset`],asset_year:Number(profile[`${prefix}_year`])});
  async function assessEsteira1(e:FormEvent){e.preventDefault();setError("");setNotice("");try{const data=await api<MarketplaceEsteira1Result>("/marketplace/esteira-1/assess",{method:"POST",body:JSON.stringify({quota_id:selectedQuota,...profilePayload("e1")})});setResult1(data);setNotice(data.message)}catch(err){setError(err instanceof Error?err.message:"Falha na Esteira 1")}}
  async function matchEsteira2(e:FormEvent){e.preventDefault();setError("");setNotice("");try{const data=await api<MarketplaceEsteira2Result>("/marketplace/esteira-2/match",{method:"POST",body:JSON.stringify({target_amount:targetAmount,category,...profilePayload("e2")})});setResult2(data);setNotice(data.message)}catch(err){setError(err instanceof Error?err.message:"Falha na Esteira 2")}}
  async function reserveQuota(quotaId:string){setError("");try{await api("/reservations",{method:"POST",body:JSON.stringify({quota_id:quotaId,ttl_minutes:60})});setNotice("Cota travada por 60 minutos. Prossiga em Propostas.");load()}catch(err){setError(err instanceof Error?err.message:"Falha na trava")}}
  function MatchCard({match,onReserve}:{match:MarketplaceMatch;onReserve:(id:string)=>void}) {
    return <article className="backlog-item"><div><strong>{match.administrator_name??"Administradora"} · {brl.format(Number(match.total_credit))}</strong><p>{match.explanation}{match.message?` — ${match.message}`:""}</p><small>Score Nina: {match.score} · Desvio {match.deviation_percent}%</small><div>{match.quotas.map(q=><label key={q.quota_id} style={{display:"block",marginTop:"0.5rem"}}><span>{q.group_code}/{q.quota_code} · {brl.format(Number(q.credit_value))} · Nina {q.nina_scan_status??"PENDENTE"}</span>{q.status==="AVAILABLE"&&q.nina_scan_status==="CLEARED"?<button type="button" className="table-action lock" style={{marginLeft:"0.75rem"}} onClick={()=>onReserve(q.quota_id)}><LockKeyhole/>Travar 60 min</button>:null}</label>)}</div></div></article>;
  }
  return <OperationalLayout title="Marketplace — Cartas contempladas" subtitle="Esteira 1: parceiro escolhe a carta e Nina valida perfil. Esteira 2: Nina entrega opções por valor e ano do bem." icon={<WalletCards/>}>
    <div className="notice"><Clock3/>Admin cadastra cotas em <b>Inventário</b> (submenu Cartas contempladas). Depois opere as esteiras aqui e finalize a venda em <b>Propostas e simulações</b>.</div>
    <div className="marketplace-tabs">
      <button type="button" className={`marketplace-tab${tab==="esteira1"?" active":""}`} onClick={()=>setTab("esteira1")}>Esteira 1 — Escolha do parceiro</button>
      <button type="button" className={`marketplace-tab${tab==="esteira2"?" active":""}`} onClick={()=>setTab("esteira2")}>Esteira 2 — Curadoria Nina</button>
    </div>
    {notice&&<div className="notice"><CheckCircle2/>{notice}</div>}{error&&<div className="error">{error}</div>}
    {tab==="esteira1"&&<form className="quick-form quota-form marketplace-form" onSubmit={assessEsteira1}>
      <label>Carta/cota<select value={selectedQuota} onChange={e=>setSelectedQuota(e.target.value)} required><option value="">Selecione a carta/cota</option>{available.map(q=><option key={q.id} value={q.id}>{q.group_code}/{q.quota_code} · {q.category==="REAL_ESTATE"?"Imóvel":"Veículo"} · {brl.format(Number(q.credit_value))}</option>)}</select></label>
      <ClientProfileFields prefix="e1" values={profile} onChange={(k,v)=>setProfile(p=>({...p,[k]:v}))}/>
      <button><RefreshCw/>Analisar com Nina</button>
    </form>}
    {tab==="esteira2"&&<form className="quick-form quota-form marketplace-form" onSubmit={matchEsteira2}>
      <label>Valor desejado (R$)<input type="number" min="1" step="0.01" value={targetAmount} onChange={e=>setTargetAmount(e.target.value)} required/></label>
      <label>Categoria<select value={category} onChange={e=>setCategory(e.target.value)}><option value="REAL_ESTATE">Imóvel</option><option value="VEHICLE">Veículo</option></select></label>
      <ClientProfileFields prefix="e2" values={profile} onChange={(k,v)=>setProfile(p=>({...p,[k]:v}))}/>
      <button><RefreshCw/>Buscar opções Nina</button>
    </form>}
    {result1&&tab==="esteira1"&&<section className="panel"><div className="panel-title"><h2>Resultado Esteira 1</h2></div><div className="notice">{result1.message}</div>{result1.blockers.length>0&&<div className="error">{result1.blockers.map(b=><div key={b}>{b}</div>)}</div>}<p><Pill value={result1.eligible?"CLEARED":"BLOCKED"}/> Carta {result1.quota.group_code}/{result1.quota.quota_code} · {brl.format(Number(result1.quota.credit_value))}</p>{result1.eligible&&result1.quota.status==="AVAILABLE"&&result1.quota.nina_scan_status==="CLEARED"?<button className="table-action lock" onClick={()=>reserveQuota(result1.quota.quota_id)}><LockKeyhole/>Travar 60 min</button>:null}{result1.alternatives.length>0&&<><h3>Alternativas Nina</h3>{result1.alternatives.map(m=><MatchCard key={m.quota_ids.join("-")} match={m} onReserve={reserveQuota}/>)}</>}</section>}
    {result2&&tab==="esteira2"&&<section className="panel"><div className="panel-title"><h2>Opções Nina (Esteira 2)</h2></div><div className="notice">{result2.message}</div>{result2.blockers.map(b=><div className="error" key={b}>{b}</div>)}{result2.matches.map(m=><MatchCard key={m.quota_ids.join("-")} match={m} onReserve={reserveQuota}/>)}</section>}
  </OperationalLayout>
}

export function ProposalsModule() {
  const [items,setItems]=useState<Proposal[]>([]);const [leads,setLeads]=useState<Lead[]>([]);const [quotas,setQuotas]=useState<Quota[]>([]);const [contracts,setContracts]=useState<Contract[]>([]);const [selected,setSelected]=useState<string[]>([]);const [notice,setNotice]=useState("");
  const [duration,setDuration]=useState(12);const [sdcCapitalSource,setSdcCapitalSource]=useState("POOL");const [poolInvestmentAmount,setPoolInvestmentAmount]=useState("80000");const [sdcPoolInvestorRate,setSdcPoolInvestorRate]=useState("");const [assetValue,setAssetValue]=useState("500000");const [capitalSource,setCapitalSource]=useState("RETAIL");const [flashPoolInvestorRate,setFlashPoolInvestorRate]=useState("");const [term,setTerm]=useState(36);const [lastCalculation,setLastCalculation]=useState<Calculation|null>(null);
  const poolRatePreview=useMemo(()=>{const amount=Number(poolInvestmentAmount);if(!amount||amount<=0)return null;return {rate:"1,6"}},[poolInvestmentAmount]);
  const load=()=>Promise.all([api<Proposal[]>("/proposals"),api<Lead[]>("/leads"),api<Quota[]>("/quotas"),api<Contract[]>("/contracts")]).then(([p,l,q,c])=>{setItems(p);setLeads(l);setQuotas(q);setContracts(c)});useEffect(()=>{void load()},[]);
  const available=useMemo(()=>quotas.filter(q=>q.status==="AVAILABLE"||q.status==="RESERVED"),[quotas]);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await api("/proposals",{method:"POST",body:JSON.stringify({lead_id:fd.get("lead_id"),product:fd.get("product"),requested_amount:fd.get("requested_amount"),terms:{channel:"DASHBOARD"}})});form.reset();load()}
  async function calculate(p:Proposal){setNotice("");try{let path=`/proposals/${p.id}/calculate`;let payload:Record<string,unknown>={quota_ids:selected,fee_percent:"10",start_fee:"1500"};if(p.product==="SDC"){path=`/proposals/${p.id}/calculate-sdc`;payload={quota_ids:selected,duration_months:duration,capital_source:sdcCapitalSource};if(sdcCapitalSource==="POOL"){if(poolInvestmentAmount)payload.pool_investment_amount=poolInvestmentAmount;if(sdcPoolInvestorRate)payload.pool_investor_rate_percent=sdcPoolInvestorRate}}if(p.product==="FLASH_CREDIT"){path=`/proposals/${p.id}/calculate-flash-credit`;payload={asset_value:assetValue,capital_source:capitalSource,term_months:term,ipca_annual_percent:"0"};if(capitalSource==="RETAIL"){if(poolInvestmentAmount)payload.pool_investment_amount=poolInvestmentAmount;if(flashPoolInvestorRate)payload.pool_investor_rate_percent=flashPoolInvestorRate}}const calc=await api<Calculation>(path,{method:"POST",body:JSON.stringify(payload)});setLastCalculation(calc);setNotice(`Memória ${calc.formula_version} criada com sucesso.`);setSelected([]);load()}catch(e){setNotice(e instanceof Error?e.message:"Falha no cálculo")}}
  async function contract(p:Proposal){const calcs=await api<{id:string}[]>(`/proposals/${p.id}/calculations`);if(!calcs.length){setNotice("Calcule a proposta antes de gerar o contrato.");return}await api(`/proposals/${p.id}/contracts`,{method:"POST",body:JSON.stringify({calculation_memory_id:calcs[0].id})});setNotice("Contrato gerado com hash de integridade.");load()}
  return <OperationalLayout title="Propostas e simulações" subtitle="Cadastro comercial unificado para parceiros: Marketplace, SDC e Flash Capital. Simule, gere contrato e registre a venda." icon={<FileText/>}>
    <div className="notice"><Clock3/><div><b>Compliance automático por produto</b><small style={{display:"block",marginTop:"0.35rem",lineHeight:1.5}}><b>SDC</b> — após simular, esteira interna com TAPAF R$ 1.500 + LTV + Valid-Stamp (<Link href="/modules/sdc">SDC — estrutura interna</Link>).<br/><b>Flash Capital</b> — LTV 40% na simulação; TAPAF R$ 1.500 + Valid-Stamp na esteira abaixo do simulador (<Link href="/modules/flash-capital">Flash Capital</Link>).<br/><b>Lease Equity / QuitCon</b> — TAPAF e RWA nos módulos próprios.</small></div></div>
    <form className="quick-form" onSubmit={submit}><select name="lead_id" required>{leads.map(l=><option value={l.id} key={l.id}>{l.name}</option>)}</select><select name="product"><option value="MARKETPLACE">Marketplace</option><option value="SDC">SDC</option><option value="FLASH_CREDIT">Flash Capital</option></select><input name="requested_amount" type="number" min="1" step="0.01" placeholder="Valor solicitado" required/><button><Plus/>Nova proposta</button></form>
    <div className="product-parameters"><div><b>Parâmetros documentais</b><small>SDC: 4,5% total · Flash Capital: fruição fixa 2,5% a.m. (Tabela Price, sem 14% + IPCA) · Pool investidor: 1,6% a.m.</small></div><label>SDC — duração<input type="number" min="1" max="60" value={duration} onChange={e=>setDuration(Number(e.target.value))}/></label><label>SDC — origem<select value={sdcCapitalSource} onChange={e=>setSdcCapitalSource(e.target.value)}>{SDC_CAPITAL_SOURCES.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>{sdcCapitalSource==="POOL"&&<><label>Pool — valor aplicado (R$)<input type="number" min="1" step="0.01" value={poolInvestmentAmount} onChange={e=>setPoolInvestmentAmount(e.target.value)}/><small>Rentabilidade pool: 1,6% a.m. para qualquer valor aplicado.</small></label>{poolRatePreview&&<div className="notice"><RefreshCw/>Rentabilidade pool: {poolRatePreview.rate}% a.m. (livre de imposto)</div>}<label>SDC — override campanha (% a.m., opcional)<input type="number" min="0" max="4.5" step="0.1" value={sdcPoolInvestorRate} onChange={e=>setSdcPoolInvestorRate(e.target.value)} placeholder="Deixe vazio para 1,6% padrão"/></label></>}<label>Valor do bem<input type="number" min="1" value={assetValue} onChange={e=>setAssetValue(e.target.value)}/></label><label>Flash Capital — origem<select value={capitalSource} onChange={e=>setCapitalSource(e.target.value)}>{FLASH_CAPITAL_SOURCES.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>{capitalSource==="RETAIL"&&<><label>Pool — valor aplicado (R$)<input type="number" min="1" step="0.01" value={poolInvestmentAmount} onChange={e=>setPoolInvestmentAmount(e.target.value)}/><small>Rentabilidade pool: 1,6% a.m. para qualquer valor aplicado.</small></label>{poolRatePreview&&<div className="notice"><RefreshCw/>Rentabilidade pool: {poolRatePreview.rate}% a.m. (livre de imposto)</div>}<label>Flash — override campanha (% a.m., opcional)<input type="number" min="0" max="2.5" step="0.1" value={flashPoolInvestorRate} onChange={e=>setFlashPoolInvestorRate(e.target.value)} placeholder="Deixe vazio para 1,6% padrão"/></label></>}<label>Prazo<select value={term} onChange={e=>setTerm(Number(e.target.value))}><option value={36}>36 meses</option><option value={60}>60 meses + balão</option></select></label></div>
    <div className="selection-box"><div><b>Cotas para Marketplace/SDC (subir proposta)</b><small>Use cotas travadas no inventário. Simular → Gerar contrato registra a venda (status SOLD).</small></div><div>{available.map(q=><label key={q.id}><input type="checkbox" checked={selected.includes(q.id)} onChange={e=>setSelected(v=>e.target.checked?[...v,q.id]:v.filter(id=>id!==q.id))}/>{q.group_code}/{q.quota_code} · {q.category==="REAL_ESTATE"?"Imóvel":"Veículo"} · {brl.format(Number(q.credit_value))}{q.installment_due_date?` · venc. ${new Date(q.installment_due_date+"T12:00:00").toLocaleDateString("pt-BR")}`:""} · {q.status}</label>)}</div></div>
    {notice&&<div className="notice"><RefreshCw/>{notice}</div>}{lastCalculation&&<CalculationResult calculation={lastCalculation}/>}<DataTable headers={["Produto","Valor","Versão","Status","Workflow"]}>{items.map(p=>{const hasContract=contracts.some(c=>c.proposal_id===p.id);const needsQuota=p.product!=="FLASH_CREDIT";return <tr key={p.id}><td><b>{productLabel(p.product)}</b><small>{leads.find(l=>l.id===p.lead_id)?.name}</small></td><td>{brl.format(Number(p.requested_amount))}</td><td>{p.calculation_version}</td><td><Pill value={p.status}/></td><td className="actions-cell"><button className="table-action" disabled={needsQuota&&!selected.length} onClick={()=>calculate(p)}>Simular</button><button className="table-action" disabled={hasContract} onClick={()=>contract(p)}>{hasContract?"Contrato criado":"Gerar contrato"}</button></td></tr>})}</DataTable>
  </OperationalLayout>
}

function CalculationResult({calculation}:{calculation:Calculation}){const labels:Record<string,string>={principal:"Principal (nominal)",total_interest:"Juros totais",investor_interest:"Investidores",platform_spread:"Spread LETTER",maturity_total:"Total no vencimento",start_fee_total:"Taxa de Start",start_fee_milestone_1:"Marco 1",start_fee_milestone_2:"Marco 2",intermediation_fee:"Fee 10%",capital_commission:"Captação 1%",asset_value:"Valor do bem",ltv_percent:"LTV (%)",monthly_payment:"Parcela",balloon_payment:"Parcela balão",management_fee_total:"Gestão 0,5%",itbi_provision:"Provisão ITBI",platform_fee:"Fee plataforma",structuring_fee:"Fee plataforma",partner_commission_base:"Base comissão rede",net_payout:"Payout líquido",total_contract:"Total do contrato",pool_investor_rate_percent:"Rentabilidade pool (% a.m.)",pool_investor_tier_label:"Faixa pool",pool_investor_tax_status:"Status fiscal pool",investor_rate_percent:"Rentabilidade investidor (% a.m.)",platform_spread_rate_percent:"Spread plataforma (% a.m.)"};const entries=Object.entries(calculation.output).filter(([key,value])=>labels[key]&&value!==null);const notes=[calculation.output.partner_commission_basis_note,calculation.output.interest_basis_note,calculation.output.pool_investor_tax_note].filter(x=>typeof x==="string");const quitconContext=calculation.formula_version.startsWith("sdc-")&&calculation.quitcon_sdc?{proposalId:calculation.proposal_id,calculationMemoryId:calculation.id,mesesRestantes:Number(calculation.output.duration_months??calculation.input.duration_months??0)||undefined}:undefined;return <div className="calculation-result"><div><span className="eyebrow dark">MEMÓRIA VERSIONADA</span><b>{calculation.formula_version}</b></div>{notes.map((note,i)=><small key={i}>{String(note)}</small>)}<div>{entries.map(([key,value])=><article key={key}><small>{labels[key]}</small><strong>{key.includes("percent")||key==="pool_investor_rate_percent"?`${value}%`:key==="pool_investor_tax_status"?"Livre de imposto (sem retenção)":key.includes("tier")?String(value):brl.format(Number(value))}</strong></article>)}</div>{calculation.quitcon_sdc&&<SdcQuitConProjectionTable data={calculation.quitcon_sdc} context={quitconContext}/>}</div>}

function OperationalLayout({title,subtitle,icon,children}:{title:string;subtitle:string;icon:React.ReactNode;children:React.ReactNode}){return <><div className="page-heading"><div><span className="eyebrow dark">OPERAÇÃO ATIVA</span><h1>{title}</h1><p>{subtitle}</p></div><div className="operational-icon">{icon}</div></div><section className="panel operational-panel">{children}</section></>}
function DataTable({headers,children}:{headers:string[];children:React.ReactNode}){return <div className="table-wrap"><table className="data-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>}
function Pill({value}:{value:string}){return <span className={`pill pill-${value.toLowerCase()}`}>{value.replaceAll("_"," ")}</span>}
