'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { stripNumberPrefix } from './stripNumberPrefix'

export interface HeadingCounter {
  h2: number
  h3: number
  h4: number
}

interface MarkdownContentProps {
  content?: string
  className?: string
  /** 外部共享的标题计数器，跨 section 连续编号。不传则内部自建（独立计数）。 */
  headingCounter?: HeadingCounter
}

const CN_NUMBERS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
function cnNumber(index: number): string {
  return CN_NUMBERS[index - 1] ?? String(index)
}

export function MarkdownContent({ content, className, headingCounter: externalCounter }: MarkdownContentProps) {
  if (!content) return null

  // 剥离 LLM 已写的编号前缀，由前端统一重新编号
  const cleaned = stripNumberPrefix(content)

  // 外部不传 counter 时内部自建（向后兼容，独立计数）
  const counter = externalCounter ?? { h2: 0, h3: 0, h4: 0 }

  return (
    <div className={`prose-notion text-[14px] leading-relaxed text-[var(--text-primary)] ${className ?? ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-[20px] font-bold mt-6 mb-3 text-[var(--text-primary)]">{children}</h1>
          ),
          h2: ({ children }) => {
            counter.h2 += 1
            counter.h3 = 0
            counter.h4 = 0
            return (
              <h2 className="text-[18px] font-bold mt-6 mb-3 pl-3 border-l-[3px] border-[var(--border-active)] pb-1 border-b border-[var(--border-divider)] text-[var(--text-primary)]">
                {cnNumber(counter.h2)}、{children}
              </h2>
            )
          },
          h3: ({ children }) => {
            counter.h3 += 1
            counter.h4 = 0
            return (
              <h3 className="text-[16px] font-semibold mt-5 mb-2 pl-3 border-l-2 border-[var(--border-active)] text-[var(--text-primary)]">
                （{cnNumber(counter.h3)}）{children}
              </h3>
            )
          },
          h4: ({ children }) => {
            counter.h4 += 1
            return (
              <h4 className="text-[14px] font-semibold mt-3 mb-1.5 text-[var(--text-primary)]">
                {counter.h4}. {children}
              </h4>
            )
          },
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-inside mb-3 flex flex-col gap-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside mb-3 flex flex-col gap-1">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed">{children}</li>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--info)] hover:underline"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-3 border-[var(--border-active)] pl-4 my-3 text-[var(--text-secondary)] italic">
              {children}
            </blockquote>
          ),
          code: ({ className: codeClassName, children }) => {
            const isInline = !codeClassName
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 rounded-[var(--radius-sm)] bg-[var(--bg-hover)] text-[13px] font-[var(--font-mono)]">
                  {children}
                </code>
              )
            }
            return (
              <code className={`${codeClassName} block p-3 rounded-[var(--radius-md)] bg-[var(--bg-hover)] text-[13px] font-[var(--font-mono)] overflow-x-auto my-3`}>
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre className="rounded-[var(--radius-md)] bg-[var(--bg-hover)] overflow-x-auto my-3">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full text-[13px] border-collapse">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-[var(--border-default)]">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-left font-semibold text-[var(--text-primary)]">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 border-b border-[var(--border-divider)]">{children}</td>
          ),
          hr: () => (
            <hr className="my-4 border-0 border-t border-[var(--border-divider)]" />
          ),
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  )
}
