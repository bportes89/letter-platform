"use client";

import { ArrowRight, CheckCircle2, Clock3, Construction, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Module } from "@/lib/api";
import { InventoryModule, LeadsModule, ProposalsModule } from "@/components/operational-modules";
import { ContractsModule, PaymentsModule, WalletModule } from "@/components/financial-modules";
import { ComplianceModule, IdentityModule, SecurityModule } from "@/components/identity-modules";
import { FundingModule, NetworkModule } from "@/components/network-funding-modules";
import { CollectionsModule } from "@/components/collections-module";
import { AuctionsModule } from "@/components/auctions-module";
import { CommunicationsModule, TaxTechModule } from "@/components/tax-communications-modules";
import { BIModule, NinaModule } from "@/components/nina-bi-modules";
import { OperationsModule } from "@/components/operations-module";

export default function ModulePage() {
  const {key}=useParams<{key:string}>(); const [module,setModule]=useState<Module|null>(null);
  useEffect(()=>{api<Module[]>("/modules").then(items=>setModule(items.find(i=>i.key===key)??null))},[key]);
  if(!module)return <div className="loading">Carregando módulo...</div>;
  if(key==="crm")return <LeadsModule/>;
  if(key==="inventory")return <InventoryModule/>;
  if(key==="proposals")return <ProposalsModule/>;
  if(key==="contracts")return <ContractsModule/>;
  if(key==="wallet")return <WalletModule/>;
  if(key==="payments")return <PaymentsModule/>;
  if(key==="identity")return <IdentityModule/>;
  if(key==="rbac")return <SecurityModule/>;
  if(key==="admin")return <ComplianceModule/>;
  if(key==="mmn")return <NetworkModule/>;
  if(key==="funding")return <FundingModule/>;
  if(key==="collections")return <CollectionsModule/>;
  if(key==="auctions")return <AuctionsModule/>;
  if(key==="taxtech")return <TaxTechModule/>;
  if(key==="communications")return <CommunicationsModule/>;
  if(key==="nina")return <NinaModule/>;
  if(key==="reports")return <BIModule/>;
  if(key==="operations")return <OperationsModule/>;
  return <>
    <div className="page-heading"><div><span className="eyebrow dark">MÓDULO LETTER</span><h1>{module.name}</h1><p>{module.description}</p></div><Status status={module.status}/></div>
    <div className="module-hero"><div><Construction/><h2>Fundação do módulo criada</h2><p>Este módulo já está integrado à navegação, identidade, organização, RBAC e auditoria da plataforma. As jornadas específicas serão ativadas conforme o roadmap.</p><button className="primary-button">Consultar roadmap <ArrowRight/></button></div><div className="module-checklist"><h3>Controles herdados</h3>{['Isolamento por organização','Permissões por escopo','Trilha de auditoria','Integrações por adaptadores','Testes e observabilidade'].map(x=><span key={x}><CheckCircle2/>{x}</span>)}</div></div>
    <section className="panel"><div className="panel-title"><div><span className="eyebrow dark">PRÓXIMAS ENTREGAS</span><h2>Backlog do módulo</h2></div></div><div className="backlog-grid">{['Modelo de dados e regras canônicas','Endpoints e políticas de acesso','Jornadas e telas operacionais','Testes de integração e homologação'].map((x,i)=><div className="backlog-item" key={x}><span>0{i+1}</span><div><strong>{x}</strong><p>{i===0?'Em preparação para a próxima evolução':'Planejado no roadmap da plataforma'}</p></div><Clock3/></div>)}</div></section>
  </>;
}

function Status({status}:{status:string}) { const label:Record<string,string>={ACTIVE:'Ativo',FOUNDATION:'Fundação pronta',ADAPTER_REQUIRED:'Aguardando fornecedor',COMPLIANCE_REQUIRED:'Aguardando compliance'}; return <span className={`status ${status.toLowerCase()}`}><ShieldCheck/>{label[status]??status}</span> }
