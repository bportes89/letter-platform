"use client";

import { Check, CheckCircle2, Clock3, Download, FileText, LockKeyhole, Plus, RefreshCw, Search, Unlock, Users, WalletCards, XCircle } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Administrator, api, Calculation, CommercialClient, Contract, downloadApi, Lead, Proposal, Quota, Reservation, User } from "@/lib/api";
import { FLASH_CAPITAL_SOURCES, productLabel } from "@/lib/products";
import { SdcQuitConProjectionTable } from "@/components/sdc-quitcon-card";
import { CurrencyInput, CurrencyFormField } from "@/components/currency-input";
import { MarketplaceQuotaFields } from "@/components/marketplace-quota-fields";

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

const INVENTORY_STOCK_STATUSES = new Set(["AVAILABLE", "RESERVED", "PENDING_REVIEW"]);

type InventoryCategoryFilter = "ALL" | "REAL_ESTATE" | "VEHICLE";

function inventorySupplierLabel(
  sourceKey: string | null | undefined,
  suppliers: { source_key: string; name: string }[],
): string {
  if (!sourceKey) return "Cadastro manual";
  const row = suppliers.find((s) => s.source_key === sourceKey);
  return row?.name ?? sourceKey;
}

type QuotaCategoryRow = { id: string; name: string; legacy_type: number; parent_id: string | null; title_sub: string | null };

