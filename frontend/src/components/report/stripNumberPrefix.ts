/**
 * 剥离 markdown 文本中标题行的编号前缀。
 *
 * 支持的前缀格式：
 * - 中文数字：一、二、三、...、十、十一、...
 * - 带括号中文数字：（一）、（二）、...
 * - 阿拉伯数字：1.  1、  1．  10. 等
 *
 * 只处理行首或 markdown heading marker（# / ## / ### 等）之后的前缀，
 * 正文中的数字不受影响。
 */

// 匹配 heading marker 之后的编号前缀
// 组1: heading marker（可选，如 "## "）
// 组2: 编号前缀本身（如 "一、"、"（二）"、"3. "）
const HEADING_PREFIX_RE = /^(#{1,6}\s+)?(?:([一二三四五六七八九十百千万零〇两]+[、.．]\s*)|（([一二三四五六七八九十百千万零〇两]+)）\s*|(\d+[、.．]\s*))/

export function stripNumberPrefix(text: string): string {
  if (!text) return text

  return text
    .split('\n')
    .map((line) => {
      const match = line.match(HEADING_PREFIX_RE)
      if (!match) return line
      // 保留 heading marker（如果有），去掉编号前缀
      const marker = match[1] ?? ''
      const rest = line.slice(match[0].length)
      return marker + rest
    })
    .join('\n')
}
