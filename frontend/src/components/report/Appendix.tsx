'use client'

import type { Appendix as AppendixType, DataSource, ConfidenceLevel } from '@/types'
import { ChevronRight, ExternalLink } from 'lucide-react'

interface AppendixProps {
  appendix: AppendixType
}

const CONFIDENCE_DOT: Record<ConfidenceLevel, string> = {
  high: 'bg-[var(--success)]',
  medium: 'bg-[var(--warning)]',
  low: 'bg-[var(--danger)]',
}

export function Appendix({ appendix }: AppendixProps) {
  const hasGlossary = appendix.glossary && Object.keys(appendix.glossary).length > 0
  const hasSources = appendix.data_sources_full && appendix.data_sources_full.length > 0
  const hasExhibits = appendix.additional_exhibits && appendix.additional_exhibits.length > 0

  if (!hasGlossary && !hasSources && !hasExhibits) return null

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        附录
      </h3>

      {/* Glossary */}
      {hasGlossary && (
        <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]">
          <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
            <ChevronRight
              size={14}
              strokeWidth={1.5}
              className="text-[var(--text-tertiary)] transition-transform details-open:rotate-90"
            />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              术语表
            </span>
          </summary>

          <div className="px-4 pb-4 border-t border-[var(--border-divider)]">
            <dl className="flex flex-col gap-2 pt-3">
              {Object.entries(appendix.glossary!).map(([term, def], i) => (
                <div key={i} className="flex flex-col gap-0.5">
                  <dt className="text-[13px] font-medium text-[var(--text-primary)]">
                    {term}
                  </dt>
                  <dd className="text-[13px] text-[var(--text-secondary)] leading-relaxed ml-0">
                    {def}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </details>
      )}

      {/* Data Sources Full */}
      {hasSources && (
        <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]" open>
          <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
            <ChevronRight
              size={14}
              strokeWidth={1.5}
              className="text-[var(--text-tertiary)] transition-transform details-open:rotate-90"
            />
            <span className="text-[13px] font-semibold text-[var(--text-primary)]">
              数据源完整列表
            </span>
            <span className="text-[11px] text-[var(--text-tertiary)]">
              ({appendix.data_sources_full!.length})
            </span>
          </summary>

          <div className="px-4 pb-4 border-t border-[var(--border-divider)]">
            <ul className="flex flex-col gap-2 pt-3">
              {appendix.data_sources_full!.map((ds, i) => (
                <SourceItem key={i} source={ds} />
              ))}
            </ul>
          </div>
        </details>
      )}

      {/* Additional Exhibits */}
      {hasExhibits && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
          <span className="text-[13px] font-semibold text-[var(--text-primary)] block mb-3">
            补充材料
          </span>
          <ul className="flex flex-col gap-1.5">
            {appendix.additional_exhibits!.map((ex, i) => (
              <li key={i} className="text-[13px] text-[var(--text-secondary)]">
                {ex.title ?? ex.artifact_id}
                {ex.description && (
                  <span className="text-[var(--text-tertiary)] ml-1">
                    — {ex.description}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function SourceItem({ source }: { source: DataSource }) {
  return (
    <li className="flex items-start gap-2 text-[13px]">
      {/* Confidence dot */}
      <span
        className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${CONFIDENCE_DOT[source.confidence ?? 'medium']}`}
        title={`可信度: ${source.confidence ?? 'medium'}`}
      />

      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center gap-1.5">
          {source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--info)] hover:underline inline-flex items-center gap-1 truncate max-w-full"
            >
              <span className="truncate">{source.title || source.url}</span>
              <ExternalLink size={11} strokeWidth={1.5} className="shrink-0" />
            </a>
          ) : (
            <span className="text-[var(--text-primary)] truncate">
              {source.title || '未知来源'}
            </span>
          )}
        </div>
        {source.source_type && (
          <span className="text-[11px] text-[var(--text-tertiary)]">
            {source.source_type}
          </span>
        )}
      </div>
    </li>
  )
}
