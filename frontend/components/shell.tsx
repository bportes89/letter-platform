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
  bankControlLabel,
  BANK_ACCOUNT_KEYS,
  BANK_CONTROL_KEYS,
  canSeeBankControl,
  isBankControlKey,
  isBankInvestmentKey,
  isBankModuleKey,
  isBankPath,
  isPlatformPath,
  platformHomePath,
} from "@/lib/main-nav";
import { PLATFORM_HIDDEN_MODULE_KEYS } from "@/lib/product-nav";
import {
  canAccessModuleRoute,
  canAccessPlatformModule,
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
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

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
    if (isBankPath(pathname)) {
      setBankZoneOpen(true);
    } else if (isPlatformPath(pathname, user?.role)) {
      setPlatformZoneOpen(true);
    }
  }, [pathname, user?.role]);

  const productNav = user ? filterProductNav(user.role) : [];
  const commercialNav = useMemo(() => productNav.filter((item) => item.commercial), [productNav]);
  const platformProducts = useMemo(
    () => productNav.filter((item) => !item.commercial && !item.bank),
    [productNav],
  );
  const bankInvestments = useMemo(
    () => productNav.filter((item) => item.bank),
    [productNav],
  );

  const bankAccountModules = useMemo(
    () =>
      modules.filter(
        (m) =>
          (BANK_ACCOUNT_KEYS as readonly string[]).includes(m.key) &&
          canAccessPlatformModule(user?.role, m.key),
      ),
    [modules, user?.role],
  );
  const bankControlModules = useMemo(() => {
    if (!canSeeBankControl(user?.role)) return [];
    return modules.filter(
      (m) =>
        (BANK_CONTROL_KEYS as readonly string[]).includes(m.key) &&
        canAccessPlatformModule(user?.role, m.key),
    );
  }, [modules, user?.role]);
  const platformModules = useMemo(
    () => modules.filter((m) => !isBankModuleKey(m.key)),
    [modules],
  );

  const persona = personaLabel(user?.role);
  const portalHome = user ? platformHomePath(user.role) : "/login";
  const modulePath = (key: string) => `/modules/${key}`;
  const isActive = (key: string) => pathname === modulePath(key);
  const isGroupActive = (keys: string[]) => keys.some(isActive);
  const isGroupExpanded = (groupKey: string, childKeys: string[]) => {
    if (isGroupActive(childKeys)) return true;
    return Boolean(openGroups[groupKey]);
  };
  const toggleGroup = (groupKey: string) => {
    setOpenGroups((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));
  };

  const showBankControl = canSeeBankControl(user?.role) && canAccessModuleRoute(user?.role, "bank-control");
  const showBankZone =
    bankAccountModules.length > 0 ||
    bankInvestments.length > 0 ||
    bankControlModules.length > 0 ||
    showBankControl;
  const showPlatformZone =
    commercialNav.length > 0 ||
    platformProducts.length > 0 ||
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
        <div className="sidebar-scroll">
          <nav className="main-nav">
            {showBankZone && (
              <div className={`nav-zone${bankZoneOpen ? " open" : ""}${isBankPath(pathname) ? " active-zone" : ""}`}>
                <button
                  type="button"
                  className={`nav-zone-header${isBankPath(pathname) ? " active" : ""}`}
                  onClick={() => setBankZoneOpen((v) => !v)}
                  aria-expanded={bankZoneOpen}
                >
                  <Landmark size={18} />
                  <span>BANK</span>
                  <ChevronDown size={14} className="nav-zone-chevron" />
                </button>
                {bankZoneOpen && (
                  <div className="nav-zone-body">
                    {(bankAccountModules.length > 0 || showBankControl) && (
                      <>
                        <div className="nav-label">Conta</div>
                        {bankAccountModules.map((m) => (
                          <Link
                            className={isActive(m.key) ? "active" : ""}
                            href={modulePath(m.key)}
                            key={m.key}
                            onClick={() => setOpen(false)}
                          >
                            <ModuleIcon keyName={m.key} />
                            Carteira LETTER
                          </Link>
                        ))}
                      </>
                    )}

                    {bankInvestments.length > 0 && (
                      <>
                        <div className="nav-label">Investimentos</div>
                        <div className="nav-products">
                          {bankInvestments.map((item) => (
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

                    {(showBankControl || bankControlModules.length > 0) && (
                      <>
                        <div className="nav-label">Controle interno</div>
                        {showBankControl && (
                          <Link
                            className={isActive("bank-control") ? "active" : ""}
                            href={modulePath("bank-control")}
                            onClick={() => setOpen(false)}
                          >
                            <ShieldCheck />
                            {bankControlLabel("bank-control")}
                          </Link>
                        )}
                        {bankControlModules.map((m) => (
                          <Link
                            className={isActive(m.key) ? "active" : ""}
                            href={modulePath(m.key)}
                            key={m.key}
                            onClick={() => setOpen(false)}
                          >
                            <ModuleIcon keyName={m.key} />
                            {bankControlLabel(m.key)}
                          </Link>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            {showPlatformZone && (
              <div className={`nav-zone${platformZoneOpen ? " open" : ""}${isPlatformPath(pathname, user?.role) ? " active-zone" : ""}`}>
                <button
                  type="button"
                  className={`nav-zone-header${isPlatformPath(pathname, user?.role) ? " active" : ""}`}
                  onClick={() => setPlatformZoneOpen((v) => !v)}
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
                                className={`nav-group${isGroupExpanded(item.key, item.children.map((c) => c.key)) ? " open" : ""}`}
                                key={item.key}
                              >
                                <button
                                  type="button"
                                  className="nav-group-title"
                                  onClick={() => toggleGroup(item.key)}
                                  aria-expanded={isGroupExpanded(item.key, item.children.map((c) => c.key))}
                                >
                                  <ProductIcon keyName="marketplace" />
                                  <span style={{ flex: 1 }}>{item.name}</span>
                                  <ChevronDown size={12} className="nav-zone-chevron" />
                                </button>
                                {isGroupExpanded(item.key, item.children.map((c) => c.key)) &&
                                  item.children.map((child) => (
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

                    {platformProducts.length > 0 && (
                      <>
                        <div className="nav-label">Produtos</div>
                        <div className="nav-products">
                          {platformProducts.map((item) => (
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
        </div>
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
  if (isBankInvestmentKey(keyName)) return <TrendingUp />;
  if (isBankControlKey(keyName) || isBankModuleKey(keyName)) return <Landmark />;
  return keyName === "nina" ? <BrainCircuit /> : keyName === "rbac" ? <ShieldCheck /> : keyName === "admin" ? <Settings /> : <Activity />;
}
