'use client'

import type { ReportScope, Methodology } from '@/types'
import { Crosshair, ChevronRight } from 'lucide-react'

interface ScopeMethodologyProps {
  scope: ReportScope
  methodology: Methodology
}

export function ScopeMethodology({ scope, methodology }: ScopeMethodologyProps) {
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        范围与方法论
      </h3>

      {/* Scope */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <Crosshair size={14} strokeWidth={1.5} className="text-[var(--text-tertiary)]" />
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            分析范围
          </span>
        </div>

        <div className="flex flex-col gap-3">
          {/* Competitors */}
          <div className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
              竞品
            </span>
            <div className="flex flex-wrap gap-1.5">
              {scope.competitors.map((c, i) => (
                <span
                  key={i}
                  className="tag-blue text-[12px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>

          {/* Time Window */}
          <div className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
              时间窗口
            </span>
            <span className="text-[13px] text-[var(--text-secondary)]">
              {scope.time_window}
            </span>
          </div>

          {/* Regions */}
          {scope.regions && scope.regions.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
                区域
              </span>
              <div className="flex flex-wrap gap-1.5">
                {scope.regions.map((r, i) => (
                  <span
                    key={i}
                    className="tag-purple text-[12px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)]"
                  >
                    {r}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Exclusions */}
          {scope.exclusions && scope.exclusions.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
                排除项
              </span>
              <ul className="list-none flex flex-col gap-0.5">
                {scope.exclusions.map((e, i) => (
                  <li key={i} className="text-[13px] text-[var(--text-secondary)] before:content-['-'] before:mr-1 before:text-[var(--text-tertiary)]">
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Methodology - collapsible */}
      <details className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)]">
        <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
          <ChevronRight
            size={14}
            strokeWidth={1.5}
            className="text-[var(--text-tertiary)] transition-transform details-open:rotate-90"
          />
          <span className="text-[13px] font-semibold text-[var(--text-primary)]">
            方法论
          </span>
        </summary>

        <div className="px-4 pb-4 flex flex-col gap-3 border-t border-[var(--border-divider)]">
          {methodology.data_collection_approach && (
            <MethodologyField
              label="数据采集方式"
              value={methodology.data_collection_approach}
            />
          )}

          <MethodologyField
            label="评估标准"
            items={methodology.evaluation_criteria}
          />

          <MethodologyField
            label="局限性"
            items={methodology.limitations}
            danger
          />

          {methodology.sample_size_note && (
            <MethodologyField
              label="样本说明"
              value={methodology.sample_size_note}
            />
          )}

          {methodology.analyst_disclosure && (
            <MethodologyField
              label="分析师声明"
              value={methodology.analyst_disclosure}
              italic
            />
          )}
        </div>
      </details>
    </div>
  )
}

function MethodologyField({
  label,
  value,
  items,
  danger,
  italic,
}: {
  label: string
  value?: string
  items?: string[]
  danger?: boolean
  italic?: boolean
}) {
  return (
    <div className="flex flex-col gap-1 pt-3 first:pt-0">
      <span className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] font-medium">
        {label}
      </span>
      {value && (
        <p className={`text-[13px] leading-relaxed ${danger ? 'text-[var(--danger)]' : 'text-[var(--text-secondary)]'} ${italic ? 'italic' : ''}`}>
          {value}
        </p>
      )}
      {items && items.length > 0 && (
        <ul className="list-none flex flex-col gap-0.5">
          {items.map((item, i) => (
            <li
              key={i}
              className={`text-[13px] leading-relaxed ${danger ? 'text-[var(--danger)]' : 'text-[var(--text-secondary)]'} before:content-['-'] before:mr-1 before:text-[var(--text-tertiary)]`}
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
