"use client";

import { KeyRound, ShieldCheck, Smartphone, LogIn } from "lucide-react";

export function MfaGuidePanel({ onActivate }: { onActivate?: () => void }) {
  return (
    <section className="panel mfa-guide-panel">
      <h2><ShieldCheck /> Login e camadas de segurança</h2>
      <p className="muted">
        Ao entrar na plataforma, após e-mail e senha você recebe um <strong>código por e-mail</strong> — essa é a
        verificação principal (obrigatória quando ativada na organização). O autenticador abaixo (TOTP) é uma
        <strong> camada avançada opcional</strong>: um código de 6 dígitos no app do celular, para quem quer proteção extra.
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
          <strong>E-mail no login + TOTP opcional</strong>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            O código por e-mail no login não se desativa aqui — ele é gerenciado pela política LETTER.
            O autenticador (esta página) é opcional e recomendado para parceiros, gestores e operações sensíveis.
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
