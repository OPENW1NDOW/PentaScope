/**
 * 枚举值翻译：英文 → "中文 (英文)" 格式
 * 移植自 src/utils/translations.py
 */

const TRANSLATIONS: Record<string, string> = {
  // 可信度
  high: "高 (high)",
  medium: "中 (medium)",
  low: "低 (low)",

  // S1 波次定位
  wave_leader: "领导者 (wave_leader)",
  wave_strong_performer: "强劲表现者 (wave_strong_performer)",
  wave_contender: "竞争者 (wave_contender)",
  wave_follower: "跟随者 (wave_follower)",

  // S2 市场角色
  incumbent: "在位者 (incumbent)",
  challenger: "挑战者 (challenger)",
  emerging: "新兴 (emerging)",
  niche: "利基 (niche)",
  substitute: "替代者 (substitute)",

  // 难度/地址性
  hard: "困难 (hard)",
  moderate: "适中 (moderate)",
  easy: "容易 (easy)",

  // 趋势方向
  up: "上升 ↑",
  down: "下降 ↓",
  flat: "持平 →",

  // 时间范围
  short_term: "短期 (short_term)",
  mid_term: "中期 (mid_term)",
  long_term: "长期 (long_term)",

  // 影响
  mixed: "混合 (mixed)",
  negative: "负面 (negative)",
  positive: "正面 (positive)",

  // 市场集中度
  concentrated: "集中 (concentrated)",
  fragmented: "分散 (fragmented)",

  // 优先级
  critical: "紧急 (critical)",
  important: "重要 (important)",
  consider: "可选 (consider)",

  // 定时线
  immediate: "立即 (immediate)",

  // MQ 象限
  mq_leader: "领导者 (mq_leader)",
  mq_challenger: "挑战者 (mq_challenger)",
  mq_visionary: "远见者 (mq_visionary)",
  mq_niche_player: "利基者 (mq_niche_player)",

  // 五力强度
  high_intensity: "高",
  medium_intensity: "中",
  low_intensity: "低",

  // 通用
  leaders: "领导者 (leaders)",
  challengers: "挑战者 (challengers)",
  visionaries: "远见者 (visionaries)",
  niche_players: "利基者 (niche_players)",

  // S3 定价模型
  per_seat: "按席位 (per_seat)",
  flat_rate: "固定费率 (flat_rate)",
  usage_based: "按用量 (usage_based)",
  freemium: "免费增值 (freemium)",
  platform_fee: "平台费 (platform_fee)",
  subscription: "订阅制 (subscription)",

  // 估算努力/影响
  // build/skip/differentiate
  build: "构建 (build)",
  skip: "跳过 (skip)",
  differentiate: "差异化 (differentiate)",
}

/**
 * 翻译枚举值为「中文 (英文)」格式
 * 非字符串或未命中则原样返回
 */
export function t(val: unknown): string {
  if (val == null) return ""
  const s = String(val)
  if (!s) return ""
  return TRANSLATIONS[s] ?? s
}
