import { PersonaDashboard } from "@/components/persona-dashboard";
import { PortalGuard } from "@/components/portal-guard";

export default function InvestidorPortalPage() {
  return (
    <PortalGuard slug="investidor">
      <PersonaDashboard />
    </PortalGuard>
  );
}
