'use client'

import { MarkdownContent } from './MarkdownContent'

interface AnalysisSectionsProps {
  sections: { heading: string; narrative: string; section_id: string }[]
}

export function AnalysisSections({ sections }: AnalysisSectionsProps) {
  // 每次渲染新建计数器：编号在单次渲染内跨 section 连续，且重渲染时从头计数。
  // 不能用 useRef——ref 跨渲染保留会导致 re-render 时编号继续累加（一、二 → 三、四）。
  const counter = { h2: 0, h3: 0, h4: 0 }

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 flex flex-col gap-6">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        详细分析
      </h3>
      <div className="flex flex-col gap-6">
        {sections.map((section, i) => (
          <div key={section.section_id || i} className="flex flex-col gap-2">
            <h4 className="text-[14px] font-semibold text-[var(--text-primary)] border-b border-[var(--border-divider)] pb-2">
              {section.heading}
            </h4>
            <MarkdownContent content={section.narrative} headingCounter={counter} />
          </div>
        ))}
      </div>
    </div>
  )
}
