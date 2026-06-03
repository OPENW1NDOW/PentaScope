from src.schemas.profile import ProfileMetadata


def test_metadata_accepts_pipeline_trace():
    meta = ProfileMetadata(
        collected_at="2026-06-03T10:00:00",
        pipeline_trace=[{"step": "search", "provider": "serpapi", "candidates": 5}],
    )
    assert meta.pipeline_trace == [{"step": "search", "provider": "serpapi", "candidates": 5}]


def test_metadata_pipeline_trace_defaults_empty():
    meta = ProfileMetadata(collected_at="2026-06-03T10:00:00")
    assert meta.pipeline_trace == []
