"use client";

import { KeyRound, ShieldCheck, Smartphone, LogIn } from "lucide-react";

export function MfaGuidePanel({ onActivate }: { onActivate?: () => void }) {
  return (
    <section className="panel mfa-guide-panel">
      <h2><ShieldCheck /> O que é autenticação em duas etapas?</h2>
      <p className="muted">
        É uma <strong>camada extra de segurança</strong> na sua conta LETTER. Além da senha, você confirma o acesso
        com um <strong>código de 6 dígitos</strong> que aparece no celular — assim, mesmo que alguém descubra sua senha,
        não entra sem o seu telefone.
      </p>

      <div className="mfa-guide-grid">
        <article className="mfa-guide-card">
          <LogIn />
          <h3>1ª etapa — senha</h3>
          <p>E-mail corporativo e senha, como você já faz hoje no login.</p>
        </article>
        <article className="mfa-guide-card">
          <Smartphone />
          <h3>2ª etapa — código no celular</h3>
          <p>Código temporário gerado no app autenticador (válido por poucos segundos).</p>
        </article>
      </div>

      <h3>Como ativar (passo a passo)</h3>
      <ol className="mfa-guide-steps">
        <li>
          <strong>Instale um app autenticador</strong> no celular — por exemplo Google Authenticator,
          Microsoft Authenticator ou Authy (grátis na loja do celular).
        </li>
        <li>
          <strong>Abra a aba “Ativar agora”</strong> nesta página e clique em <em>Ativar código validador</em>.
        </li>
        <li>
          <strong>Escaneie o QR Code</strong> com o app (ou copie a chave manualmente, se preferir).
        </li>
        <li>
          <strong>Digite o código de 6 dígitos</strong> que o app mostrar e confirme — pronto, proteção ativa.
        </li>
        <li>
          <strong>Nos próximos logins</strong>, marque a opção “Já ativei o autenticador” e informe o código do app.
        </li>
      </ol>

      <div className="notice">
        <ShieldCheck size={16} />
        <div>
          <strong>É opcional, mas recomendado</strong>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Quem não ativar continua entrando só com e-mail e senha. Quem ativar ganha proteção extra —
            ideal para parceiros, gestores e quem movimenta operações na plataforma.
          </p>
        </div>
      </div>

      <h3>Perguntas frequentes</h3>
      <dl className="mfa-faq">
        <dt>Perdi o celular. E agora?</dt>
        <dd>Entre em contato com o suporte LETTER para revalidar sua identidade e reconfigurar o acesso.</dd>
        <dt>Preciso fazer isso para abrir a conta LETTER?</dt>
        <dd>Não. A abertura da conta digital é outro fluxo (CPF/CNPJ e verificação). Isso aqui é só segurança do login.</dd>
        <dt>O código chega por SMS?</dt>
        <dd>Hoje o código é gerado no app autenticador, sem custo de SMS. É o mesmo padrão usado por bancos e grandes plataformas.</dd>
      </dl>

      {onActivate && (
        <button type="button" className="admin-button" onClick={onActivate}>
          <KeyRound /> Ir para ativação
        </button>
      )}
    </section>
  );
}
