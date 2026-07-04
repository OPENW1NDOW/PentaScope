import { describe, it, expect } from 'vitest'
import { stripNumberPrefix } from '@/components/report/stripNumberPrefix'

describe('stripNumberPrefix', () => {
  it('strips Chinese numeral prefix "一、"', () => {
    expect(stripNumberPrefix('一、企业协同办公市场总览')).toBe('企业协同办公市场总览')
  })

  it('strips parenthesized Chinese numeral prefix "（一）"', () => {
    expect(stripNumberPrefix('（一）企业协同办公市场总览')).toBe('企业协同办公市场总览')
  })

  it('strips Arabic numeral prefix "1."', () => {
    expect(stripNumberPrefix('1. 竞争格局')).toBe('竞争格局')
  })

  it('strips Arabic numeral prefix "1、"', () => {
    expect(stripNumberPrefix('1、竞争格局')).toBe('竞争格局')
  })

  it('strips Arabic numeral prefix "1．" (fullwidth dot)', () => {
    expect(stripNumberPrefix('1．竞争格局')).toBe('竞争格局')
  })

  it('strips prefix from multi-digit numbers like "10、"', () => {
    expect(stripNumberPrefix('10、第十章')).toBe('第十章')
  })

  it('does not strip non-prefix text', () => {
    expect(stripNumberPrefix('竞争格局：定位清晰')).toBe('竞争格局：定位清晰')
  })

  it('does not strip numbers in the middle of text', () => {
    expect(stripNumberPrefix('第2章 概述')).toBe('第2章 概述')
  })

  it('handles multi-line markdown content', () => {
    const input = '## 一、市场总览\n\n正文内容\n\n## （二）竞争格局\n\n更多正文'
    const expected = '## 市场总览\n\n正文内容\n\n## 竞争格局\n\n更多正文'
    expect(stripNumberPrefix(input)).toBe(expected)
  })

  it('handles empty string', () => {
    expect(stripNumberPrefix('')).toBe('')
  })

  it('handles content without headings', () => {
    const input = '这是一段普通文本，没有标题。'
    expect(stripNumberPrefix(input)).toBe(input)
  })

  it('strips prefix after markdown heading markers', () => {
    expect(stripNumberPrefix('## 一、标题')).toBe('## 标题')
    expect(stripNumberPrefix('### （三）子标题')).toBe('### 子标题')
    expect(stripNumberPrefix('#### 2. 小节')).toBe('#### 小节')
  })
})
