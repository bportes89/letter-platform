"use client";

import { Activity, Bell, BrainCircuit, ChevronDown, LayoutDashboard, LogOut, Menu, Search, Settings, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LetterLogo } from "@/components/brand/letter-logo";
import { api, logout, Module, User } from "@/lib/api";

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const [modules, setModules] = useState<Module[]>([]); const [user, setUser] = useState<User | null>(null); const [open, setOpen] = useState(false);
  useEffect(() => {
    Promise.all([api<Module[]>("/modules"), api<User>("/auth/me")]).then(([m,u]) => {
      const nav = m.some(x => x.key === "finops") ? m : [
        ...m.slice(0, 9),
        { key: "finops", name: "FinOps e quitação", description: "Simulador, quitação e pré-análise TAPAF", status: "ACTIVE", route: "/finops", critical: true },
        ...m.slice(9),
      ];
      setModules(nav); setUser(u);
    }).catch(() => logout());
  }, []);
  return <div className="app-shell">
    <aside className={open ? "sidebar open" : "sidebar"}>
      <div className="side-logo">
        <Link href="/" className="side-logo-link" aria-label="LETTER — início">
          <LetterLogo variant="horizontal" theme="dark" className="side-logo-mark" />
        </Link>
        <button onClick={()=>setOpen(false)}><X/></button>
      </div>
      <div className="side-context"><small>AMBIENTE</small><strong>LETTER Matriz</strong><ChevronDown size={14}/></div>
      <nav>
        <Link className={pathname==="/dashboard"?"active":""} href="/dashboard"><LayoutDashboard/>Visão geral</Link>
        <div className="nav-label">ECOSSISTEMA</div>
        {modules.slice(0,15).map(m=><Link className={pathname===`/modules/${m.key}`?"active":""} href={`/modules/${m.key}`} key={m.key}><ModuleIcon keyName={m.key}/>{m.name}</Link>)}
        <div className="nav-label">GESTÃO</div>
        {modules.slice(15).map(m=><Link className={pathname===`/modules/${m.key}`?"active":""} href={`/modules/${m.key}`} key={m.key}><ModuleIcon keyName={m.key}/>{m.name}</Link>)}
      </nav>
      <button className="logout" onClick={logout}><LogOut/>Sair</button>
    </aside>
    <section className="workspace">
      <div className="workspace-ambient" aria-hidden="true">
        <span className="ambient-orb ambient-orb-1" />
        <span className="ambient-orb ambient-orb-2" />
        <span className="ambient-orb ambient-orb-3" />
      </div>
      <header className="topbar"><button className="menu-button" onClick={()=>setOpen(true)}><Menu/></button><div className="search"><Search/><input placeholder="Buscar operação, cliente ou cota..."/></div><div className="top-actions"><button><Bell/></button><div className="user-chip"><span>{user?.name?.slice(0,2).toUpperCase()??"LP"}</span><div><strong>{user?.name??"Carregando..."}</strong><small>{user?.role?.replaceAll("_"," ")}</small></div></div></div></header>
      <div className="content">{children}</div>
    </section>
  </div>
}

function ModuleIcon({keyName}:{keyName:string}) { return keyName==="nina"?<BrainCircuit/>:keyName==="rbac"?<ShieldCheck/>:keyName==="admin"?<Settings/>:<Activity/> }
