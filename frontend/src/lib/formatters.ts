/**
 * 数据格式化工具函数
 */

import type { MarketValue, Trend } from "@/types";

const UNIT_MAP: Record<string, string> = {
  billion: "B",
  million: "M",
  thousand: "K",
  raw: "",
};

const CURRENCY_SYMBOL: Record<string, string> = {
  USD: "$",
  CNY: "¥",
  EUR: "€",
  JPY: "¥",
  unknown: "",
};

/** 格式化市场价值为 "{amount}{unit}{currency}" */
export function formatMarketValue(val: MarketValue | null | undefined): string {
  if (!val || val.amount == null) return "—";
  const symbol = CURRENCY_SYMBOL[val.currency ?? "unknown"] ?? "";
  const unit = UNIT_MAP[val.unit ?? "raw"] ?? "";
  return `${symbol}${val.amount}${unit}`;
}

/** 趋势箭头 */
export function trendArrow(direction: string | undefined): string {
  switch (direction) {
    case "up":
      return "↑";
    case "down":
      return "↓";
    case "flat":
      return "→";
    default:
      return "";
  }
}

/** 强度映射为数值（五力图用） */
export function intensityToNum(intensity: string | undefined): number {
  switch (intensity) {
    case "high":
      return 5;
    case "medium":
      return 3;
    case "low":
      return 1;
    default:
      return 0;
  }
}

/** 格式化百分比 */
export function formatPct(val: number | null | undefined): string {
  if (val == null) return "—";
  return `${val.toFixed(1)}%`;
}

/** 截断文本 */
export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 1) + "…";
}
