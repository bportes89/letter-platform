"use client";

import { ArrowUpRight, BrainCircuit, CircleDollarSign, FileCheck2, ShieldAlert, Users, WalletCards } from "lucide-react";
import { useEffect, useState } from "react";
import { api, Summary } from "@/lib/api";

const money = new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"});

export default function Dashboard() {
  const [data,setData]=useState<Summary|null>(null);
  useEffect(()=>{api<Summary>("/dashboard").then(setData)},[]);
  return <>
    <div className="page-heading"><div><span className="eyebrow dark">VISÃO EXECUTIVA</span><h1>Centro de operações</h1><p>Acompanhe o ecossistema LETTER em uma única visão.</p></div><button className="outline-button">Exportar relatório</button></div>
    {!data?.financial_transactions_enabled&&<div className="warning-banner"><ShieldAlert/><div><strong>Modo seguro de implantação</strong><p>Transações financeiras permanecem bloqueadas até a homologação do BaaS e da conta escrow.</p></div></div>}
    <div className="metric-grid">
      <Metric icon={<Users/>} label="Leads no funil" value={data?.leads??0} trend="Base inicial" />
      <Metric icon={<WalletCards/>} label="Cotas disponíveis" value={data?.available_quotas??0} trend="Inventário ativo" />
      <Metric icon={<FileCheck2/>} label="Propostas ativas" value={data?.active_proposals??0} trend="Em acompanhamento" />
      <Metric icon={<CircleDollarSign/>} label="Operações ativas" value={data?.active_operations??0} trend="Ledger protegido" />
    </div>
    <div className="dashboard-grid">
      <section className="panel large"><div className="panel-title"><div><span className="eyebrow dark">PIPELINE</span><h2>Esteiras de negócio</h2></div><button>Ver detalhes <ArrowUpRight/></button></div><div className="pipeline">
        {[['Análise inicial',8,72],['Documentação',5,49],['Funding',3,34],['Contratação',2,22],['Liquidação',1,12]].map(([name,count,pct])=><div className="pipeline-row" key={name as string}><span>{name}</span><div><i style={{width:`${pct}%`}}/></div><b>{count}</b></div>)}
      </div></section>
      <section className="panel nina-card"><div className="nina-orb"><BrainCircuit/></div><span className="eyebrow">NINA ENGINE</span><h2>Inteligência operacional</h2><p>A camada de regras e automações está pronta para receber os adaptadores de bureaus, WhatsApp e análise.</p><div className="nina-stats"><span><b>18</b> módulos</span><span><b>100%</b> auditável</span></div><button>Abrir central NINA <ArrowUpRight/></button></section>
      <section className="panel"><div className="panel-title"><div><span className="eyebrow dark">RISCO</span><h2>Alertas operacionais</h2></div></div><div className="empty-state"><ShieldAlert/><strong>Nenhum alerta crítico</strong><p>O monitoramento exibirá divergências, bloqueios e exceções.</p></div></section>
      <section className="panel"><div className="panel-title"><div><span className="eyebrow dark">FINANCEIRO</span><h2>Volume estruturado</h2></div></div><div className="big-number">{money.format(800000)}</div><p className="muted">Volume de demonstração em propostas</p><div className="split-bar"><i/><i/><i/></div><div className="legend"><span>Marketplace</span><span>SDC</span><span>Flash Capital</span></div></section>
    </div>
  </>;
}

function Metric({icon,label,value,trend}:{icon:React.ReactNode,label:string,value:number,trend:string}) { return <div className="metric-card"><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{trend}</small></div></div> }
