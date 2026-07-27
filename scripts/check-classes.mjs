/**
 * Detecta clases de Tailwind usadas en el código pero que NO se generaron en el CSS.
 * Ejecutar después de `npm run build`.
 *   node scripts/check-classes.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, extname } from 'node:path'

const SRC = 'src'
const DIST = 'dist/assets'

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f)
    return statSync(p).isDirectory() ? walk(p) : [p]
  })
}

// 1. CSS generado
const css = readdirSync(DIST)
  .filter((f) => extname(f) === '.css')
  .map((f) => readFileSync(join(DIST, f), 'utf8'))
  .join('\n')

// Extrae los selectores de clase presentes en el CSS (des-escapados)
const generated = new Set()
for (const m of css.matchAll(/\.((?:[\w-]|\\.)+)/g)) {
  generated.add(m[1].replace(/\\/g, ''))
}

// 2. Clases usadas en el código
const used = new Map() // clase -> archivos
const classAttr = /class(?:Name)?\s*[=:]\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`)/g
// strings sueltos: cubren los mapas de clases (cn(...), Record<..., string>)
const bareStrings = /'([a-z0-9:\/\[\]\.\-_ ]{6,})'|"([a-z0-9:\/\[\]\.\-_ ]{6,})"/g

/** Utilities de Tailwind que aceptamos analizar (evita rutas de import y otros strings). */
const TW_UTILITY =
  /^(?:-?(?:[a-z]+:)*)?(?:bg|text|border|ring|ring-offset|from|via|to|fill|stroke|shadow|divide|decoration|outline|placeholder|accent|h|w|min-h|min-w|max-h|max-w|p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap|gap-x|gap-y|space-x|space-y|inset|top|right|bottom|left|z|opacity|rounded|font|leading|tracking|grid-cols|col-span|flex|items|justify|self|order|aspect|object|overflow|whitespace|cursor|select|pointer-events|transition|duration|delay|ease|animate|blur|backdrop-blur|translate-x|translate-y|scale|rotate|origin|line-clamp|truncate|tabular-nums|antialiased|sr-only|not-sr-only|container|block|inline|inline-block|inline-flex|inline-grid|hidden|absolute|relative|fixed|sticky|static|resize|appearance|list|underline|italic|uppercase|lowercase|capitalize|normal-case|break|border-collapse|table)(?:-|$)/

const isImportPath = (s) => s.includes('/') && /^(?:@|\.{1,2}\/|[a-z][\w-]*\/)/.test(s) && !s.includes('[')

for (const file of walk(SRC)) {
  if (!['.tsx', '.ts'].includes(extname(file))) continue
  const code = readFileSync(file, 'utf8')
  // elimina líneas de import para no capturar especificadores de módulo
  const body = code
    .split('\n')
    .filter((l) => !/^\s*(?:import|export)\b.*\bfrom\b/.test(l) && !/^\s*import\s+['"]/.test(l))
    .join('\n')

  const chunks = []
  for (const m of body.matchAll(classAttr)) chunks.push(m[1] ?? m[2] ?? m[3] ?? '')
  for (const m of body.matchAll(bareStrings)) chunks.push(m[1] ?? m[2] ?? '')

  for (const chunk of chunks) {
    for (const raw of chunk.split(/\s+/)) {
      const c = raw.trim()
      if (!c || isImportPath(c)) continue
      if (!TW_UTILITY.test(c)) continue
      if (c.includes('(') || c.includes('$') || c.includes(',')) continue
      if (!used.has(c)) used.set(c, new Set())
      used.get(c).add(file)
    }
  }
}

// 3. Reporta las que no existen en el CSS
const missing = []
for (const [cls, files] of used) {
  // separa variantes (hover:, sm:, etc.) del utility final
  const utility = cls.split(':').pop()
  if (!utility) continue
  if (generated.has(cls) || generated.has(utility)) continue
  // ignora clases propias definidas en index.css con @layer components
  if (
    [
      'container-page',
      'glass',
      'glass-strong',
      'text-gradient',
      'text-gradient-mint',
      'eyebrow',
      'gradient-border',
      'noise',
      'mask-fade-x',
      'mask-fade-b',
      'react-flow__attribution',
      // falsos positivos conocidos: nombres de campo TS / atributos SVG
      'accent',
      'opacity',
      // `'object'` aparece en comprobaciones `typeof x === 'object'`
      'object',
      'table',
    ].includes(utility)
  )
    continue
  missing.push({ cls, files: [...files] })
}

if (missing.length === 0) {
  console.log('OK: todas las clases usadas existen en el CSS generado.')
  process.exit(0)
}

console.log(`Posibles clases sin CSS generado (${missing.length}):\n`)
for (const m of missing) {
  console.log(`  ${m.cls}`)
  for (const f of m.files) console.log(`      ${f}`)
}
process.exit(1)