export function InventoryModule() {
  const [items,setItems]=useState<Quota[]>([]);const [admins,setAdmins]=useState<Administrator[]>([]);const [reservations,setReservations]=useState<Reservation[]>([]);const [suppliers,setSuppliers]=useState<{source_key:string;name:string;markup_percent:string}[]>([]);const [quotaCategories,setQuotaCategories]=useState<QuotaCategoryRow[]>([]);const [error,setError]=useState("");const [notice,setNotice]=useState("");const [formKey,setFormKey]=useState(0);
  const [categoryFilter, setCategoryFilter] = useState<InventoryCategoryFilter>("ALL");
  const [supplierFilter, setSupplierFilter] = useState("");
  const [inventorySearch, setInventorySearch] = useState("");
  const load=()=>Promise.all([api<Quota[]>("/quotas"),api<Administrator[]>("/administrators"),api<Reservation[]>("/reservations"),api<{source_key:string;name:string;markup_percent:string;active:boolean}[]>("/marketplace/suppliers?active_only=true").catch(()=>[]),api<QuotaCategoryRow[]>("/marketplace/quota-categories").catch(()=>[])]).then(([q,a,r,s,c])=>{setItems(q);setAdmins(a);setReservations(r);setSuppliers(s.filter(x=>x.active!==false));setQuotaCategories(c)}).catch(e=>setError(e.message));useEffect(()=>{void load()},[]);
  const subcategories=useMemo(()=>quotaCategories.filter(c=>c.legacy_type===1),[quotaCategories]);
  const parentLabel=(parentId:string|null)=>{const p=quotaCategories.find(x=>x.id===parentId);return p?(p.title_sub||p.name):"";};
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);const qcat=String(fd.get("quota_category_id")||"");await api("/quotas",{method:"POST",body:JSON.stringify({administrator_id:fd.get("administrator_id"),group_code:fd.get("group_code"),quota_code:fd.get("quota_code"),category:fd.get("category"),quota_category_id:qcat||null,credit_value:fd.get("credit_value"),outstanding_balance:fd.get("outstanding_balance")||"0",premium_value:fd.get("premium_value")||"0",installment_value:fd.get("installment_value")||"0",installment_due_date:fd.get("installment_due_date")||null,remaining_installments:fd.get("remaining_installments")?Number(fd.get("remaining_installments")):null,supplier_source:fd.get("supplier_source")||null})});form.reset();setFormKey(k=>k+1);setNotice("Cota cadastrada no inventário.");load()}
  async function ninaScan(quota:Quota){setError("");try{const result=await api<{message:string}>("/quotas/"+quota.id+"/nina-scan",{method:"POST"});setNotice(result.message);load()}catch(e){setError(e instanceof Error?e.message:"Varredura Nina reprovada.")}}
  async function reserve(quota:Quota){setError("");try{await api("/reservations",{method:"POST",body:JSON.stringify({quota_id:quota.id,ttl_minutes:60})});setNotice(`Cota ${quota.group_code}/${quota.quota_code} travada por 60 minutos.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha na trava")}}
  async function release(quota:Quota){const res=reservations.find(r=>r.quota_id===quota.id&&r.status==="ACTIVE");if(res){await api(`/reservations/${res.id}/release`,{method:"POST"});load()}}
  async function approveQuota(quota:Quota){setError("");try{await api(`/marketplace/quotas/${quota.id}/approve`,{method:"POST"});setNotice(`Cota ${quota.group_code}/${quota.quota_code} aprovada — disponível no estoque.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha ao aprovar cota")}}
  async function rejectQuota(quota:Quota){const reason=window.prompt("Motivo da recusa (compliance):");if(!reason)return;setError("");try{await api(`/marketplace/quotas/${quota.id}/reject`,{method:"POST",body:JSON.stringify({reason})});setNotice(`Cota ${quota.group_code}/${quota.quota_code} recusada.`);load()}catch(e){setError(e instanceof Error?e.message:"Falha ao recusar cota")}}
  async function downloadQuotaStatement(quota:Quota){try{await downloadApi(`/marketplace/quotas/${quota.id}/statement`,quota.statement_filename||`extrato-${quota.group_code}-${quota.quota_code}.pdf`)}catch(e){setError(e instanceof Error?e.message:"Extrato indisponível")}}
  const pendingSupplier=items.filter(x=>x.status==="PENDING_REVIEW"&&Boolean(x.supplier_source));
  const stockRows = useMemo(
    () =>
      items.filter(
        (x) =>
          INVENTORY_STOCK_STATUSES.has(x.status) &&
          (categoryFilter === "ALL" || x.category === categoryFilter),
      ),
    [items, categoryFilter],
  );
  const stockSummary = useMemo(() => {
    let credit = 0;
    for (const row of stockRows) {
      const value = Number(row.credit_value);
      if (Number.isFinite(value)) credit += value;
    }
    return { count: stockRows.length, credit };
  }, [stockRows]);
  const fmtDate=(value?:string|null)=>value?new Date(value+"T12:00:00").toLocaleDateString("pt-BR"):"—";
  const categoryLabel =
    categoryFilter === "ALL" ? "Total" : categoryFilter === "REAL_ESTATE" ? "Imóveis" : "Veículos";
  const supplierFilterOptions = useMemo(() => {
    const keys = new Set<string>();
    for (const row of items) {
      if (row.supplier_source) keys.add(row.supplier_source);
    }
    for (const s of suppliers) keys.add(s.source_key);
    return [...keys].sort();
  }, [items, suppliers]);
  const displayedItems = useMemo(() => {
    const needle = inventorySearch.trim().toLowerCase();
    return items.filter((x) => {
      if (categoryFilter !== "ALL" && x.category !== categoryFilter) return false;
      if (supplierFilter === "__manual__" && x.supplier_source) return false;
      if (supplierFilter && supplierFilter !== "__manual__" && x.supplier_source !== supplierFilter) return false;
      if (!needle) return true;
      const supplierName = inventorySupplierLabel(x.supplier_source, suppliers);
      const hay = `${x.group_code} ${x.quota_code} ${supplierName} ${x.supplier_source ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [items, categoryFilter, supplierFilter, inventorySearch, suppliers]);
  return <OperationalLayout title="Inventário (admin)" subtitle="Cadastro interno de cotas, compliance de fornecedores (extrato), varredura Nina e trava de 60 min." icon={<WalletCards/>}>
    <div className="network-metrics" style={{ margin: "0 0 1rem" }}>
      <article>
        <small>Estoque ({categoryLabel}) — cotas</small>
        <strong>{stockSummary.count}</strong>
      </article>
      <article>
        <small>Crédito total ({categoryLabel})</small>
        <strong>{brl.format(stockSummary.credit)}</strong>
      </article>
    </div>
    <div className="marketplace-tabs" style={{ margin: "0 0 1rem", padding: "0 18px" }}>
      {(
        [
          { key: "ALL" as const, label: "Total" },
          { key: "REAL_ESTATE" as const, label: "Imóveis" },
          { key: "VEHICLE" as const, label: "Veículos" },
        ] as const
      ).map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`marketplace-tab${categoryFilter === tab.key ? " active" : ""}`}
          onClick={() => setCategoryFilter(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
    <p className="muted" style={{ fontSize: 10, margin: "0 18px 0.75rem", lineHeight: 1.45 }}>
      Totais consideram cotas <b>disponíveis, reservadas ou em revisão</b> (exclui inativas e vendidas). Use os filtros para localizar cotas por fornecedor, grupo ou número da cota.
    </p>
    <div
      className="quick-form"
      style={{ margin: "0 18px 0.75rem", display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}
    >
      <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, fontWeight: 700, minWidth: 200 }}>
        Fornecedor
        <select value={supplierFilter} onChange={(e) => setSupplierFilter(e.target.value)} style={{ fontWeight: 400, padding: 8 }}>
          <option value="">Todos</option>
          <option value="__manual__">Cadastro manual (sem API)</option>
          {supplierFilterOptions.map((key) => (
            <option key={key} value={key}>{inventorySupplierLabel(key, suppliers)}</option>
          ))}
        </select>
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, fontWeight: 700, flex: "1 1 220px" }}>
        Buscar
        <input
          value={inventorySearch}
          onChange={(e) => setInventorySearch(e.target.value)}
          placeholder="Grupo, cota ou nome do fornecedor"
          style={{ fontWeight: 400, padding: 8 }}
        />
      </label>
      {(supplierFilter || inventorySearch || categoryFilter !== "ALL") && (
        <button
          type="button"
          className="table-action"
          onClick={() => {
            setSupplierFilter("");
            setInventorySearch("");
            setCategoryFilter("ALL");
          }}
        >
          Limpar filtros
        </button>
      )}
      <small className="muted" style={{ alignSelf: "end" }}>{displayedItems.length} cota(s) na lista</small>
    </div>
    <div className="notice"><Clock3/>Fluxo: <b>1.</b> Fornecedor ou admin cadastra cota + extrato · <b>2.</b> Compliance aprova em Inventário · <b>3.</b> Varredura Nina · <b>4.</b> Trava 60 min · <b>5.</b> Proposta · Ofertas do site em <b>Compliance — Vender cota</b></div>
    {pendingSupplier.length>0&&<div className="notice"><CheckCircle2/>{pendingSupplier.length} cota(s) de fornecedor aguardando compliance (revise o extrato antes de aprovar).</div>}
    <form key={formKey} className="quick-form quota-form" onSubmit={submit}><select name="administrator_id" required>{admins.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select><input name="group_code" placeholder="Grupo" required/><input name="quota_code" placeholder="Cota" required/><select name="quota_category_id" title="Subcategoria legado (opcional)"><option value="">Subcategoria (opcional)</option>{subcategories.map(s=><option key={s.id} value={s.id}>{parentLabel(s.parent_id)} — {s.name}</option>)}</select><select name="category"><option value="REAL_ESTATE">Imóvel</option><option value="VEHICLE">Veículo</option></select><CurrencyFormField name="credit_value" placeholder="Crédito (R$)" required/><CurrencyFormField name="premium_value" placeholder="Entrada/ágio (R$)"/><CurrencyFormField name="installment_value" placeholder="Parcela (R$)"/><CurrencyFormField name="outstanding_balance" placeholder="Saldo devedor (R$)"/><input name="installment_due_date" type="date" placeholder="Vencimento parcela" required title="Vencimento da parcela"/><input name="remaining_installments" type="number" min="0" placeholder="Parcelas restantes"/><select name="supplier_source"><option value="">Fornecedor API</option>{suppliers.length?suppliers.map(s=><option key={s.source_key} value={s.source_key}>{s.name} (+{s.markup_percent}%)</option>):(<><option value="FRAGA">Fraga (+3%)</option><option value="BITTELO">Bittelo (+3%)</option><option value="LANCE">Lance (+3%)</option><option value="UNI_CONTEMPLADOS">Uni Contemplados (+10%)</option><option value="CONTEMPLADO_SP">Contemplado SP (+10%)</option><option value="LUME">Lume (+10%)</option></>)}</select><button><Plus/>Cadastrar cota</button></form>
    {notice&&<div className="notice"><CheckCircle2/>{notice}</div>}{error&&<div className="error">{error}</div>}<DataTable headers={["Identificação","Categoria","Crédito","Parcela","Ágio","Vencimento","Extrato","Nina","Status","Ações"]}>{displayedItems.map(x=><tr key={x.id}><td><b>Grupo {x.group_code}</b><small>Cota {x.quota_code} · {inventorySupplierLabel(x.supplier_source, suppliers)}</small>{x.compliance_rejection_reason?<small style={{color:"#a33"}}>Recusa: {x.compliance_rejection_reason}</small>:null}</td><td>{x.quota_category_name?x.quota_category_name:(x.category==="REAL_ESTATE"?"Imóvel":"Veículo")}</td><td>{brl.format(Number(x.credit_value))}</td><td>{brl.format(Number(x.installment_value||0))}</td><td>{brl.format(Number(x.premium_value))}</td><td>{fmtDate(x.installment_due_date)}</td><td>{x.statement_document_id?<button className="table-action" onClick={()=>void downloadQuotaStatement(x)}><Download/>{x.statement_filename||"Baixar"}</button>:<small className="muted">Pendente</small>}</td><td><Pill value={x.nina_scan_status??"PENDENTE"}/></td><td><Pill value={x.status}/></td><td className="actions-cell">{x.status==="PENDING_REVIEW"?<><button className="table-action" onClick={()=>approveQuota(x)} disabled={!x.statement_document_id}><Check/>Aprovar</button><button className="table-action" onClick={()=>rejectQuota(x)}><XCircle/>Recusar</button></>:x.status==="AVAILABLE"?<><button className="table-action" onClick={()=>ninaScan(x)} disabled={!x.installment_due_date}><RefreshCw/>Varredura Nina</button><button className="table-action lock" onClick={()=>reserve(x)} disabled={x.nina_scan_status!=="CLEARED"}><LockKeyhole/>Travar 60 min</button></>:x.status==="RESERVED"?<button className="table-action" onClick={()=>release(x)}><Unlock/>Liberar</button>:x.status==="SOLD"?"Vendida":"—"}</td></tr>)}</DataTable>
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

type MarketplaceCatalogCota = {
  quota_id: string;
  group_code: string;
  quota_code: string;
  credit_value: string;
  entrada_final: string;
  installment_value: string;
  remaining_installments?: number | null;
  administrator_id: string;
  administrator_name: string | null;
  nina_scan_status: string | null;
  label: string;
  status?: string;
  installment_due_date?: string | null;
};

type MarketplaceEsteira1Result = {
  esteira: string;
  eligible: boolean;
  quota: MarketplaceMatch["quotas"][0];
  selected_quotas?: MarketplaceMatch["quotas"];
  combo?: boolean;
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

const ESTEIRA_SEARCH_BAND = 0.1;

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

function noticeAfterProposalCreated(): string {
  return "Linha Flash Capital criada na tabela. Confira valor do bem e prazo nos parâmetros e clique «Calcular memória» na mesma linha.";
}

function noticeBeforeCalculate(): string {
  return "Informe o valor do bem nos parâmetros Flash e clique novamente em «Calcular memória».";
}

function marketplaceProfileValue(profile: Record<string, string>, prefix: "e1" | "e2", key: "income" | "asset" | "year"): string {
  return String(profile[`${prefix}_${key}`] || profile[`e1_${key}`] || profile[`e2_${key}`] || "");
}

function profileValidationMessage(prefix: "e1" | "e2", cat: string, profile: Record<string, string>): string | null {
  if (!parseMoney(marketplaceProfileValue(profile, prefix, "income"))) return "Informe a renda mensal comprovada.";
  if (!parseMoney(marketplaceProfileValue(profile, prefix, "asset"))) return "Informe o valor do bem.";
  if (cat === "VEHICLE" && !marketplaceProfileValue(profile, prefix, "year").trim()) return "Informe o ano do bem (veículo).";
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
  const [catalog,setCatalog]=useState<MarketplaceCatalogCota[]>([]);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [tab,setTab]=useState<"esteira1"|"esteira2">("esteira1");
  const [profile,setProfile]=useState({e1_income:"",e1_asset:"",e1_year:"",e2_income:"",e2_asset:"",e2_year:""});
  const [flags,setFlags]=useState({e1_dirty:false,e1_zero:false,e2_dirty:false,e2_zero:false});
  const [selectedQuotaIds,setSelectedQuotaIds]=useState<string[]>([]);
  const [e1Category,setE1Category]=useState<"REAL_ESTATE"|"VEHICLE">("REAL_ESTATE");
  const [e1FilterCredit,setE1FilterCredit]=useState("");
  const [e1FilterEntrada,setE1FilterEntrada]=useState("");
  const [e1FilterAdministratorId,setE1FilterAdministratorId]=useState("");
  const [targetAmount,setTargetAmount]=useState("");
  const [targetEntrada,setTargetEntrada]=useState("");
  const [category,setCategory]=useState("REAL_ESTATE");
  const [quotaCategories,setQuotaCategories]=useState<{id:string;name:string;legacy_type:number;parent_id:string|null;title_sub:string|null}[]>([]);
  const [e2SubcategoryId,setE2SubcategoryId]=useState("");
  const [e2BankAdmins,setE2BankAdmins]=useState<{id:string;name:string;rules:{is_bank?:boolean}}[]>([]);
  const [e2ClientBankIds,setE2ClientBankIds]=useState<string[]>([]);
  const [e2ClientProblemBankIds,setE2ClientProblemBankIds]=useState<string[]>([]);
  const [result1,setResult1]=useState<MarketplaceEsteira1Result|null>(null);
  const [result2,setResult2]=useState<MarketplaceEsteira2Result|null>(null);
  const [esteira1Busy,setEsteira1Busy]=useState(false);
  const [esteira2Busy,setEsteira2Busy]=useState(false);
  const loadCatalog=(cat:string)=>api<MarketplaceCatalogCota[]>(
    `/marketplace/venda-direta-manual/cotas?category=${encodeURIComponent(cat)}&include_reserved=true`,
  ).then(setCatalog).catch(e=>setError(e.message));
  useEffect(()=>{void loadCatalog(e1Category)},[e1Category]);
  useEffect(()=>{api<{id:string;name:string;legacy_type:number;parent_id:string|null;title_sub:string|null}[]>("/marketplace/quota-categories").then(setQuotaCategories).catch(()=>setQuotaCategories([]))},[]);
  useEffect(()=>{api<{id:string;name:string;rules:{is_bank?:boolean}}[]>("/administrators").then(rows=>setE2BankAdmins(rows.filter(a=>Boolean(a.rules?.is_bank)))).catch(()=>setE2BankAdmins([]))},[]);
  function toggleE2BankId(list:string[],id:string,checked:boolean,setter:(v:string[])=>void){setter(checked?[...list,id]:list.filter(x=>x!==id));}
  const e2Subcategories=useMemo(()=>quotaCategories.filter(c=>c.legacy_type===1),[quotaCategories]);
  const e1FilterActive = parseMoney(e1FilterCredit) > 0 || parseMoney(e1FilterEntrada) > 0 || !!e1FilterAdministratorId;
  const e1AdministratorOptions=useMemo(()=>{
    const map=new Map<string,string>();
    for(const c of catalog){
      if(c.administrator_id) map.set(c.administrator_id,c.administrator_name||"Administradora");
    }
    return [...map.entries()].sort((a,b)=>a[1].localeCompare(b[1],"pt-BR"));
  },[catalog]);
  const e1Catalog=useMemo(()=>{
    const creditTarget=parseMoney(e1FilterCredit);
    const entradaTarget=parseMoney(e1FilterEntrada);
    return catalog
      .filter(c=>{
        if(e1FilterAdministratorId&&c.administrator_id!==e1FilterAdministratorId) return false;
        const credit=Number(c.credit_value);
        const entrada=Number(c.entrada_final);
        return withinSearchBand(credit,creditTarget)&&withinSearchBand(entrada,entradaTarget);
      })
      .sort((a,b)=>Number(a.credit_value)-Number(b.credit_value));
  },[catalog,e1FilterCredit,e1FilterEntrada,e1FilterAdministratorId]);
  const e1SelectableCatalog = e1Catalog.filter((c) => (c.status ?? "AVAILABLE") === "AVAILABLE");
  const e1PendingInCatalog = catalog.filter((c) => c.status === "PENDING_REVIEW");
  const selectedCatalog=e1Catalog.filter(c=>selectedQuotaIds.includes(c.quota_id));
  function toggleEsteira1Quota(c: MarketplaceCatalogCota, checked: boolean) {
    if (checked && (c.status ?? "AVAILABLE") !== "AVAILABLE") {
      setError("Esta cota ainda não está liberada no estoque. Aprove no Inventário (compliance).");
      return;
    }
    if (!checked) {
      setSelectedQuotaIds(ids=>ids.filter(id=>id!==c.quota_id));
      return;
    }
    if (selectedQuotaIds.length > 0) {
      const anchor = catalog.find(x=>x.quota_id===selectedQuotaIds[0]);
      if (anchor && anchor.administrator_id !== c.administrator_id) {
        setError("Junção manual só permite cotas da mesma administradora.");
        return;
      }
    }
    setError("");
    setSelectedQuotaIds(ids=>[...ids,c.quota_id]);
  }
  const profilePayload=(prefix:"e1"|"e2",cat:string)=>{
    const year=marketplaceProfileValue(profile,prefix,"year");
    const assetYear=cat==="VEHICLE"&&year?Number(year):new Date().getFullYear();
    const dirty=flags[`${prefix}_dirty`]||flags.e1_dirty||flags.e2_dirty;
    const zero=flags[`${prefix}_zero`]||flags.e1_zero||flags.e2_zero;
    return {
      monthly_income:String(parseMoney(marketplaceProfileValue(profile,prefix,"income"))),
      monthly_commitment:"0",
      asset_value:String(parseMoney(marketplaceProfileValue(profile,prefix,"asset"))),
      asset_year:assetYear,
      has_credit_restriction:dirty,
      asset_is_zero_km:zero,
    };
  };
  async function assessEsteira1(e:FormEvent){e.preventDefault();setError("");setNotice("");const validation=profileValidationMessage("e1",e1Category,profile);if(validation){setError(validation);return}if(!selectedQuotaIds.length){setError("Selecione ao menos uma carta na lista.");return}setEsteira1Busy(true);try{const data=await api<MarketplaceEsteira1Result>("/marketplace/esteira-1/assess",{method:"POST",body:JSON.stringify({quota_ids:selectedQuotaIds,...profilePayload("e1",e1Category)})},{interactive:true});setResult1(data);setNotice(data.message)}catch(err){setError(err instanceof Error?err.message:"Falha na Esteira 1")}finally{setEsteira1Busy(false)}}
  async function matchEsteira2(e:FormEvent){e.preventDefault();setError("");setNotice("");setResult2(null);const validation=profileValidationMessage("e2",category,profile);if(validation){setError(validation);return}if(!parseMoney(targetAmount)){setError("Informe o crédito desejado.");return}if(!parseMoney(targetEntrada)){setError("Informe a entrada desejada.");return}setEsteira2Busy(true);try{const data=await api<MarketplaceEsteira2Result>("/marketplace/esteira-2/match",{method:"POST",body:JSON.stringify({target_amount:String(parseMoney(targetAmount)),target_entrada:String(parseMoney(targetEntrada)),category,quota_category_id:e2SubcategoryId||null,client_bank_administrator_ids:e2ClientBankIds,client_problem_bank_administrator_ids:e2ClientProblemBankIds,...profilePayload("e2",category)})},{interactive:true});setResult2(data);setNotice(data.message);if(!data.eligible&&data.blockers?.length)setError(data.blockers.join(" "))}catch(err){setError(err instanceof Error?err.message:"Falha na Esteira 2")}finally{setEsteira2Busy(false)}}
  async function reserveQuota(quotaId:string){setError("");try{await api("/reservations",{method:"POST",body:JSON.stringify({quota_id:quotaId,ttl_minutes:60})});setNotice("Cota travada por 60 minutos. Prossiga em Propostas.");void loadCatalog(e1Category)}catch(err){setError(err instanceof Error?err.message:"Falha na trava")}}
  async function reserveSelectedQuotas(ids: string[]) {
    setError("");
    try {
      for (const quotaId of ids) {
        await api("/reservations", { method: "POST", body: JSON.stringify({ quota_id: quotaId, ttl_minutes: 60 }) });
      }
      setNotice(`${ids.length} cota(s) travada(s) por 60 minutos. Prossiga em Propostas.`);
      setResult1(null);
      void loadCatalog(e1Category);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na trava");
    }
  }
  function MatchCard({ match, onReserve }: { match: MarketplaceMatch; onReserve: (id: string) => void }) {
    return (
      <article className="marketplace-match-card">
        <p>
          {match.explanation}
          {match.message ? ` — ${match.message}` : ""}
        </p>
        <small>
          Lane {match.lane ?? "—"} · Score {match.score} · Desvio crédito {match.deviation_percent}%
          {match.entrada_deviation_percent != null ? ` · Desvio entrada ${match.entrada_deviation_percent}%` : ""}
          {match.rollover_applied ? " · Rollover 7d" : ""}
        </small>
        {match.quotas.map((q) => (
          <div className="marketplace-match-quota" key={q.quota_id}>
            <MarketplaceQuotaFields quota={q} administratorFallback={match.administrator_name} />
            <small className="muted" style={{ display: "block", marginTop: 6 }}>
              {q.group_code} · {q.quota_code}
              {q.rollover_applied ? " · rollover na entrada" : ""}
              · Nina {q.nina_scan_status ?? "PENDENTE"}
            </small>
            {q.status === "AVAILABLE" && q.nina_scan_status === "CLEARED" ? (
              <button type="button" className="table-action lock" style={{ marginTop: 8 }} onClick={() => onReserve(q.quota_id)}>
                <LockKeyhole />
                Travar 60 min
              </button>
            ) : null}
          </div>
        ))}
      </article>
    );
  }
  return <OperationalLayout title="Marketplace — Cartas contempladas" subtitle="Esteira 2 (robô): 1 opção na banda de 10% para crédito e 1 para entrada, rollover 7 dias e markup do fornecedor. Regras Bacen via approval_rules sincronizadas." icon={<WalletCards/>}>
    <div className="notice"><Clock3/>Admin cadastra cotas (fornecedor + prazo restante) em <b>Inventário</b>. Sync Bacen em <b>Administradoras</b> alimenta approval_rules usadas no matching. Finalize a venda em <b>Propostas</b>.</div>
    <div className="marketplace-tabs">
      <button type="button" className={`marketplace-tab${tab==="esteira1"?" active":""}`} onClick={()=>setTab("esteira1")}>Esteira 1 — Escolha do parceiro</button>
      <button type="button" className={`marketplace-tab${tab==="esteira2"?" active":""}`} onClick={()=>{setTab("esteira2");setError("")}}>Esteira 2 — Robô Nina</button>
    </div>
    {notice&&<div className="notice"><CheckCircle2/>{notice}</div>}{error&&<div className="error">{error}</div>}
    {tab==="esteira1"&&<form className="marketplace-form" onSubmit={assessEsteira1}>
      <div className="marketplace-subtabs">
        <button type="button" className={`marketplace-tab${e1Category==="REAL_ESTATE"?" active":""}`} onClick={()=>{setE1Category("REAL_ESTATE");setSelectedQuotaIds([]);setE1FilterAdministratorId("");setE1FilterCredit("");setE1FilterEntrada("")}}>Imóvel</button>
        <button type="button" className={`marketplace-tab${e1Category==="VEHICLE"?" active":""}`} onClick={()=>{setE1Category("VEHICLE");setSelectedQuotaIds([]);setE1FilterAdministratorId("");setE1FilterCredit("");setE1FilterEntrada("")}}>Veículo</button>
      </div>
      <div className="marketplace-form-row">
        <label className="marketplace-field marketplace-field-wide">
          Administradora
          <select
            value={e1FilterAdministratorId}
            onChange={(e) => {
              setE1FilterAdministratorId(e.target.value);
              setSelectedQuotaIds([]);
            }}
          >
            <option value="">Todas as administradoras</option>
            {e1AdministratorOptions.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <p className="marketplace-e1-hint">
          Passo a passo: escolha <strong>imóvel ou veículo</strong>, depois a <strong>administradora</strong> (ou todas).
          A lista abaixo mostra só cotas desse tipo de bem
          {e1FilterAdministratorId ? " e dessa administradora" : ""}.
        </p>
      </div>
      <div className="marketplace-form-row">
        <label className="marketplace-field"><span className="marketplace-field-label"><Search size={14}/> Refinar por crédito (R$)</span><CurrencyInput value={e1FilterCredit} onChange={setE1FilterCredit} placeholder="Opcional — ex.: 250.000"/></label>
        <label className="marketplace-field"><span className="marketplace-field-label"><Search size={14}/> Refinar por entrada (R$)</span><CurrencyInput value={e1FilterEntrada} onChange={setE1FilterEntrada} placeholder="Opcional — ex.: 80.000"/></label>
        <small className="marketplace-hint">Crédito e entrada: tolerância ±10% (opcional). Deixe em branco para listar todas da administradora escolhida.</small>
        {e1FilterActive ? (
          <button type="button" className="table-action" style={{ marginTop: 6 }} onClick={() => { setE1FilterCredit(""); setE1FilterEntrada(""); setE1FilterAdministratorId(""); setSelectedQuotaIds([]); }}>
            Limpar filtros de busca
          </button>
        ) : null}
      </div>
      <div className="marketplace-form-row">
        <div className="marketplace-field marketplace-field-wide quota-pick-list">
          <b>
            Cartas disponíveis (marque uma ou mais — junção só na mesma administradora)
            {e1SelectableCatalog.length ? ` · ${e1SelectableCatalog.length} liberada(s)` : ""}
            {e1Catalog.length > e1SelectableCatalog.length ? ` · ${e1Catalog.length - e1SelectableCatalog.length} aguardando aprovação` : ""}
          </b>
          <div className="quota-pick-scroll" style={{ maxHeight: 240 }}>
            {e1Catalog.length === 0 ? (
              <small className="muted">
                {catalog.length === 0
                  ? `Nenhuma carta de ${e1Category === "REAL_ESTATE" ? "imóvel" : "veículo"} no estoque. Cadastre em Inventário ou sincronize Fornecedores e aprove a cota (compliance).`
                  : e1FilterActive
                    ? `Há ${catalog.length} carta(s) no estoque, mas nenhuma combina os filtros (crédito/entrada ±10% ou administradora). Limpe os filtros ou ajuste os valores.`
                    : "Nenhuma carta nesta categoria. Cadastre no Inventário."}
                {catalog.length > 0 && catalog.every((c) => c.status === "PENDING_REVIEW") ? (
                  <> {e1PendingInCatalog.length} cota(s) aguardam aprovação no Inventário antes de liberar para venda.</>
                ) : null}
              </small>
            ) : (
              e1Catalog.map((c) => {
                const selectable = (c.status ?? "AVAILABLE") === "AVAILABLE";
                return (
                  <label
                    key={c.quota_id}
                    className={`quota-pick-row quota-pick-row--detail${selectable ? "" : " muted"}`}
                    style={{ opacity: selectable ? 1 : 0.75 }}
                  >
                    <input
                      type="checkbox"
                      disabled={!selectable}
                      checked={selectedQuotaIds.includes(c.quota_id)}
                      onChange={(e) => toggleEsteira1Quota(c, e.target.checked)}
                    />
                    <span>
                      <MarketplaceQuotaFields quota={c} />
                      <small className="muted" style={{ display: "block", marginTop: 4 }}>
                        {c.group_code} · {c.quota_code}
                        {!selectable ? " · aguardando aprovação (Inventário)" : ""}
                        {c.status === "RESERVED" ? " · reservada" : ""}
                      </small>
                    </span>
                  </label>
                );
              })
            )}
          </div>
          {selectedCatalog.length > 0 && (
            <div className="notice" style={{ marginTop: 8 }}>
              {selectedCatalog.length} carta(s) · {selectedCatalog[0].administrator_name ?? "Adm."} · crédito total{" "}
              {brl.format(selectedCatalog.reduce((s, c) => s + Number(c.credit_value), 0))}
            </div>
          )}
        </div>
        <ClientProfileFields prefix="e1" category={e1Category} values={profile} flags={flags} onChange={(k,v)=>setProfile(p=>({...p,[k]:v}))} onFlag={(k,v)=>setFlags(p=>({...p,[k]:v}))}/>
        <button type="submit" className="marketplace-submit" disabled={!selectedQuotaIds.length||esteira1Busy}><RefreshCw className={esteira1Busy?"spin":undefined}/>{esteira1Busy?"Analisando com Nina…":"Analisar com Nina"}</button>
      </div>
    </form>}
    {tab==="esteira2"&&<form className="marketplace-form" onSubmit={matchEsteira2}>
      <div className="marketplace-form-row">
        <label className="marketplace-field">Crédito desejado (R$)<CurrencyInput value={targetAmount} onChange={setTargetAmount} required/></label>
        <label className="marketplace-field">Entrada desejada (R$)<CurrencyInput value={targetEntrada} onChange={setTargetEntrada} required/></label>
        <label className="marketplace-field marketplace-field-compact">Categoria<select value={category} onChange={e=>setCategory(e.target.value)}><option value="REAL_ESTATE">Imóvel</option><option value="VEHICLE">Veículo</option></select></label>
        <label className="marketplace-field marketplace-field-compact">Subcategoria<select value={e2SubcategoryId} onChange={e=>setE2SubcategoryId(e.target.value)}><option value="">Todas (tipo de bem)</option>{e2Subcategories.map(s=>{const p=quotaCategories.find(x=>x.id===s.parent_id);return<option key={s.id} value={s.id}>{p?(p.title_sub||p.name)+" — ":""}{s.name}</option>})}</select></label>
        <ClientProfileFields prefix="e2" category={category} values={profile} flags={flags} onChange={(k,v)=>setProfile(p=>({...p,[k]:v}))} onFlag={(k,v)=>setFlags(p=>({...p,[k]:v}))}/>
        {e2BankAdmins.length>0&&<div className="marketplace-form-row" style={{flexDirection:"column",alignItems:"stretch",gap:8}}><small className="muted">Bancos administradores: correntista ou restrição com a administradora.</small><div style={{display:"flex",flexWrap:"wrap",gap:"12px 20px"}}>{e2BankAdmins.map(adm=><div key={adm.id} style={{minWidth:200}}><b style={{fontSize:11}}>{adm.name}</b><label style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginTop:4}}><input type="checkbox" checked={e2ClientBankIds.includes(adm.id)} onChange={e=>toggleE2BankId(e2ClientBankIds,adm.id,e.target.checked,setE2ClientBankIds)}/>Cliente correntista</label><label style={{display:"flex",alignItems:"center",gap:6,fontSize:11,marginTop:2}}><input type="checkbox" checked={e2ClientProblemBankIds.includes(adm.id)} onChange={e=>toggleE2BankId(e2ClientProblemBankIds,adm.id,e.target.checked,setE2ClientProblemBankIds)}/>Restrição / inadimplência</label></div>)}</div></div>}
        <button type="submit" className="marketplace-submit" disabled={esteira2Busy}><RefreshCw className={esteira2Busy?"spin":undefined}/>{esteira2Busy?"Buscando opções robô…":"Buscar opções robô"}</button>
      </div>
    </form>}
    {esteira2Busy&&tab==="esteira2"&&<div className="notice"><Clock3/>Robô Nina consultando o estoque e as regras Bacen — pode levar alguns segundos na primeira busca do dia.</div>}
    {result1&&tab==="esteira1"&&<section className="panel"><div className="panel-title"><h2>Resultado Esteira 1{result1.combo?" (junção manual)":""}</h2></div><div className="notice">{result1.message}</div>{result1.blockers.length>0&&<div className="error">{result1.blockers.map(b=><div key={b}>{b}</div>)}</div>}{(result1.selected_quotas??[result1.quota]).map(q=><div key={q.quota_id} className="marketplace-match-card" style={{marginTop:12}}><Pill value={result1.eligible?"CLEARED":"BLOCKED"}/><div style={{marginTop:10}}><MarketplaceQuotaFields quota={q}/></div></div>)}{result1.eligible&&(result1.selected_quotas??[result1.quota]).every(q=>q.status==="AVAILABLE"&&q.nina_scan_status==="CLEARED")?<button type="button" className="table-action lock" onClick={()=>void reserveSelectedQuotas((result1.selected_quotas??[result1.quota]).map(q=>q.quota_id))}><LockKeyhole/>Travar 60 min{(result1.selected_quotas?.length??1)>1?` (${result1.selected_quotas?.length} cotas)`:""}</button>:null}{result1.alternatives.length>0&&<><h3>Alternativas Nina</h3>{result1.alternatives.map(m=><MatchCard key={m.quota_ids.join("-")} match={m} onReserve={reserveQuota}/>)}</>}</section>}
    {result2&&tab==="esteira2"&&!esteira2Busy&&<section className="panel"><div className="panel-title"><h2>Opções robô Esteira 2 (régua {result2.band_percent??"10"}%)</h2></div><div className="notice">{result2.message}</div>{(result2.blockers??[]).map(b=><div className="error" key={b}>{b}</div>)}{(result2.credit_matches?.length??0)>0&&<h3>Lane crédito</h3>}{(result2.credit_matches??[]).map(m=><MatchCard key={`c-${m.quota_ids.join("-")}`} match={m} onReserve={reserveQuota}/>)}{(result2.entrada_matches?.length??0)>0&&<h3>Lane entrada</h3>}{(result2.entrada_matches??[]).map(m=><MatchCard key={`e-${m.quota_ids.join("-")}`} match={m} onReserve={reserveQuota}/>)}{!(result2.credit_matches?.length||result2.entrada_matches?.length)&&result2.matches.map(m=><MatchCard key={m.quota_ids.join("-")} match={m} onReserve={reserveQuota}/>)}</section>}
  </OperationalLayout>
}

const PROPOSALS_SIM_PRODUCT = "FLASH_CREDIT";

export function ProposalsModule() {
  const [items, setItems] = useState<Proposal[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [clients, setClients] = useState<CommercialClient[]>([]);
  const [isCommercial, setIsCommercial] = useState(false);
  const [isLetterOps, setIsLetterOps] = useState(false);
  const [activeProposalId, setActiveProposalId] = useState<string | null>(null);
  const [calculatedProposalIds, setCalculatedProposalIds] = useState<Set<string>>(() => new Set());
  const [notice, setNotice] = useState("");
  const [proposalError, setProposalError] = useState("");
  const [selectedLeadId, setSelectedLeadId] = useState("");
  const [highlightProposalId, setHighlightProposalId] = useState<string | null>(null);
  const proposalsTableRef = useRef<HTMLDivElement>(null);
  const [requestedAmount, setRequestedAmount] = useState("");
  const [poolInvestmentAmount, setPoolInvestmentAmount] = useState("");
  const [assetValue, setAssetValue] = useState("");
  const [capitalSource, setCapitalSource] = useState("RETAIL");
  const [flashPoolInvestorRate, setFlashPoolInvestorRate] = useState("");
  const [term, setTerm] = useState(36);
  const [lastCalculation, setLastCalculation] = useState<Calculation | null>(null);
  const [flashIpcaAnnual, setFlashIpcaAnnual] = useState("4.5");

  useEffect(() => {
    api<{ default_ipca_projected_percent?: string }>("/finops/flash-capital/simulation-params")
      .then((p) => {
        if (p.default_ipca_projected_percent) setFlashIpcaAnnual(p.default_ipca_projected_percent);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const id = new URLSearchParams(window.location.search).get("lead_id");
    if (id) setSelectedLeadId(id);
  }, []);

  const poolRatePreview = useMemo(() => {
    const amount = Number(poolInvestmentAmount);
    if (!amount || amount <= 0) return null;
    return { rate: "1,6" };
  }, [poolInvestmentAmount]);

  const flashProposals = useMemo(
    () => items.filter((p) => p.product === PROPOSALS_SIM_PRODUCT),
    [items],
  );

  const refreshCalculatedFlags = async (proposals: Proposal[]) => {
    const ids = new Set<string>();
    await Promise.all(
      proposals.map(async (p) => {
        try {
          const calcs = await api<{ id: string }[]>(`/proposals/${p.id}/calculations`);
          if (calcs.length) ids.add(p.id);
        } catch {
          /* ignore */
        }
      }),
    );
    setCalculatedProposalIds(ids);
  };

  const load = () =>
    Promise.all([
      api<User>("/auth/me"),
      api<Proposal[]>("/proposals"),
      api<Lead[]>("/leads"),
      api<Contract[]>("/contracts"),
    ]).then(async ([me, p, l, c]) => {
      setItems(p);
      setLeads(l);
      setContracts(c);
      const flashOnly = p.filter((row) => row.product === PROPOSALS_SIM_PRODUCT);
      void refreshCalculatedFlags(flashOnly);
      const commercial = ["MASTER_FRANCHISEE", "MANAGER", "PARTNER", "QUOTA_SELLER"].includes(me.role);
      setIsCommercial(commercial);
      setIsLetterOps(me.role === "PLATFORM_ADMIN" || me.role === "INTERNAL_STAFF");
      if (commercial) {
        try {
          setClients(await api<CommercialClient[]>("/commercial/clients"));
        } catch {
          setClients([]);
        }
      } else {
        setClients([]);
      }
    });

  useEffect(() => {
    void load();
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setProposalError("");
    setNotice("");
    const fd = new FormData(e.currentTarget);
    const amount = parseMoney(requestedAmount);
    if (!amount) {
      setProposalError("Informe o valor solicitado (R$).");
      return;
    }
    const leadId = selectedLeadId.trim();
    if (!leadId) {
      setProposalError(
        leads.length
          ? "Selecione o cadastro do cliente no campo acima."
          : "Cadastre um lead no CRM ou use Cadastros / Venda Direta antes de simular.",
      );
      return;
    }
    const clientId = String(fd.get("client_user_id") || "");
    try {
      const created = await api<Proposal>("/proposals", {
        method: "POST",
        body: JSON.stringify({
          lead_id: leadId,
          product: PROPOSALS_SIM_PRODUCT,
          requested_amount: String(amount),
          client_user_id: clientId || undefined,
          sale_channel: isCommercial ? "PARTNER_OFFICE" : undefined,
          terms: { channel: isCommercial ? "PARTNER_OFFICE" : "SELF_SERVICE" },
        }),
      });
      setHighlightProposalId(created.id);
      setActiveProposalId(created.id);
      setRequestedAmount("");
      await load();
      if (parseMoney(assetValue)) {
        await calculate(created);
      } else {
        setNotice(noticeAfterProposalCreated());
        proposalsTableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : "Não foi possível criar a proposta.");
    }
  }

  async function calculate(p: Proposal) {
    setNotice("");
    setProposalError("");
    setActiveProposalId(p.id);
    if (p.product !== PROPOSALS_SIM_PRODUCT) {
      setNotice("Esta tela simula apenas Flash Capital. Use as mesas SDC e Marketplace nos módulos dedicados.");
      return;
    }
    if (!parseMoney(assetValue)) {
      setNotice(noticeBeforeCalculate());
      document.querySelector(".product-parameters")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    try {
      const flashSource = isCommercial || isLetterOps ? "RETAIL" : capitalSource;
      const fundSource = flashSource === "INSTITUTIONAL";
      const payload: Record<string, unknown> = {
        asset_value: assetValue,
        capital_source: flashSource,
        term_months: term,
        ipca_annual_percent: fundSource ? flashIpcaAnnual : "0",
      };
      if (flashSource === "RETAIL" && !isCommercial && !isLetterOps) {
        if (poolInvestmentAmount) payload.pool_investment_amount = poolInvestmentAmount;
        if (flashPoolInvestorRate) payload.pool_investor_rate_percent = flashPoolInvestorRate;
      }
      const calc = await api<Calculation>(`/proposals/${p.id}/calculate-flash-credit`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setLastCalculation(calc);
      setHighlightProposalId(p.id);
      setCalculatedProposalIds((prev) => new Set(prev).add(p.id));
      setNotice(
        isCommercial
          ? `Simulação ${calc.formula_version} — valores resumidos acima (sem geração de contrato nesta tela).`
          : `Memória ${calc.formula_version} criada — agora pode «Gerar contrato» nesta linha.`,
      );
      void load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Falha no cálculo";
      setProposalError(msg);
      setNotice("");
    }
  }

  async function quickCreateLead() {
    setProposalError("");
    const name = window.prompt("Nome do cliente (obrigatório para simular):");
    if (!name?.trim()) return;
    const phone = window.prompt("WhatsApp do cliente:") || "";
    if (!phone.trim() || phone.trim().length < 8) {
      setProposalError("Informe um WhatsApp válido para cadastrar o cliente.");
      return;
    }
    try {
      const lead = await api<Lead>("/leads", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          phone: phone.trim(),
          product_interest: "FLASH_CREDIT",
          source: "DASHBOARD",
        }),
      });
      setSelectedLeadId(lead.id);
      setNotice(`Cliente «${lead.name}» cadastrado. Agora informe o valor solicitado e adicione a simulação.`);
      await load();
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : "Não foi possível cadastrar o cliente.");
    }
  }

  async function contract(p: Proposal) {
    setActiveProposalId(p.id);
    const calcs = await api<{ id: string }[]>(`/proposals/${p.id}/calculations`);
    if (!calcs.length) {
      setNotice(
        p.product === "FLASH_CREDIT"
          ? "Esta linha Flash ainda não foi calculada. Ajuste valor do bem/prazo e use «Calcular memória» nesta linha."
          : p.product === "SDC"
            ? "Esta linha SDC ainda não foi calculada. Marque as cotas acima e use «Calcular memória» nesta linha."
            : "Calcule a memória nesta linha antes de gerar o contrato.",
      );
      document.querySelector(".product-parameters")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    setCalculatedProposalIds((prev) => new Set(prev).add(p.id));
    await api(`/proposals/${p.id}/contracts`, {
      method: "POST",
      body: JSON.stringify({ calculation_memory_id: calcs[0].id }),
    });
    setNotice("Contrato gerado com hash de integridade.");
    void load();
  }

  const pageTitle = "Simulador Flash Capital";
  const pageSubtitle = isCommercial
    ? "Simulação resumida para o cliente. Cartas contempladas: Venda Direta e Cadastros. SDC: mesa SDC — Capital de Giro."
    : "Apenas Flash Capital nesta tela. SDC e Marketplace têm módulos próprios; aqui simule, calcule memória e gere contrato.";
  const showPoolCapitalParams = !isCommercial && !isLetterOps;
  const assetReady = parseMoney(assetValue) > 0;

  return (
    <OperationalLayout title={pageTitle} subtitle={pageSubtitle} icon={<FileText />}>
      <div className="notice">
        <Clock3 />
        <div>
          <b>Como usar</b>
          <small style={{ display: "block", marginTop: "0.35rem", lineHeight: 1.5 }}>
            <b>Passo 1</b> — Selecione o <em>cadastro</em> do cliente e o <em>valor solicitado</em>; clique em{" "}
            <em>Adicionar simulação</em> (a linha Flash aparece na tabela).
            <br />
            <b>Passo 2</b> — Informe <em>valor do bem</em> e <em>prazo</em> nos parâmetros. Clique{" "}
            <em>Calcular memória</em> na <b>mesma linha</b> da tabela.
            <br />
            {isCommercial ? (
              <>
                <b>Passo 3</b> — Use o resumo da memória para apresentar ao cliente. Contrato e operação completa ficam com a
                matriz.
                <br />
                <b>Marketplace</b> — use{" "}
                <Link href="/modules/venda-direta-manual">Venda Direta Manual</Link> ou{" "}
                <Link href="/modules/cadastros">Cadastros</Link>.
              </>
            ) : (
              <>
                <b>Passo 3</b> — <em>Gerar contrato</em> só na linha que já tiver memória calculada (botão fica ativo).
              </>
            )}
            {!isCommercial ? (
              <>
                <br />
                <b>Marketplace</b> — exige cotas travadas no inventário antes do contrato.
              </>
            ) : null}
            <br />
            <b>SDC</b> — <Link href="/modules/sdc">SDC — Capital de Giro</Link>. · <b>Marketplace</b> —{" "}
            <Link href="/modules/venda-direta-manual">Venda Direta</Link> / <Link href="/modules/cadastros">Cadastros</Link>.
            · <b>Flash operação</b> — <Link href="/modules/flash-capital">Flash Capital</Link>.
          </small>
        </div>
      </div>
      <form className="quick-form" onSubmit={submit}>
        {isCommercial && clients.length > 0 && (
          <select name="client_user_id">
            <option value="">Cliente no escritório (opcional)</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
        <select
          value={selectedLeadId}
          onChange={(e) => setSelectedLeadId(e.target.value)}
          required
          aria-label="Cadastro do cliente"
        >
          <option value="">
            {leads.length ? "Selecione o cadastro do cliente *" : "Nenhum cadastro — cadastre o cliente abaixo"}
          </option>
          {leads.map((l) => (
            <option value={l.id} key={l.id}>
              {l.name}
            </option>
          ))}
        </select>
        <button type="button" className="table-action" onClick={() => void quickCreateLead()}>
          <Plus />
          Cadastrar cliente
        </button>
        <Link href="/modules/crm" className="table-action" style={{ display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
          CRM completo
        </Link>
        <CurrencyInput value={requestedAmount} onChange={setRequestedAmount} placeholder="Valor solicitado (R$) *" />
        <CurrencyInput value={assetValue} onChange={setAssetValue} placeholder="Valor do bem (R$) *" />
        <select value={term} onChange={(e) => setTerm(Number(e.target.value))} aria-label="Prazo">
          <option value={36}>Prazo 36 meses</option>
          <option value={60}>Prazo 60 meses + balão</option>
        </select>
        <button type="submit">
          <Plus />
          Adicionar simulação
        </button>
      </form>
      {proposalError && <div className="error">{proposalError}</div>}
      <div className="product-parameters">
          <div>
            <b>Parâmetros — Flash Capital</b>
            <small>
              {isCommercial || isLetterOps
                ? "Operação LETTER: fruição 2,5% a.m. (Tabela Price). Origem do capital e pool são definidos pela matriz — use valor do bem e prazo no formulário acima."
                : showPoolCapitalParams
                  ? "Fruição 2,5% a.m. (Tabela Price) · Pool opcional abaixo."
                  : "Fruição 2,5% a.m. (Tabela Price)."}
            </small>
          </div>
              {!assetReady && (
                <div className="error" style={{ margin: 0, gridColumn: "1 / -1" }}>
                  Informe o <b>valor do bem</b> no formulário acima para habilitar «Calcular memória» na tabela.
                </div>
              )}
              {showPoolCapitalParams && (
                <label>
                  Flash Capital — origem
                  <select value={capitalSource} onChange={(e) => setCapitalSource(e.target.value)}>
                    {FLASH_CAPITAL_SOURCES.map((x) => (
                      <option key={x.value} value={x.value}>
                        {x.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {showPoolCapitalParams && capitalSource === "INSTITUTIONAL" && (
                <div className="notice">
                  <small>
                    Origem fundo: IPCA anual projetado {flashIpcaAnnual}% na memória (fruição 2,5% a.m. inalterada).
                  </small>
                </div>
              )}
              {showPoolCapitalParams && capitalSource === "RETAIL" && (
                <>
                  <label>
                    Pool — valor aplicado (R$) — opcional
                    <CurrencyInput value={poolInvestmentAmount} onChange={setPoolInvestmentAmount} />
                    <small>Só para simular rentabilidade do pool (1,6% a.m.). Não é obrigatório para a memória Flash.</small>
                  </label>
                  {poolRatePreview && (
                    <div className="notice">
                      <RefreshCw />
                      Rentabilidade pool: {poolRatePreview.rate}% a.m. (livre de imposto)
                    </div>
                  )}
                  <label>
                    Flash — override campanha (% a.m., opcional)
                    <input
                      type="number"
                      min="0"
                      max="2.5"
                      step="0.1"
                      value={flashPoolInvestorRate}
                      onChange={(e) => setFlashPoolInvestorRate(e.target.value)}
                      placeholder="Deixe vazio para 1,6% padrão"
                    />
                  </label>
                </>
              )}
        </div>
      {notice && (
        <div className="notice">
          <RefreshCw />
          {notice}
        </div>
      )}
      {lastCalculation && <CalculationResult calculation={lastCalculation} hidePlatformFee />}
      <div ref={proposalsTableRef}>
        <DataTable headers={["Produto", "Valor", "Canal", "Comissão", "Parceiro", "Status", "Workflow"]}>
          {flashProposals.map((p) => {
            const hasContract = contracts.some((c) => c.proposal_id === p.id);
            const hasMemory = calculatedProposalIds.has(p.id);
            const rowActive = activeProposalId === p.id || highlightProposalId === p.id;
            return (
              <tr
                key={p.id}
                style={
                  rowActive ? { background: "rgba(34, 197, 94, 0.08)" } : undefined
                }
              >
                <td>
                  <b>{productLabel(p.product)}</b>
                  <small>{p.lead_name ?? leads.find((l) => l.id === p.lead_id)?.name}</small>
                </td>
                <td>{brl.format(Number(p.requested_amount))}</td>
                <td>
                  <small>{p.sale_channel ?? "—"}</small>
                </td>
                <td>
                  <b>{p.commission_originator_name ?? "—"}</b>
                </td>
                <td>
                  <b>{p.owner_name ?? "—"}</b>
                  <small>{p.served_by_name ? `Atend.: ${p.served_by_name}` : p.owner_role ?? ""}</small>
                </td>
                <td>
                  <Pill value={p.status} />
                </td>
                <td className="actions-cell">
                  <button
                    type="button"
                    className="table-action"
                    disabled={!assetReady}
                    title={
                      assetReady
                        ? "Gera memória de cálculo Flash desta linha"
                        : "Informe o valor do bem no formulário superior"
                    }
                    onClick={() => void calculate(p)}
                  >
                    Calcular memória
                  </button>
                  {!isCommercial && (
                    <button
                      type="button"
                      className="table-action"
                      disabled={hasContract || !hasMemory}
                      title={!hasMemory ? "Calcule a memória nesta linha antes" : undefined}
                      onClick={() => void contract(p)}
                    >
                      {hasContract ? "Contrato criado" : "Gerar contrato"}
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </DataTable>
      </div>
    </OperationalLayout>
  );
}

const CALC_HIDDEN_PLATFORM_FEE_KEYS = new Set(["platform_fee", "structuring_fee"]);

function CalculationResult({
  calculation,
  hidePlatformFee = true,
}: {
  calculation: Calculation;
  hidePlatformFee?: boolean;
}) {
  const labels: Record<string, string> = {
    principal: "Principal (nominal)",
    total_interest: "Juros totais",
    investor_interest: "Investidores",
    platform_spread: "Spread LETTER",
    maturity_total: "Total no vencimento",
    start_fee_total: "Taxa de Start",
    start_fee_milestone_1: "Marco 1",
    start_fee_milestone_2: "Marco 2",
    intermediation_fee: "Fee 10%",
    capital_commission: "Captação 1%",
    asset_value: "Valor do bem",
    ltv_percent: "LTV (%)",
    monthly_payment: "Parcela",
    balloon_payment: "Parcela balão",
    management_fee_total: "Gestão 0,5%",
    itbi_provision: "Provisão ITBI",
    platform_fee: "Fee plataforma",
    structuring_fee: "Fee plataforma",
    partner_commission_base: "Base comissão rede",
    net_payout: "Payout líquido",
    total_contract: "Total do contrato",
    pool_investor_rate_percent: "Rentabilidade pool (% a.m.)",
    pool_investor_tier_label: "Faixa pool",
    pool_investor_tax_status: "Status fiscal pool",
    investor_rate_percent: "Rentabilidade investidor (% a.m.)",
    platform_spread_rate_percent: "Spread plataforma (% a.m.)",
  };
  const entries = Object.entries(calculation.output).filter(
    ([key, value]) =>
      labels[key] &&
      value !== null &&
      !(hidePlatformFee && CALC_HIDDEN_PLATFORM_FEE_KEYS.has(key)),
  );const notes=[calculation.output.partner_commission_basis_note,calculation.output.interest_basis_note,calculation.output.pool_investor_tax_note].filter(x=>typeof x==="string");const quitconContext=calculation.formula_version.startsWith("sdc-")&&calculation.quitcon_sdc?{proposalId:calculation.proposal_id,calculationMemoryId:calculation.id,mesesRestantes:Number(calculation.output.duration_months??calculation.input.duration_months??0)||undefined}:undefined;return <div className="calculation-result"><div><span className="eyebrow dark">MEMÓRIA VERSIONADA</span><b>{calculation.formula_version}</b></div>{notes.map((note,i)=><small key={i}>{String(note)}</small>)}<div>{entries.map(([key,value])=><article key={key}><small>{labels[key]}</small><strong>{key.includes("percent")||key==="pool_investor_rate_percent"?`${value}%`:key==="pool_investor_tax_status"?"Livre de imposto (sem retenção)":key.includes("tier")?String(value):brl.format(Number(value))}</strong></article>)}</div>{calculation.quitcon_sdc&&<SdcQuitConProjectionTable data={calculation.quitcon_sdc} context={quitconContext}/>}</div>}

function OperationalLayout({title,subtitle,icon,children}:{title:string;subtitle:string;icon:React.ReactNode;children:React.ReactNode}){return <><div className="page-heading"><div><span className="eyebrow dark">OPERAÇÃO ATIVA</span><h1>{title}</h1><p>{subtitle}</p></div><div className="operational-icon">{icon}</div></div><section className="panel operational-panel">{children}</section></>}
function DataTable({headers,children}:{headers:string[];children:React.ReactNode}){return <div className="table-wrap"><table className="data-table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>}
const PILL_LABELS_PT: Record<string, string> = {
  AVAILABLE: "Disponível",
  RESERVED: "Reservada",
  PENDING_REVIEW: "Em revisão",
  SOLD: "Vendida",
  INACTIVE: "Inativa",
  CLEARED: "Aprovada (Nina)",
  BLOCKED: "Bloqueada (Nina)",
  PENDENTE: "Pendente",
  NEW: "Novo",
  CONTACTED: "Contatado",
  QUALIFIED: "Qualificado",
  PROPOSAL: "Proposta",
  CONVERTED: "Convertido",
  ACTIVE: "Ativa",
  APPROVED: "Aprovado",
  REJECTED: "Reprovado",
};

function pillLabelPt(value: string): string {
  const key = value.trim().toUpperCase();
  return PILL_LABELS_PT[key] ?? value.replaceAll("_", " ");
}

function Pill({value}:{value:string}){return <span className={`pill pill-${value.toLowerCase()}`}>{pillLabelPt(value)}</span>}
