/**
 * Marcas de terceros reproducidas a partir de sus SVG oficiales.
 * Se usan únicamente para indicar compatibilidad/integración.
 * Cada marca es propiedad de su respectivo dueño.
 */
import type { SVGProps } from 'react'

type LogoProps = SVGProps<SVGSVGElement> & { className?: string }

/* ------------------------------------------------------------------ */
/* GitHub — Octocat mark oficial (16x16 grid)                          */
/* ------------------------------------------------------------------ */
export function GitHubLogo({ className = 'h-6 w-6', ...props }: LogoProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={className}
      fill="currentColor"
      role="img"
      aria-label="GitHub"
      {...props}
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.07-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.06-.01 1.87-.01 2.13 0 .21.15.46.55.38A7.995 7.995 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Supabase — logo oficial (dos "rayos" con degradado verde)            */
/* ------------------------------------------------------------------ */
export function SupabaseLogo({ className = 'h-6 w-6', ...props }: LogoProps) {
  const id = 'sb-grad'
  return (
    <svg
      viewBox="0 0 109 113"
      className={className}
      fill="none"
      role="img"
      aria-label="Supabase"
      {...props}
    >
      <path
        d="M63.7076 110.284C60.8481 113.885 55.0502 111.912 54.9813 107.314L53.9738 40.0627H99.1935C107.384 40.0627 111.952 49.5228 106.859 55.9374L63.7076 110.284Z"
        fill={`url(#${id}-a)`}
      />
      <path
        d="M63.7076 110.284C60.8481 113.885 55.0502 111.912 54.9813 107.314L53.9738 40.0627H99.1935C107.384 40.0627 111.952 49.5228 106.859 55.9374L63.7076 110.284Z"
        fill={`url(#${id}-b)`}
        fillOpacity="0.2"
      />
      <path
        d="M45.317 2.07103C48.1765 -1.53037 53.9745 0.442937 54.0434 5.041L54.4849 72.2922H9.83113C1.64038 72.2922 -2.92775 62.8321 2.1655 56.4175L45.317 2.07103Z"
        fill="#3ECF8E"
      />
      <defs>
        <linearGradient
          id={`${id}-a`}
          x1="53.9738"
          y1="54.974"
          x2="94.1635"
          y2="71.8295"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#249361" />
          <stop offset="1" stopColor="#3ECF8E" />
        </linearGradient>
        <linearGradient
          id={`${id}-b`}
          x1="36.1558"
          y1="30.578"
          x2="54.4844"
          y2="65.0806"
          gradientUnits="userSpaceOnUse"
        >
          <stop />
          <stop offset="1" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Google — "G" oficial de 4 colores                                   */
/* ------------------------------------------------------------------ */
export function GoogleLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="Google" {...props}>
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65Z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59A14.4 14.4 0 0 1 9.77 24c0-1.6.28-3.15.76-4.59l-7.98-6.19A23.94 23.94 0 0 0 0 24c0 3.88.93 7.55 2.56 10.78l7.97-6.19Z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z"
      />
      <path fill="none" d="M0 0h48v48H0z" />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Vercel — triángulo oficial                                          */
/* ------------------------------------------------------------------ */
export function VercelLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 76 65" className={className} fill="currentColor" role="img" aria-label="Vercel" {...props}>
      <path d="M37.5274 0L75.0548 65H0L37.5274 0Z" />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Slack — 4 pares de trazos oficiales                                 */
/* ------------------------------------------------------------------ */
export function SlackLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 122.8 122.8" className={className} role="img" aria-label="Slack" {...props}>
      <path
        d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9zm6.5 0c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V77.6z"
        fill="#E01E5A"
      />
      <path
        d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9H45.2zm0 6.5c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9h32.3z"
        fill="#36C5F0"
      />
      <path
        d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9-5.8 12.9-12.9 12.9H97V45.2zm-6.5 0c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0s12.9 5.8 12.9 12.9v32.3z"
        fill="#2EB67D"
      />
      <path
        d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9-12.9-5.8-12.9-12.9V97h12.9zm0-6.5c-7.1 0-12.9-5.8-12.9-12.9s5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H77.6z"
        fill="#ECB22E"
      />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Notion — marca oficial                                              */
/* ------------------------------------------------------------------ */
export function NotionLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} role="img" aria-label="Notion" {...props}>
      <path
        d="M6.017 4.313l55.333-4.087c6.797-.583 8.543.19 12.817 3.383l17.663 12.443c2.913 2.14 3.883 2.723 3.883 5.053v68.243c0 4.277-1.553 6.807-6.99 7.193L24.467 99.967c-4.08.193-6.023-.39-8.16-3.113L3.3 79.94c-2.333-3.113-3.3-5.443-3.3-8.167V11.113c0-3.497 1.553-6.413 6.017-6.8z"
        fill="#fff"
      />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M61.35.227L6.017 4.313C1.553 4.7 0 7.616 0 11.113v60.66c0 2.723.967 5.053 3.3 8.167l13.007 16.913c2.137 2.723 4.08 3.307 8.16 3.113l64.257-3.883c5.433-.387 6.99-2.917 6.99-7.193V21.106c0-2.21-.873-2.847-3.443-4.733L69.51 3.61C65.237.417 63.49-.356 61.35.227zM25.92 19.523c-5.247.353-6.437.433-9.417-1.99L8.927 11.507c-.77-.78-.383-1.753 1.557-1.947l53.193-3.887c4.467-.39 6.793 1.167 8.54 2.527l9.123 6.6c.387.197 1.353 1.36.193 1.36l-54.933 3.307-.68.056zM19.803 88.3V30.367c0-2.53.777-3.697 3.103-3.893L86 22.78c2.14-.193 3.107 1.167 3.107 3.693v57.547c0 2.53-.39 4.67-3.883 4.863l-60.377 3.5c-3.493.193-5.043-.97-5.043-4.083zm59.6-54.827c.387 1.75 0 3.5-1.75 3.7l-2.907.577v42.7c-2.527 1.36-4.853 2.137-6.797 2.137-3.107 0-3.883-.973-6.21-3.887l-19.03-29.94v28.967l6.02 1.363s0 3.5-4.857 3.5l-13.39.777c-.39-.78 0-2.723 1.357-3.11l3.497-.97v-38.24L30.48 40.7c-.39-1.75.583-4.277 3.3-4.473l14.367-.967 19.8 30.327v-26.83l-5.047-.58c-.39-2.143 1.163-3.7 3.103-3.89l13.4-.813z"
        fill="#000"
      />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Linear — marca oficial                                              */
/* ------------------------------------------------------------------ */
export function LinearLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" role="img" aria-label="Linear" {...props}>
      <path d="M1.226 61.523c-.312-1.234.11-2.542 1.016-3.448L58.075 2.242c.906-.906 2.214-1.328 3.448-1.016 12.756 3.226 23.105 13.575 26.331 26.331.312 1.234-.11 2.542-1.016 3.448L30.99 86.868c-.906.906-2.214 1.328-3.448 1.016C14.786 84.658 4.437 74.309 1.211 61.553l.015-.03Z" />
      <path d="M.007 46.075c-.055.99 1.134 1.58 1.834.88l45.144-45.145c.7-.7.11-1.889-.88-1.834C21.383 1.324 1.324 21.383.007 46.075Z" />
      <path d="M45.926 98.72c-1.164.19-1.767-1.4-.93-2.236l50.16-50.16c.837-.837 2.426-.234 2.237.93-3.632 22.31-21.157 39.835-43.467 43.467l-8 8Z" />
      <path d="M53.32 99.847c-1.02.083-1.44-1.238-.63-1.865C74.05 81.7 82.68 68.29 87.99 53.5c.5-1.39 2.47-1.09 2.4.38-.86 17.3-14.62 31.35-31.87 32.72l-5.2 13.247Z" />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Figma — 5 formas oficiales                                          */
/* ------------------------------------------------------------------ */
export function FigmaLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 38 57" className={className} role="img" aria-label="Figma" {...props}>
      <path d="M19 28.5a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0Z" fill="#1ABCFE" />
      <path d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 0 1-19 0Z" fill="#0ACF83" />
      <path d="M19 0v19h9.5a9.5 9.5 0 0 0 0-19H19Z" fill="#FF7262" />
      <path d="M0 9.5A9.5 9.5 0 0 0 9.5 19H19V0H9.5A9.5 9.5 0 0 0 0 9.5Z" fill="#F24E1E" />
      <path d="M0 28.5A9.5 9.5 0 0 0 9.5 38H19V19H9.5A9.5 9.5 0 0 0 0 28.5Z" fill="#A259FF" />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Stripe — wordmark simplificado                                      */
/* ------------------------------------------------------------------ */
export function StripeLogo({ className = 'h-5 w-5', ...props }: LogoProps) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label="Stripe" {...props}>
      <rect width="32" height="32" rx="7" fill="#635BFF" />
      <path
        d="M15.34 12.9c0-.79.66-1.1 1.72-1.1 1.3 0 2.94.4 4.24 1.1v-3.4c-1.42-.56-2.83-.78-4.24-.78-3.46 0-5.77 1.8-5.77 4.82 0 4.68 6.44 3.93 6.44 5.95 0 .93-.81 1.23-1.9 1.23-1.42 0-3.24-.58-4.68-1.37v3.45c1.6.69 3.21 .98 4.68.98 3.55 0 6-1.75 6-4.81 0-5.05-6.49-4.15-6.49-6.07Z"
        fill="#fff"
      />
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Marca propia                                                        */
/* ------------------------------------------------------------------ */
/**
 * Marca Datgent: logo del proyecto.
 */
export function OrquestaMark({ className = 'h-8 w-8' }: LogoProps) {
  return (
    <img
      src="/datgent-logo-sm.png"
      alt="Datgent"
      width="192"
      height="192"
      decoding="async"
      className={`${className} rounded-lg object-contain`}
    />
  )
}

export function CodigoFacilitoLogo({ className = 'h-7 w-7', ...props }: LogoProps) {
  return (
    <img
      src="/codigo-facilito-logo-sm.png"
      alt="Código Facilito"
      width="192"
      height="143"
      loading="lazy"
      decoding="async"
      className={`${className} object-contain`}
      {...(props as React.ImgHTMLAttributes<HTMLImageElement>)}
    />
  )
}

export function KiroLogo({ className = 'h-7 w-7', ...props }: LogoProps) {
  return (
    <img
      src="/kiro-logo-sm.png"
      alt="Kiro"
      width="192"
      height="192"
      loading="lazy"
      decoding="async"
      className={`${className} rounded-lg object-contain`}
      {...(props as React.ImgHTMLAttributes<HTMLImageElement>)}
    />
  )
}
