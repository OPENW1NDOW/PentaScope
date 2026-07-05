'use client'

// global-error 替换整个根布局渲染，必须自带 <html>/<body>
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="zh-CN">
      <body style={{ fontFamily: 'system-ui, sans-serif', background: '#F7F6F3', color: '#37352F' }}>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            gap: 12,
            padding: 24,
          }}
        >
          <p style={{ fontSize: 16, fontWeight: 600 }}>应用发生严重错误</p>
          <p style={{ fontSize: 13, color: '#787774', maxWidth: 480, textAlign: 'center', wordBreak: 'break-all' }}>
            {error.message || '未知错误'}
          </p>
          <button
            onClick={reset}
            style={{
              padding: '6px 14px',
              fontSize: 13,
              fontWeight: 500,
              borderRadius: 4,
              border: '1px solid #E9E9E7',
              background: '#FFFFFF',
              cursor: 'pointer',
            }}
          >
            重新加载
          </button>
        </div>
      </body>
    </html>
  )
}
