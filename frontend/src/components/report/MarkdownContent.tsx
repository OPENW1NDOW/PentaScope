'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownContentProps {
  content?: string
  className?: string
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  if (!content) return null

  return (
    <div className={`prose-notion text-[14px] leading-relaxed text-[var(--text-primary)] ${className ?? ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-[20px] font-bold mt-6 mb-3 text-[var(--text-primary)]">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-[17px] font-semibold mt-5 mb-2 text-[var(--text-primary)]">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[15px] font-semibold mt-4 mb-2 text-[var(--text-primary)]">{children}</h3>
          ),
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
          code: ({ className: codeClassName, children, ...props }) => {
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
        {content}
      </ReactMarkdown>
    </div>
  )
}
