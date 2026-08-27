import type { Metadata } from "next";
import "./globals.css";
import "./collections.css";
import "./auctions.css";
import "./tax-communications.css";
import "./nina-bi.css";

export const metadata: Metadata = {
  title: "LETTER | Infraestrutura Fiduciária",
  description:
    "Engenharia financeira, tecnologia fiduciária e ativos reais para capital empresarial estruturado.",
  openGraph: {
    title: "LETTER | Infraestrutura Fiduciária",
    description: "Capital estruturado para empresas que precisam avançar.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
