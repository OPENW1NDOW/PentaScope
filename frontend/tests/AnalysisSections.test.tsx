import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnalysisSections } from '@/components/report/AnalysisSections'

const SECTIONS = [
  { section_id: 's1', heading: '章节一', narrative: '## 市场总览\n\n正文' },
  { section_id: 's2', heading: '章节二', narrative: '## 竞争格局\n\n正文' },
]

describe('AnalysisSections', () => {
  it('numbers h2 headings sequentially across sections', () => {
    render(<AnalysisSections sections={SECTIONS} />)
    expect(screen.getByText('一、市场总览')).toBeInTheDocument()
    expect(screen.getByText('二、竞争格局')).toBeInTheDocument()
  })

  it('resets numbering on re-render instead of accumulating', () => {
    const { rerender } = render(<AnalysisSections sections={SECTIONS} />)
    rerender(<AnalysisSections sections={SECTIONS} />)
    // 重渲染后编号必须仍从「一」开始，而不是累加成「三、四」
    expect(screen.getByText('一、市场总览')).toBeInTheDocument()
    expect(screen.getByText('二、竞争格局')).toBeInTheDocument()
    expect(screen.queryByText('三、市场总览')).not.toBeInTheDocument()
  })
})
