"use client";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export type QuitConCustoEntradaItem = {
  codigo: string;
  nome: string;
  valor: string | null;
  obrigatorio?: boolean;
  aplicavel?: boolean;
  reembolsavel?: boolean;
  reembolsavel_se_reprovado_adm?: boolean;
  descricao?: string;
};

export type QuitConCustosEntrada = {
  titulo: string;
  itens: QuitConCustoEntradaItem[];
  total_obrigatorio_abertura: string;
  total_com_servico_operacional: string;
};

export function QuitConCustosEntradaPanel({ data }: { data: QuitConCustosEntrada }) {
  const comServico = data.itens.some((i) => i.codigo === "SERVICO_OPERACIONAL_2PCT" && i.aplicavel);
  return (
    <section className="panel quitcon-custos-entrada">
      <h3>{data.titulo}</h3>
      <div className="quitcon-custos-list">
        {data.itens.map((item) => {
          const opcionalInativo = item.codigo === "SERVICO_OPERACIONAL_2PCT" && !item.aplicavel;
          return (
            <article key={item.codigo} className={opcionalInativo ? "muted" : ""}>
              <div className="quitcon-custo-head">
                <b>{item.nome}</b>
                <strong>
                  {item.valor ? brl.format(Number(item.valor)) : "Opcional — marque serviço LETTER"}
                </strong>
              </div>
              <small>{item.descricao}</small>
              <small>
                {item.reembolsavel_se_reprovado_adm && "100% reembolsável se a administradora reprovar · "}
                {item.reembolsavel === false && !item.reembolsavel_se_reprovado_adm && "Não reembolsável · "}
                {item.obrigatorio ? "Obrigatório na abertura" : "Opcional na abertura"}
              </small>
            </article>
          );
        })}
      </div>
      <div className="finops-summary">
        <article>
          <small>Total obrigatório (TAPAF + Escrow 10%)</small>
          <strong>{brl.format(Number(data.total_obrigatorio_abertura))}</strong>
        </article>
        {comServico && (
          <article>
            <small>Total com taxa serviço 2%</small>
            <strong>{brl.format(Number(data.total_com_servico_operacional))}</strong>
          </article>
        )}
      </div>
    </section>
  );
}
