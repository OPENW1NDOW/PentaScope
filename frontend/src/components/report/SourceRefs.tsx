'use client'

import type { SourceRef } from '@/types'

interface SourceRefsProps {
  refs?: SourceRef[]
  /** Render inline (default) or as a block list */
  variant?: 'inline' | 'block'
}

function getLabel(ref: SourceRef, index: number): string {
  if (ref.title) return ref.title
  try {
    const domain = new URL(ref.url).hostname
    return domain
  } catch {
    return `来源 ${index + 1}`
  }
}

export function SourceRefs({ refs, variant = 'inline' }: SourceRefsProps) {
  if (!refs || refs.length === 0) return null

  if (variant === 'block') {
    return (
      <ul className="flex flex-col gap-1">
        {refs.map((ref, i) => (
          <li key={i} className="text-[12px] text-[var(--text-secondary)]">
            <a
              href={ref.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline decoration-[var(--text-tertiary)]"
            >
              {getLabel(ref, i)}
            </a>
          </li>
        ))}
      </ul>
    )
  }

  const labels = refs.map((ref, i) => {
    const label = getLabel(ref, i)
    return (
      <a
        key={i}
        href={ref.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:underline decoration-[var(--text-tertiary)]"
      >
        {label}
      </a>
    )
  })

  return (
    <span className="text-[12px] text-[var(--text-tertiary)]">
      来源：
      {labels.reduce<React.ReactNode[]>((acc, el, i) => {
        if (i > 0) acc.push(<span key={`sep-${i}`} className="mx-1">{'·'}</span>)
        acc.push(el)
        return acc
      }, [])}
    </span>
  )
}
