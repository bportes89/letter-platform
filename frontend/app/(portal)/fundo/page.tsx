import { PersonaDashboard } from "@/components/persona-dashboard";
import { PortalGuard } from "@/components/portal-guard";

export default function FundoPortalPage() {
  return (
    <PortalGuard slug="fundo">
      <PersonaDashboard />
    </PortalGuard>
  );
}
