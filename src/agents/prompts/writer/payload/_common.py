"""5 场景 payload 共用的溯源约束块。"""

SOURCE_REFS_PROTOCOL = """
【溯源 URL 强约束（编造 URL 视为严重违规）】

1. 任何 evidence_url / SourceRef.url / source_url 字段，**只能填**输入的 profiles_source_urls 列表中实际存在的 URL。
2. profiles_source_urls 列表见下方注入的 {discovered_urls_json}，请只用这些 URL，不要编造。
3. SourceRef 对象格式（source_refs 字段下的每条）：
   {{
     "url": "必须来自 profiles_source_urls",
     "title": "未知时填空字符串",
     "source_type": "official_website | third_party_review | industry_report | news | user_review | regulatory | other（不确定填 other）",
     "accessed_at": "未知时省略"
   }}
4. 如果某条目（如 ObservedCompetitorTier、FeatureChange、ConsumerSegment 等 source_refs 必填的）找不到 ≥1 个合法 URL，**不要生成该条目**。宁缺勿滥。
"""
