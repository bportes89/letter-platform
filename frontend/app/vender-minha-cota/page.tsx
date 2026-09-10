"use client";

import { Suspense } from "react";
import VenderMinhaCotaPage from "./vender-page";

export default function Page() {
  return (
    <Suspense fallback={<div className="site-root"><main style={{ padding: 40 }}>Carregando…</main></div>}>
      <VenderMinhaCotaPage />
    </Suspense>
  );
}
