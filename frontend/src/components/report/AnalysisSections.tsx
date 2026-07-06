'use client'

import { MarkdownContent } from './MarkdownContent'
import { formatParenthesizedHeading } from './stripNumberPrefix'

interface AnalysisSectionsProps {
  sections: { heading: string; narrative: string; section_id: string }[]
}

export function AnalysisSections({ sections }: AnalysisSectionsProps) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 flex flex-col gap-6">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">
        详细分析
      </h3>
      <div className="flex flex-col gap-6">
        {sections.map((section, i) => (
          <div key={section.section_id || i} className="flex flex-col gap-2">
            <h4 className="text-[14px] font-semibold text-[var(--text-primary)] border-b border-[var(--border-divider)] pb-2">
              {formatParenthesizedHeading(i + 1, section.heading)}
            </h4>
            {/* narrative 对齐 Streamlit：st.markdown 原样渲染，不跨 section 累加编号 */}
            <MarkdownContent content={section.narrative} renumberHeadings={false} />
          </div>
        ))}
      </div>
    </div>
  )
}
