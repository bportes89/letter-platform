import { PersonaDashboard } from "@/components/persona-dashboard";
import { PortalGuard } from "@/components/portal-guard";

export default function OperacaoPortalPage() {
  return (
    <PortalGuard slug="operacao">
      <PersonaDashboard />
    </PortalGuard>
  );
}
