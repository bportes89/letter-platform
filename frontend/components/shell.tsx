"use client";

import {
  Activity, Bell, BrainCircuit, Building2, ChevronDown, FileCheck2, FileText, Gavel,
  HandCoins, Landmark, LayoutDashboard, LayoutGrid, LogOut, Menu, Search, Settings, ShieldCheck,
  ShoppingBag, Sparkles, TrendingUp, Wallet, X, Zap,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { LetterLogo } from "@/components/brand/letter-logo";
import { api, logout, Module, User } from "@/lib/api";
import {
  isBankPath,
  isBankModuleKey,
  isPlatformPath,
  platformHomePath,
} from "@/lib/main-nav";
import { PLATFORM_HIDDEN_MODULE_KEYS } from "@/lib/product-nav";
import {
  filterPlatformModules,
  filterProductNav,
  personaLabel,
} from "@/lib/role-nav";
import { isPortalHomePath } from "@/lib/portal-routes";

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [modules, setModules] = useState<Module[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);
  const [bankZoneOpen, setBankZoneOpen] = useState(true);
  const [platformZoneOpen, setPlatformZoneOpen] = useState(true);

  useEffect(() => {
    Promise.all([api<Module[]>("/modules"), api<User>("/auth/me")])
      .then(([m, u]) => {
        const platform = filterPlatformModules(
          u.role,
          m.filter((x) => !PLATFORM_HIDDEN_MODULE_KEYS.has(x.key)),
        );
        setModules(platform);
        setUser(u);
      })
      .catch(() => logout());
  }, []);

  useEffect(() => {
    // Mantém as duas zonas acessíveis: só garante que a zona da rota atual esteja aberta.
    // Não fecha a outra — o BANK sumia visualmente na visão geral quando ficava só o título.
    if (isBankPath(pathname)) {
      setBankZoneOpen(true);
    } else if (isPlatformPath(pathname, user?.role)) {
      setPlatformZoneOpen(true);
    }
  }, [pathname, user?.role]);

  const productNav = user ? filterProductNav(user.role) : [];
  const commercialNav = useMemo(() => productNav.filter((item) => item.commercial), [productNav]);
  const structuralNav = useMemo(() => productNav.filter((item) => !item.commercial), [productNav]);
  const bankModules = useMemo(
    () => modules.filter((m) => isBankModuleKey(m.key)),
    [modules],
  );
  const platformModules = useMemo(
    () => modules.filter((m) => !isBankModuleKey(m.key)),
    [modules],
  );
  const persona = personaLabel(user?.role);
  const portalHome = user ? platformHomePath(user.role) : "/login";
  const modulePath = (key: string) => `/modules/${key}`;
  const isActive = (key: string) => pathname === modulePath(key);
  const isGroupActive = (keys: string[]) => keys.some(isActive);
  const showBankZone = bankModules.length > 0;
  const showPlatformZone =
    commercialNav.length > 0 ||
    structuralNav.length > 0 ||
    platformModules.length > 0 ||
    Boolean(user);

  return (
    <div className="app-shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="side-logo">
          <Link href="/" className="side-logo-link" aria-label="LETTER — início">
            <LetterLogo variant="official" theme="light" className="side-logo-mark" priority />
          </Link>
          <button onClick={() => setOpen(false)}><X /></button>
        </div>
        <div className="side-context">
          <small>SEU ACESSO</small>
          <strong>{persona}</strong>
          <ChevronDown size={14} />
        </div>
        <nav className="main-nav">
          {showBankZone && (
            <div className={`nav-zone${bankZoneOpen ? " open" : ""}${isBankPath(pathname) ? " active-zone" : ""}`}>
              <button
                type="button"
                className={`nav-zone-header${isBankPath(pathname) ? " active" : ""}`}
                onClick={() => setBankZoneOpen((open) => !open)}
                aria-expanded={bankZoneOpen}
              >
                <Landmark size={18} />
                <span>BANK</span>
                <ChevronDown size={14} className="nav-zone-chevron" />
              </button>
              {bankZoneOpen && (
                <div className="nav-zone-body">
                  {bankModules.map((m) => (
                    <Link
                      className={isActive(m.key) ? "active" : ""}
                      href={modulePath(m.key)}
                      key={m.key}
                      onClick={() => setOpen(false)}
                    >
                      <ModuleIcon keyName={m.key} />
                      {m.key === "my-wallet" ? "Carteira LETTER" : m.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {showPlatformZone && (
            <div className={`nav-zone${platformZoneOpen ? " open" : ""}${isPlatformPath(pathname, user?.role) ? " active-zone" : ""}`}>
              <button
                type="button"
                className={`nav-zone-header${isPlatformPath(pathname, user?.role) ? " active" : ""}`}
                onClick={() => setPlatformZoneOpen((open) => !open)}
                aria-expanded={platformZoneOpen}
              >
                <LayoutGrid size={18} />
                <span>PLATAFORMA</span>
                <ChevronDown size={14} className="nav-zone-chevron" />
              </button>
              {platformZoneOpen && (
                <div className="nav-zone-body">
                  <Link
                    className={isPortalHomePath(pathname, user?.role) ? "active" : ""}
                    href={portalHome}
                    onClick={() => setOpen(false)}
                  >
                    <LayoutDashboard />
                    Visão geral
                  </Link>
                  <Link
                    className={pathname === "/seguranca" ? "active" : ""}
                    href="/seguranca"
                    onClick={() => setOpen(false)}
                  >
                    <ShieldCheck />
                    Autenticação 2 etapas
                  </Link>

                  {commercialNav.length > 0 && (
                    <>
                      <div className="nav-label">Comercial</div>
                      <div className="nav-products">
                        {commercialNav.map((item) =>
                          item.children?.length ? (
                            <div
                              className={`nav-group${isGroupActive(item.children.map((c) => c.key)) ? " open" : ""}`}
                              key={item.key}
                            >
                              <div className="nav-group-title">
                                <ProductIcon keyName="marketplace" />
                                {item.name}
                              </div>
                              {item.children.map((child) => (
                                <Link
                                  className={`nav-sub${isActive(child.key) ? " active" : ""}`}
                                  href={modulePath(child.key)}
                                  key={child.key}
                                  onClick={() => setOpen(false)}
                                >
                                  {child.name}
                                </Link>
                              ))}
                            </div>
                          ) : (
                            <Link
                              className={isActive(item.key) ? "active" : ""}
                              href={modulePath(item.key)}
                              key={item.key}
                              onClick={() => setOpen(false)}
                            >
                              <ProductIcon keyName={item.key} />
                              {item.name}
                            </Link>
                          ),
                        )}
                      </div>
                    </>
                  )}

                  {structuralNav.length > 0 && (
                    <>
                      <div className="nav-label">Produtos</div>
                      <div className="nav-products">
                        {structuralNav.map((item) => (
                          <Link
                            className={isActive(item.key) ? "active" : ""}
                            href={modulePath(item.key)}
                            key={item.key}
                            onClick={() => setOpen(false)}
                          >
                            <ProductIcon keyName={item.key} />
                            {item.name}
                          </Link>
                        ))}
                      </div>
                    </>
                  )}

                  {platformModules.length > 0 && (
                    <>
                      <div className="nav-label">Ferramentas</div>
                      {platformModules.map((m) => (
                        <Link
                          className={pathname === modulePath(m.key) ? "active" : ""}
                          href={modulePath(m.key)}
                          key={m.key}
                          onClick={() => setOpen(false)}
                        >
                          <ModuleIcon keyName={m.key} />
                          {m.name}
                        </Link>
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </nav>
        <button className="logout" onClick={logout}>
          <LogOut />
          Sair
        </button>
      </aside>
      <section className="workspace">
        <div className="workspace-ambient" aria-hidden="true">
          <span className="ambient-orb ambient-orb-1" />
          <span className="ambient-orb ambient-orb-2" />
          <span className="ambient-orb ambient-orb-3" />
        </div>
        <header className="topbar">
          <button className="menu-button" onClick={() => setOpen(true)}>
            <Menu />
          </button>
          <div className="search">
            <Search />
            <input placeholder="Buscar operação, cliente ou cota..." />
          </div>
          <div className="top-actions">
            <button><Bell /></button>
            <div className="user-chip">
              <span>{user?.name?.slice(0, 2).toUpperCase() ?? "LP"}</span>
              <div>
                <strong>{user?.name ?? "Carregando..."}</strong>
                <small>{user?.role?.replaceAll("_", " ")}</small>
              </div>
            </div>
          </div>
        </header>
        <div className="content">{children}</div>
      </section>
    </div>
  );
}

function ProductIcon({ keyName }: { keyName: string }) {
  switch (keyName) {
    case "marketplace":
    case "marketplace-group":
      return <ShoppingBag />;
    case "proposals":
      return <FileText />;
    case "sdc":
      return <Wallet />;
    case "flash-capital":
      return <Zap />;
    case "lease-equity":
      return <Building2 />;
    case "flash-invest":
      return <TrendingUp />;
    case "quitcon":
      return <HandCoins />;
    case "lss":
      return <FileCheck2 />;
    case "leilao":
      return <Gavel />;
    default:
      return <Sparkles />;
  }
}

function ModuleIcon({ keyName }: { keyName: string }) {
  if (keyName === "my-wallet" || keyName === "wallet" || keyName === "payments") {
    return <Landmark />;
  }
  return keyName === "nina" ? <BrainCircuit /> : keyName === "rbac" ? <ShieldCheck /> : keyName === "admin" ? <Settings /> : <Activity />;
}
