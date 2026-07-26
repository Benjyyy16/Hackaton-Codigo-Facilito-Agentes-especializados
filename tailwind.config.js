/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Papel: el fondo dominante es blanco
        paper: {
          DEFAULT: '#FFFFFF',
          50: '#FCFCFD',
          100: '#F7F7FA',
          200: '#EFEFF4',
          300: '#E5E4EC',
          400: '#D8D6E2',
        },
        // Tinta: texto y bordes duros
        ink: {
          950: '#08060F',
          900: '#0D0B16',
          800: '#1A1727',
          700: '#2E2A42',
          600: '#4A4463',
          500: '#6B6484',
          400: '#938DA8',
          300: '#BDB8CC',
          200: '#DDD9E6',
          100: '#EDEBF2',
        },
        // Morado: acento, no fondo
        violet: {
          50: '#F5F1FF',
          100: '#EBE3FF',
          200: '#D7C7FF',
          300: '#BCA2FF',
          400: '#9E77FF',
          500: '#8B5CF6',
          600: '#7C3AED',
          700: '#6926D9',
          800: '#551FAD',
          900: '#3F1880',
          950: '#2A1060',
        },
        // Verde: detalles mínimos (estados verificados)
        mint: {
          50: '#EDFDF5',
          100: '#DEFBEC',
          200: '#B6F3D6',
          300: '#7EE7B8',
          400: '#4FDCA0',
          500: '#3ECF8E',
          600: '#2FB37A',
          700: '#1F8A5C',
        },
        // Ámbar para advertencias del ledger
        clay: {
          100: '#FFF3E0',
          300: '#FFCF8A',
          500: '#F0A03C',
          700: '#B36B12',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Instrument Serif"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.045em',
      },
      boxShadow: {
        // Sombras sólidas desplazadas: estética de impreso, no de glow
        hard: '3px 3px 0 0 #0D0B16',
        'hard-sm': '2px 2px 0 0 #0D0B16',
        'hard-lg': '5px 5px 0 0 #0D0B16',
        'hard-violet': '3px 3px 0 0 #7C3AED',
        'hard-mint': '3px 3px 0 0 #2FB37A',
        lift: '0 1px 2px rgba(13,11,22,.06), 0 12px 32px -16px rgba(13,11,22,.18)',
        'lift-lg': '0 2px 4px rgba(13,11,22,.05), 0 28px 60px -28px rgba(13,11,22,.28)',
        inset: 'inset 0 1px 0 0 rgba(255,255,255,.7)',
      },
      backgroundImage: {
        // Cuadrícula tipo papel milimetrado
        grid: 'linear-gradient(to right, rgba(13,11,22,.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(13,11,22,.06) 1px, transparent 1px)',
        'grid-fine':
          'linear-gradient(to right, rgba(13,11,22,.035) 1px, transparent 1px), linear-gradient(to bottom, rgba(13,11,22,.035) 1px, transparent 1px)',
        'grid-dark':
          'linear-gradient(to right, rgba(255,255,255,.07) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,.07) 1px, transparent 1px)',
        rule: 'repeating-linear-gradient(to bottom, transparent 0 27px, rgba(13,11,22,.07) 27px 28px)',
        hatch:
          'repeating-linear-gradient(45deg, rgba(124,58,237,.12) 0 4px, transparent 4px 9px)',
        'hatch-mint':
          'repeating-linear-gradient(45deg, rgba(47,179,122,.16) 0 4px, transparent 4px 9px)',
      },
      backgroundSize: {
        grid: '32px 32px',
        'grid-lg': '76px 76px',
        'grid-sm': '8px 8px',
      },
      keyframes: {
        'stamp-in': {
          '0%': { transform: 'scale(2.4) rotate(-18deg)', opacity: '0' },
          '55%': { transform: 'scale(.92) rotate(-9deg)', opacity: '1' },
          '100%': { transform: 'scale(1) rotate(-7deg)', opacity: '1' },
        },
        marquee: {
          from: { transform: 'translateX(0)' },
          to: { transform: 'translateX(-50%)' },
        },
        'marquee-rev': {
          from: { transform: 'translateX(-50%)' },
          to: { transform: 'translateX(0)' },
        },
        blink: {
          '0%,100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'dash-run': { to: { strokeDashoffset: '-16' } },
        'tick-up': {
          '0%': { transform: 'translateY(60%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        wiggle: {
          '0%,100%': { transform: 'rotate(-1.2deg)' },
          '50%': { transform: 'rotate(1.2deg)' },
        },
        'grid-drift': {
          '0%': { backgroundPosition: '0 0, 0 0' },
          '100%': { backgroundPosition: '32px 32px, 32px 32px' },
        },
        float: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        'sheen-x': {
          '0%': { transform: 'translateX(-120%) skewX(-18deg)' },
          '100%': { transform: 'translateX(220%) skewX(-18deg)' },
        },
      },
      animation: {
        'stamp-in': 'stamp-in .7s cubic-bezier(.2,1.4,.4,1) both',
        marquee: 'marquee 34s linear infinite',
        'marquee-rev': 'marquee-rev 44s linear infinite',
        blink: 'blink 1.05s step-end infinite',
        'dash-run': 'dash-run .9s linear infinite',
        wiggle: 'wiggle 4s ease-in-out infinite',
        'grid-drift': 'grid-drift 22s linear infinite',
        float: 'float 6s ease-in-out infinite',
        'sheen-x': 'sheen-x 1.1s ease-out',
      },
    },
  },
  plugins: [],
}
