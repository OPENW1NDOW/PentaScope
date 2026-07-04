import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MarkdownContent } from '@/components/report/MarkdownContent'
import type { HeadingCounter } from '@/components/report/MarkdownContent'

describe('MarkdownContent', () => {
  it('renders plain text without headings', () => {
    render(<MarkdownContent content="这是一段普通文本" />)
    expect(screen.getByText('这是一段普通文本')).toBeInTheDocument()
  })

  it('returns null for empty content', () => {
    const { container } = render(<MarkdownContent content="" />)
    expect(container.firstChild).toBeNull()
  })

  it('returns null for undefined content', () => {
    const { container } = render(<MarkdownContent content={undefined} />)
    expect(container.firstChild).toBeNull()
  })

  it('strips LLM-written number prefix and re-numbers h2 from 一', () => {
    // LLM 输出了"（二）"前缀，前端应剥离后从"一"重新编号
    render(<MarkdownContent content="## （二）竞争格局" />)
    // 应该显示"一、竞争格局"而非"（二）竞争格局"
    expect(screen.getByText('一、竞争格局')).toBeInTheDocument()
  })

  it('strips multiple prefixes and numbers sequentially', () => {
    const content = '## 一、市场总览\n\n正文\n\n## （三）竞争格局'
    render(<MarkdownContent content={content} />)
    expect(screen.getByText('一、市场总览')).toBeInTheDocument()
    expect(screen.getByText('二、竞争格局')).toBeInTheDocument()
  })

  it('numbers h3 with parenthesized Chinese numerals', () => {
    render(<MarkdownContent content="### 子标题" />)
    expect(screen.getByText('（一）子标题')).toBeInTheDocument()
  })

  it('numbers h4 with Arabic numerals', () => {
    render(<MarkdownContent content="#### 小节标题" />)
    expect(screen.getByText('1. 小节标题')).toBeInTheDocument()
  })

  it('resets h3 counter when h2 increments', () => {
    const content = '## 标题一\n\n### 子A\n\n## 标题二\n\n### 子B'
    render(<MarkdownContent content={content} />)
    // 两个 h3 都应该从（一）开始（各自 h2 下的第一个）
    expect(screen.getAllByText('（一）子A').length).toBe(1)
    expect(screen.getAllByText('（一）子B').length).toBe(1)
  })

  it('accepts external headingCounter for cross-section continuity', () => {
    const counter: HeadingCounter = { h2: 2, h3: 0, h4: 0 }
    render(<MarkdownContent content="## 新标题" headingCounter={counter} />)
    // counter.h2 从 2 开始，所以应该编号为"三"
    expect(screen.getByText('三、新标题')).toBeInTheDocument()
    expect(counter.h2).toBe(3)
  })

  it('external counter is shared across multiple MarkdownContent instances', () => {
    const counter: HeadingCounter = { h2: 0, h3: 0, h4: 0 }
    const { rerender } = render(<MarkdownContent content="## 第一节" headingCounter={counter} />)
    expect(screen.getByText('一、第一节')).toBeInTheDocument()

    rerender(<MarkdownContent content="## 第二节" headingCounter={counter} />)
    expect(screen.getByText('二、第二节')).toBeInTheDocument()
  })
})
