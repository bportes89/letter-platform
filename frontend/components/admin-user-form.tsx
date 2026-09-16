"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Plus, ShieldCheck } from "lucide-react";
import { api, Branch, PermissionCatalogGroup, User } from "@/lib/api";

type Props = {
  branches: Branch[];
  busy?: boolean;
  onCreated?: (user: User) => void;
  onError?: (message: string) => void;
};

function passwordChecks(password: string, confirm: string) {
  return {
    length: password.length >= 8,
    number: /\d/.test(password),
    letter: /[A-Za-z]/.test(password),
    special: /[@#$]/.test(password),
    match: password.length > 0 && password === confirm,
  };
}

export function AdminUserForm({ branches, busy = false, onCreated, onError }: Props) {
  const [catalog, setCatalog] = useState<PermissionCatalogGroup[]>([]);
  const [accessAll, setAccessAll] = useState(true);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api<PermissionCatalogGroup[]>("/admin/permissions/catalog")
      .then(setCatalog)
      .catch(() => setCatalog([]));
  }, []);

  const checks = useMemo(() => passwordChecks(password, confirm), [password, confirm]);
  const canSubmit =
    checks.length &&
    checks.number &&
    checks.letter &&
    checks.special &&
    checks.match &&
    (accessAll || Object.values(selected).some(Boolean));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || submitting) return;
    const form = event.currentTarget;
    const fd = new FormData(form);
    setSubmitting(true);
    try {
      const permissions = Object.entries(selected)
        .filter(([, on]) => on)
        .map(([key]) => key);
      const user = await api<User>("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          name: fd.get("name"),
          email: fd.get("email"),
          phone: fd.get("phone") || null,
          password,
          branch_id: String(fd.get("branch_id") || "") || null,
          access_all: accessAll,
          permissions,
        }),
      });
      form.reset();
      setPassword("");
      setConfirm("");
      setSelected({});
      setAccessAll(true);
      onCreated?.(user);
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Não foi possível criar o administrador.");
    } finally {
      setSubmitting(false);
    }
  }

  function toggleAllInGroup(group: PermissionCatalogGroup, checked: boolean) {
    setSelected((prev) => {
      const next = { ...prev };
      for (const item of group.items) next[item.key] = checked;
      return next;
    });
  }

  return (
    <form className="stack-form admin-user-form" onSubmit={submit}>
      <h2><ShieldCheck /> Novo administrador</h2>
      <input name="name" placeholder="Nome completo" required disabled={busy || submitting} />
      <input name="email" type="email" placeholder="E-mail" required disabled={busy || submitting} />
      <input name="phone" placeholder="Telefone celular" disabled={busy || submitting} />
      <div className="admin-user-form__password-row">
        <input
          name="password"
          type={showPassword ? "text" : "password"}
          placeholder="Senha"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={busy || submitting}
        />
        <button type="button" className="table-action" onClick={() => setShowPassword((v) => !v)}>
          {showPassword ? "Ocultar" : "Mostrar"}
        </button>
      </div>
      <input
        name="confirm_password"
        type={showPassword ? "text" : "password"}
        placeholder="Confirmar senha"
        required
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        disabled={busy || submitting}
      />
      <ul className="admin-user-form__checks">
        <li className={checks.length ? "ok" : ""}>Mínimo 8 caracteres</li>
        <li className={checks.number ? "ok" : ""}>Pelo menos 1 número</li>
        <li className={checks.letter ? "ok" : ""}>Pelo menos 1 letra</li>
        <li className={checks.special ? "ok" : ""}>Pelo menos 1 caractere especial (@ # $)</li>
        <li className={checks.match ? "ok" : "err"}>
          {checks.match ? "Senhas conferem" : "A senha e a confirmação não são iguais"}
        </li>
      </ul>
      <select name="branch_id" disabled={busy || submitting || branches.length === 0}>
        <option value="">Sem filial (Matriz)</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>{b.name} ({b.code})</option>
        ))}
      </select>
      <label className="admin-user-form__access-all">
        <span>Acesso Total</span>
        <select value={accessAll ? "yes" : "no"} onChange={(e) => setAccessAll(e.target.value === "yes")} disabled={busy || submitting}>
          <option value="yes">Sim</option>
          <option value="no">Não</option>
        </select>
      </label>
      {!accessAll && (
        <div className="admin-user-form__permissions">
          <b>Permissões</b>
          {catalog.map((group) => (
            <div key={group.group} className="admin-user-form__permission-group">
              <div className="admin-user-form__group-head">
                <span>{group.group}</span>
                <button type="button" className="table-action" onClick={() => toggleAllInGroup(group, true)}>Marcar grupo</button>
                <button type="button" className="table-action" onClick={() => toggleAllInGroup(group, false)}>Limpar grupo</button>
              </div>
              <div className="admin-user-form__permission-grid">
                {group.items.map((item) => (
                  <label key={item.key} className="admin-user-form__permission-item">
                    <input
                      type="checkbox"
                      checked={Boolean(selected[item.key])}
                      onChange={(e) => setSelected((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                      disabled={busy || submitting}
                    />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      <button type="submit" disabled={!canSubmit || busy || submitting}>
        <Plus />
        {submitting ? "Criando…" : "Salvar administrador"}
      </button>
    </form>
  );
}
