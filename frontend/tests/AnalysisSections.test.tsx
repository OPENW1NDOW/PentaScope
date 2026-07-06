import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnalysisSections } from '@/components/report/AnalysisSections'

const SECTIONS = [
  { section_id: 's1', heading: '总览分析', narrative: '### 开场结论\n\n正文' },
  { section_id: 's2', heading: '竞品档案', narrative: '### 头部玩家\n\n正文' },
  { section_id: 's3', heading: '功能矩阵', narrative: '### 加权得分\n\n正文' },
]

describe('AnalysisSections', () => {
  it('numbers section headings as (一)(二)(三) like Streamlit _hc.h3', () => {
    render(<AnalysisSections sections={SECTIONS} />)
    expect(screen.getByText('（一）总览分析')).toBeInTheDocument()
    expect(screen.getByText('（二）竞品档案')).toBeInTheDocument()
    expect(screen.getByText('（三）功能矩阵')).toBeInTheDocument()
  })

  it('does not inject cross-section numbering into narrative subheadings', () => {
    render(<AnalysisSections sections={SECTIONS} />)
    expect(screen.getByText('开场结论')).toBeInTheDocument()
    expect(screen.getByText('头部玩家')).toBeInTheDocument()
    expect(screen.queryByText('（二）开场结论')).not.toBeInTheDocument()
    expect(screen.queryByText('（四）头部玩家')).not.toBeInTheDocument()
  })

  it('resets section heading numbering on re-render', () => {
    const { rerender } = render(<AnalysisSections sections={SECTIONS} />)
    rerender(<AnalysisSections sections={SECTIONS} />)
    expect(screen.getByText('（一）总览分析')).toBeInTheDocument()
    expect(screen.queryByText('（四）总览分析')).not.toBeInTheDocument()
  })
})
