import type { Metadata } from "next";
import { Fraunces } from "next/font/google";
import "./globals.css";

// Tipo editorial (seção 1 do checkpoint 10) - só para manchetes, números-hero
// e títulos de shadcn (Card/Sheet/Dialog já usam a classe `font-heading`
// nativamente). A sans neutra (system-ui, em globals.css) continua para UI,
// tabela e eixo - o contraste entre os dois é a identidade, não uma troca
// completa de tipografia.
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-editorial",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Mercator — Radar de Comércio",
  description:
    "Mapeamento de abertura e fechamento de estabelecimentos por bairro e categoria em Curitiba",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`h-full antialiased ${fraunces.variable}`}>
      <body className="h-full flex flex-col">{children}</body>
    </html>
  );
}
