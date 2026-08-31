import { PersonaDashboard } from "@/components/persona-dashboard";
import { PortalGuard } from "@/components/portal-guard";

export default function ClientePortalPage() {
  return (
    <PortalGuard slug="cliente">
      <PersonaDashboard />
    </PortalGuard>
  );
}
