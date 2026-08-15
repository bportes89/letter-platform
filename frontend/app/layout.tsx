import type { Metadata } from "next";
import "./globals.css";
import "./collections.css";
import "./auctions.css";
import "./tax-communications.css";
import "./nina-bi.css";

export const metadata: Metadata = {
  title: "LETTER | Financial Infrastructure",
  description: "Plataforma de operações estruturadas, cotas, funding e inteligência NINA",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
