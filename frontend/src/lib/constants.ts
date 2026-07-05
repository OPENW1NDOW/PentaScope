/** graph 节点 → 中文名（与后端 src/graph/builder.py 节点名对应） */
export const NODE_LABELS: Record<string, string> = {
  set_entry: '场景路由',
  recommender: '竞品推荐',
  collector: '信息采集',
  analyzer: '竞品分析',
  writer: '报告撰写',
  inspector: '质检审核',
}

/** 主流水线节点顺序（S2 场景在 collector 前多一个 recommender） */
export const PIPELINE_NODES = ['collector', 'analyzer', 'writer', 'inspector'] as const
export const PIPELINE_NODES_S2 = ['recommender', ...PIPELINE_NODES] as const
