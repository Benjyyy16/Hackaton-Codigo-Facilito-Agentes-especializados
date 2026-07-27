import { useEffect, useRef } from 'react'

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * Atrapa el foco dentro de un contenedor mientras `active` sea true y lo
 * devuelve al elemento que lo tenía al cerrar. Requisito de a11y para modals:
 * sin esto, Tab lleva el foco a la página de fondo.
 */
export function useFocusTrap<T extends HTMLElement>(active: boolean) {
  const ref = useRef<T | null>(null)

  useEffect(() => {
    if (!active) return
    const node = ref.current
    if (!node) return

    const previouslyFocused = document.activeElement as HTMLElement | null

    const focusables = () =>
      Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      )

    // Foco inicial en el primer control del modal
    const first = focusables()[0]
    if (first) first.focus()
    else {
      node.setAttribute('tabindex', '-1')
      node.focus()
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) {
        e.preventDefault()
        return
      }
      const firstEl = items[0]
      const lastEl = items[items.length - 1]
      const current = document.activeElement

      if (e.shiftKey && (current === firstEl || !node.contains(current))) {
        e.preventDefault()
        lastEl.focus()
      } else if (!e.shiftKey && current === lastEl) {
        e.preventDefault()
        firstEl.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previouslyFocused?.focus?.()
    }
  }, [active])

  return ref
}
