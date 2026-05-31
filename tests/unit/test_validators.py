import pytest
from pydantic import BaseModel, Field
from src.tools.validators import SchemaValidator, UrlValidator


class DummySchema(BaseModel):
    name: str
    value: int = Field(ge=0)


class TestSchemaValidator:
    def test_validate_valid(self):
        result = SchemaValidator.validate(DummySchema, {"name": "test", "value": 1})
        assert result.name == "test"

    def test_validate_invalid(self):
        with pytest.raises(ValueError):
            SchemaValidator.validate(DummySchema, {"name": "test", "value": -1})

    def test_validate_missing_field(self):
        with pytest.raises(ValueError):
            SchemaValidator.validate(DummySchema, {"name": "test"})

    def test_validate_dict(self):
        result = SchemaValidator.validate_dict({"name": "test", "value": 1}, DummySchema)
        assert result.name == "test"


class TestUrlValidator:
    @pytest.mark.asyncio
    async def test_valid_url(self):
        import httpx
        from unittest.mock import AsyncMock, patch
        mock_response = httpx.Response(200)
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
            result = await UrlValidator.check_url("https://example.com")
            assert result is True

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        import httpx
        from unittest.mock import AsyncMock, patch
        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, side_effect=httpx.RequestError("fail")):
            result = await UrlValidator.check_url("https://invalid.example.com")
            assert result is False

    def test_is_valid_url_format(self):
        assert UrlValidator.is_valid_format("https://example.com") is True
        assert UrlValidator.is_valid_format("not a url") is False
        assert UrlValidator.is_valid_format("") is False
