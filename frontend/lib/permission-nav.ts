import type { Module, User } from "@/lib/api";
import {
  canAccessModuleRoute as roleCanAccessModuleRoute,
  canAccessPlatformModule as roleCanAccessPlatformModule,
  canAccessProduct as roleCanAccessProduct,
  filterPlatformModules as roleFilterPlatformModules,
  filterProductNav as roleFilterProductNav,
} from "@/lib/role-nav";

const MODULE_ALIASES: Record<string, string[]> = {
  cadastros: ["cadastros", "marketplace"],
  marketplace: ["marketplace", "cadastros"],
  "flash-capital": ["flash-capital", "finops"],
  finops: ["flash-capital", "finops"],
  "flash-invest": ["flash-invest", "funding"],
  funding: ["flash-invest", "funding"],
  leilao: ["leilao", "auctions"],
  auctions: ["leilao", "auctions"],
  payments: ["payments", "bank-control"],
  "bank-control": ["bank-control", "payments"],
};

function usesCustomModules(user: User | null | undefined): boolean {
  return Boolean(user?.effective_modules && user.effective_modules.length > 0);
}

function moduleSet(user: User | null | undefined): Set<string> | null {
  if (!user || !usesCustomModules(user)) return null;
  const modules = new Set<string>();
  for (const mod of user.effective_modules ?? []) {
    modules.add(mod);
    for (const alias of MODULE_ALIASES[mod] ?? []) modules.add(alias);
  }
  return modules;
}

function routeAllowed(routeKey: string, modules: Set<string>): boolean {
  if (modules.has(routeKey)) return true;
  for (const [canonical, aliases] of Object.entries(MODULE_ALIASES)) {
    if (aliases.includes(routeKey) && modules.has(canonical)) return true;
  }
  return false;
}

export function canAccessModuleRouteForUser(user: User | null | undefined, routeKey: string): boolean {
  if (!user) return false;
  const modules = moduleSet(user);
  if (!modules) return roleCanAccessModuleRoute(user.role, routeKey);
  return routeAllowed(routeKey, modules);
}

export function canAccessPlatformModuleForUser(user: User | null | undefined, moduleKey: string): boolean {
  if (!user) return false;
  const modules = moduleSet(user);
  if (!modules) return roleCanAccessPlatformModule(user.role, moduleKey);
  return modules.has(moduleKey);
}

export function canAccessProductForUser(user: User | null | undefined, productKey: string): boolean {
  if (!user) return false;
  const modules = moduleSet(user);
  if (!modules) return roleCanAccessProduct(user.role, productKey);
  return routeAllowed(productKey, modules);
}

export function filterProductNavForUser(user: User | null | undefined) {
  if (!user) return [];
  const modules = moduleSet(user);
  if (!modules) return roleFilterProductNav(user.role);
  const nav = roleFilterProductNav(user.role);
  return nav
    .map((item) => {
      if (item.children?.length) {
        const children = item.children.filter((child) => routeAllowed(child.key, modules));
        if (!children.length) return null;
        return { ...item, children };
      }
      return routeAllowed(item.key, modules) ? item : null;
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);
}

export function filterPlatformModulesForUser(user: User | null | undefined, modules: Module[]): Module[] {
  if (!user) return [];
  const allowed = moduleSet(user);
  if (!allowed) return roleFilterPlatformModules(user.role, modules);
  return modules.filter((m) => allowed.has(m.key));
}
