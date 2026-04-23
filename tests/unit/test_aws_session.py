"""Unit tests for STRAT-203: AWS Session Factory."""

from unittest.mock import MagicMock, call, patch

import pytest

from stratum.aws_sesion import S3ClientFactory
from stratum.models import UploadConfig, UploadMode


def make_config(**kwargs) -> UploadConfig:
    defaults = dict(
        bucket="test-bucket",
        prefix="stratum/",
        region="us-east-1",
        profile="my-profile",
    )
    defaults.update(kwargs)
    return UploadConfig(**defaults)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestS3ClientFactoryConstruction:
    def test_construction_does_not_raise_without_credentials(self):
        config = make_config()
        with patch("stratum.aws_sesion.boto3.Session") as mock_session:
            # Ensure no network activity on construction
            factory = S3ClientFactory(config)
        mock_session.assert_not_called()

    def test_construction_stores_config(self):
        config = make_config()
        factory = S3ClientFactory(config)
        assert factory.config is config

    def test_client_is_none_before_first_get(self):
        config = make_config()
        factory = S3ClientFactory(config)
        assert factory.client is None


# ---------------------------------------------------------------------------
# get_client — lazy init and caching
# ---------------------------------------------------------------------------


class TestGetClient:
    def _make_factory(self, **kwargs) -> S3ClientFactory:
        return S3ClientFactory(make_config(**kwargs))

    def test_get_client_returns_a_client(self):
        factory = self._make_factory()
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session):
            result = factory.get_client()
        assert result is mock_client

    def test_get_client_called_twice_returns_same_instance(self):
        factory = self._make_factory()
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session):
            first = factory.get_client()
            second = factory.get_client()
        assert first is second

    def test_boto3_session_constructed_only_once_on_repeated_calls(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session) as mock_sess_cls:
            factory.get_client()
            factory.get_client()
            factory.get_client()
        mock_sess_cls.assert_called_once()

    def test_correct_region_passed_to_session(self):
        factory = self._make_factory(region="eu-west-2")
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session) as mock_sess_cls:
            factory.get_client()
        _, kwargs = mock_sess_cls.call_args
        assert kwargs["region_name"] == "eu-west-2"

    def test_correct_profile_passed_to_session(self):
        factory = self._make_factory(profile="prod-profile")
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session) as mock_sess_cls:
            factory.get_client()
        _, kwargs = mock_sess_cls.call_args
        assert kwargs["profile_name"] == "prod-profile"

    def test_none_profile_passed_through_to_session(self):
        factory = self._make_factory(profile=None)
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session) as mock_sess_cls:
            factory.get_client()
        _, kwargs = mock_sess_cls.call_args
        assert kwargs.get("profile_name") is None

    def test_session_client_called_with_s3(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session):
            factory.get_client()
        mock_session.client.assert_called_once_with("s3")


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


class TestReset:
    def _make_factory(self) -> S3ClientFactory:
        return S3ClientFactory(make_config())

    def test_reset_clears_cached_client(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session):
            factory.get_client()
        factory.reset()
        assert factory.client is None

    def test_get_client_after_reset_constructs_new_instance(self):
        factory = self._make_factory()
        first_client = MagicMock()
        second_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.side_effect = [first_client, second_client]
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session):
            c1 = factory.get_client()
            factory.reset()
            c2 = factory.get_client()
        assert c1 is first_client
        assert c2 is second_client
        assert c1 is not c2

    def test_boto3_session_constructed_twice_after_reset(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch("stratum.aws_sesion.boto3.Session", return_value=mock_session) as mock_sess_cls:
            factory.get_client()
            factory.reset()
            factory.get_client()
        assert mock_sess_cls.call_count == 2

    def test_reset_before_any_get_client_is_safe(self):
        factory = self._make_factory()
        factory.reset()  # should not raise
        assert factory.client is None
