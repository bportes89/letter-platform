import { Shell } from "@/components/shell";
import { WalletOnboardingGuard } from "@/components/wallet-onboarding-guard";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <WalletOnboardingGuard>
      <Shell>{children}</Shell>
    </WalletOnboardingGuard>
  );
}
