from datetime import date
import pytest
from pydantic import ValidationError
from src.schemas.common import SourceRef, ArtifactBase, DataSource, Revision, Exhibit


def test_source_ref_min_url_length():
    """SourceRef.url 最小长度 8（http(s)://）"""
    with pytest.raises(ValidationError):
        SourceRef(url="short")
    sr = SourceRef(url="https://x")
    assert sr.url == "https://x"


def test_source_ref_default_source_type():
    sr = SourceRef(url="https://example.com")
    assert sr.source_type == "other"


def test_source_ref_optional_accessed_at():
    sr = SourceRef(url="https://example.com", accessed_at=date(2026, 6, 7))
    assert sr.accessed_at == date(2026, 6, 7)


def test_artifact_base_id_constraints():
    """ArtifactBase.artifact_id 长度 3-40"""
    with pytest.raises(ValidationError):
        ArtifactBase(artifact_id="ab", artifact_type="x")
    with pytest.raises(ValidationError):
        ArtifactBase(artifact_id="a" * 41, artifact_type="x")
    a = ArtifactBase(artifact_id="abc", artifact_type="feature_matrix")
    assert a.artifact_id == "abc"


def test_data_source_default_confidence():
    ds = DataSource(url="https://example.com")
    assert ds.confidence == "medium"


def test_revision_required_fields():
    r = Revision(revision_date=date(2026, 6, 7), change_summary="initial", triggered_by="initial")
    assert r.triggered_by == "initial"


def test_exhibit_inherits_artifact_base():
    e = Exhibit(artifact_id="ex1", title="Test")
    assert e.artifact_type == "exhibit"
