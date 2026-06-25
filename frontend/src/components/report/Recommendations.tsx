'use client'

import type { Recommendation } from '@/types'
import { PRIORITY_CONFIG, TIMELINE_CONFIG } from '@/types'
import { SourceRefs } from './SourceRefs'
import { Clock, Users } from 'lucide-react'

interface RecommendationsProps {
  recommendations?: Recommendation[]
}

const PRIORITY_STYLE: Record<string, string> = {
  critical: 'tag-red',
  important: 'tag-orange',
  consider: 'tag-blue',
}

const TIMELINE_ORDER: Recommendation['timeline'][] = ['immediate', 'short_term', 'long_term']

function groupByTimeline(items: Recommendation[]): Map<Recommendation['timeline'], Recommendation[]> {
  const map = new Map<Recommendation['timeline'], Recommendation[]>()
  for (const item of items) {
    const list = map.get(item.timeline) ?? []
    list.push(item)
    map.set(item.timeline, list)
  }
  return map
}

export function Recommendations({ recommendations }: RecommendationsProps) {
  if (!recommendations || recommendations.length === 0) return null

  const grouped = groupByTimeline(recommendations)

  return (
    <div className="flex flex-col gap-5">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        行动建议
      </h3>

      {TIMELINE_ORDER.map((timeline) => {
        const items = grouped.get(timeline)
        if (!items || items.length === 0) return null

        return (
          <div key={timeline} className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Clock size={14} strokeWidth={1.5} className="text-[var(--text-tertiary)]" />
              <span className="text-[13px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
                {TIMELINE_CONFIG[timeline].label}
              </span>
            </div>

            <div className="flex flex-col gap-2">
              {items.map((rec, i) => (
                <div
                  key={i}
                  className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-4 flex flex-col gap-2.5"
                >
                  {/* Top row: priority + target */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[12px] font-medium px-2 py-0.5 rounded-[var(--radius-sm)] ${PRIORITY_STYLE[rec.priority]}`}>
                      {PRIORITY_CONFIG[rec.priority].label}
                    </span>
                    {rec.target_role && (
                      <span className="inline-flex items-center gap-1 text-[12px] text-[var(--text-tertiary)]">
                        <Users size={12} strokeWidth={1.5} />
                        {rec.target_role}
                      </span>
                    )}
                  </div>

                  {/* Action */}
                  <p className="text-[14px] font-medium text-[var(--text-primary)] leading-snug">
                    {rec.action}
                  </p>

                  {/* Rationale */}
                  {rec.rationale && (
                    <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed">
                      {rec.rationale}
                    </p>
                  )}

                  {/* Sources */}
                  {rec.source_refs && rec.source_refs.length > 0 && (
                    <div className="pt-1 border-t border-[var(--border-divider)]">
                      <SourceRefs refs={rec.source_refs} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
