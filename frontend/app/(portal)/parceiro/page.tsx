import { PersonaDashboard } from "@/components/persona-dashboard";
import { PortalGuard } from "@/components/portal-guard";

export default function ParceiroPortalPage() {
  return (
    <PortalGuard slug="parceiro">
      <PersonaDashboard />
    </PortalGuard>
  );
}
