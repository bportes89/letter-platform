import Image from "next/image";

type LetterLogoProps = {
  variant?: "horizontal" | "icon" | "full";
  /** Fundo escuro (nav do site / sidebar) ou claro (materiais em white mode). */
  theme?: "dark" | "light";
  className?: string;
  priority?: boolean;
};

const SOURCES = {
  horizontal: {
    dark: {
      src: "/brand/letter-logo-nav-dark.png",
      width: 1150,
      height: 326,
    },
    light: {
      src: "/brand/letter-logo-nav-light-bg.png",
      width: 1150,
      height: 326,
    },
  },
  full: {
    dark: {
      src: "/brand/letter-logo-full-transparent.png",
      width: 1150,
      height: 526,
    },
    light: {
      src: "/brand/letter-logo-full.png",
      width: 1254,
      height: 1254,
    },
  },
  icon: {
    dark: {
      src: "/brand/letter-shield-l.png",
      width: 512,
      height: 512,
    },
    light: {
      src: "/brand/letter-shield-l.png",
      width: 512,
      height: 512,
    },
  },
} as const;

export function LetterLogo({
  variant = "horizontal",
  theme = "dark",
  className,
  priority = false,
}: LetterLogoProps) {
  const asset = SOURCES[variant][theme];

  return (
    <Image
      src={asset.src}
      alt="LETTER — O Shopping do Crédito Seguro e Inteligente"
      width={asset.width}
      height={asset.height}
      className={className}
      priority={priority}
    />
  );
}
