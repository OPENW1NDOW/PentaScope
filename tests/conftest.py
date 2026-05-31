"""Shared test fixtures for all test modules."""

import pytest


@pytest.fixture
def sample_competitor_basic():
    """Basic competitor input dict matching CompetitorBasic schema."""
    return {
        "name": "支付宝",
        "company": "蚂蚁集团",
        "category": "金融科技",
    }


@pytest.fixture
def sample_analysis_context():
    """Natural language analysis intent."""
    return "分析支付宝最近的新功能，我们准备做一个类似的功能"


@pytest.fixture
def sample_competitor_profile():
    """Complete CompetitorProfile dict matching the PRD schema."""
    return {
        "classification": {
            "competitor_type": "核心竞品",
            "reason": "同为支付赛道头部产品，功能重叠度高",
        },
        "basic_info": {
            "name": "支付宝",
            "company": "蚂蚁集团",
            "version": "10.5.80",
            "release_date": "2026-05-10",
            "platform": ["iOS", "Android"],
        },
        "feature_tree": [
            {
                "module": "支付",
                "features": [
                    {
                        "name": "扫码支付",
                        "description": "支持二维码和条形码扫描完成支付",
                        "is_new": False,
                        "source_url": "https://www.alipay.com/features",
                    }
                ],
            }
        ],
        "pricing": {
            "model": "免费增值",
            "tiers": [
                {
                    "name": "基础版",
                    "price": "免费",
                    "features": ["扫码支付", "转账"],
                }
            ],
            "source_url": "https://www.alipay.com/pricing",
        },
        "user_reviews": {
            "rating": 4.5,
            "total_reviews": 100000,
            "positive_summary": "支付便捷、功能丰富、生态完善",
            "negative_summary": "广告较多、部分功能入口深",
            "sample_reviews": [
                {
                    "content": "日常支付很方便，几乎离不开",
                    "rating": 5,
                    "source": "App Store",
                    "source_url": "https://apps.apple.com/review/1",
                }
            ],
        },
        "recent_updates": [
            {
                "date": "2026-05-01",
                "title": "新增智能推荐功能",
                "summary": "基于用户习惯推荐常用功能和服务",
                "source_url": "https://www.alipay.com/changelog",
            }
        ],
        "metadata": {
            "collected_at": "2026-05-31T12:00:00Z",
            "data_sources": ["app_store", "official_site"],
            "completeness_score": 0.85,
        },
    }


@pytest.fixture
def sample_competitive_analysis():
    """Complete CompetitiveAnalysis dict matching the PRD schema."""
    return {
        "positioning": {
            "per_competitor": [
                {
                    "name": "支付宝",
                    "target_users": "中国主流消费群体，18-55岁",
                    "core_scenario": "日常支付、生活服务",
                    "pain_points": "传统支付方式效率低、线下消费不便",
                    "value_proposition": "让支付更简单，让生活更美好",
                }
            ],
            "source_urls": ["https://www.alipay.com"],
        },
        "feature_matrix": [
            {
                "feature": "扫码支付",
                "our_product": "有",
                "competitors": {"支付宝": "有"},
                "gap_level": "落后",
                "evidence": "支付宝在扫码支付体验上更流畅",
                "source_urls": ["https://www.alipay.com/features"],
            }
        ],
        "business_model": {
            "per_competitor": [
                {
                    "name": "支付宝",
                    "revenue_model": "广告+增值服务",
                    "pricing_details": "基础服务免费，高级功能付费",
                    "free_vs_paid": "核心支付免费，会员享受权益",
                }
            ],
            "source_urls": ["https://www.alipay.com/pricing"],
        },
        "operations": {
            "per_competitor": [
                {
                    "name": "支付宝",
                    "growth_strategy": "生态绑定+社交裂变",
                    "marketing_channels": "线下推广、社交媒体、合作伙伴",
                    "content_strategy": "生活场景化内容",
                }
            ],
            "source_urls": ["https://36kr.com/p/123456"],
        },
        "user_sentiment": {
            "summary": "支付宝整体口碑较好，用户对其支付便捷性认可度高",
            "per_competitor": {"支付宝": "正面为主，便捷性获好评"},
            "source_urls": ["https://weibo.com/alipay"],
        },
        "swot": {
            "strengths": [
                {
                    "point": "生态完善",
                    "evidence": "覆盖支付、理财、生活服务等多场景",
                    "dimension": "positioning",
                    "source_urls": ["https://www.alipay.com"],
                }
            ],
            "weaknesses": [
                {
                    "point": "广告过多",
                    "evidence": "用户反馈界面广告影响体验",
                    "dimension": "feature",
                    "source_urls": ["https://weibo.com/alipay"],
                }
            ],
            "opportunities": [
                {
                    "point": "海外市场",
                    "evidence": "东南亚数字支付增长迅速",
                    "dimension": "operations",
                    "source_urls": ["https://36kr.com/p/789"],
                }
            ],
            "threats": [
                {
                    "point": "微信支付竞争",
                    "evidence": "微信支付市场份额持续增长",
                    "dimension": "positioning",
                    "source_urls": ["https://36kr.com/p/456"],
                }
            ],
        },
        "radar_scores": [
            {
                "competitor": "支付宝",
                "dimensions": {
                    "feature_breadth": 4.5,
                    "usability": 4.0,
                    "cost_effectiveness": 4.2,
                    "stability": 4.8,
                    "design_quality": 4.0,
                },
            }
        ],
    }


@pytest.fixture
def sample_final_report():
    """Complete FinalReport dict matching the PRD schema."""
    return {
        "title": "支付宝竞品分析报告",
        "executive_summary": {
            "what_competitors_did_right": "支付宝在生态建设和支付体验上做到了极致",
            "what_competitors_did_wrong": "界面广告过多，部分功能入口过深",
            "our_opportunities": "聚焦细分场景，打造差异化支付体验",
            "next_steps_summary": "优先优化核心支付流程，提升用户满意度",
        },
        "sections": [
            {
                "title": "产品定位分析",
                "content": "## 产品定位\n\n支付宝定位为综合性金融服务平台...",
                "source_refs": ["1", "2"],
            }
        ],
        "action_items": {
            "immediate": [
                {
                    "priority": "高",
                    "description": "优化扫码支付流程",
                    "rationale": "这是用户最高频使用的功能",
                    "source_urls": ["https://www.alipay.com/features"],
                }
            ],
            "short_term": [
                {
                    "priority": "中",
                    "description": "增加智能推荐功能",
                    "rationale": "提升用户粘性和活跃度",
                    "source_urls": ["https://www.alipay.com/changelog"],
                }
            ],
            "long_term": [
                {
                    "priority": "低",
                    "description": "拓展生活服务生态",
                    "rationale": "参考支付宝的生态策略",
                    "source_urls": ["https://36kr.com/p/123"],
                }
            ],
        },
        "metadata": {
            "competitors_analyzed": ["支付宝"],
            "analysis_goal": {
                "goal_type": "feature_iteration",
                "product_stage": "growing",
                "focus_area": "支付功能",
                "output_expectation": "action",
            },
            "generated_at": "2026-05-31T12:00:00Z",
            "data_sources": [
                "https://www.alipay.com",
                "https://www.alipay.com/features",
            ],
            "quality_score": 0.85,
            "warnings": [],
        },
    }
