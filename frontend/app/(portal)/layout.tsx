import { Shell } from "@/components/shell";
import { WalletOnboardingGuard } from "@/components/wallet-onboarding-guard";
import { ContractOnboardingGuard } from "@/components/contract-onboarding-guard";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <WalletOnboardingGuard>
      <ContractOnboardingGuard>
        <Shell>{children}</Shell>
      </ContractOnboardingGuard>
    </WalletOnboardingGuard>
  );
}
