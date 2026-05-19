"""Unit tests for STRAT-203: AWS Session Factory."""

import threading
from unittest.mock import MagicMock, patch

from stratum.aws_session import S3ClientFactory
from stratum.models import UploadConfig


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
        with patch("stratum.aws_session.boto3.Session") as mock_session:
            # Ensure no network activity on construction
            S3ClientFactory(config)
        mock_session.assert_not_called()

    def test_construction_stores_config(self):
        config = make_config()
        factory = S3ClientFactory(config)
        assert factory.config is config

    def test_no_client_cached_before_first_get(self):
        config = make_config()
        S3ClientFactory(config)
        # _thread_local is class-level; construction must not pre-populate it
        S3ClientFactory._thread_local.__dict__.pop("client", None)
        assert not hasattr(S3ClientFactory._thread_local, "client")


# ---------------------------------------------------------------------------
# get_client — lazy init and caching
# ---------------------------------------------------------------------------


class TestGetClient:
    def setup_method(self):
        S3ClientFactory._thread_local.__dict__.pop("client", None)

    def _make_factory(self, **kwargs) -> S3ClientFactory:
        return S3ClientFactory(make_config(**kwargs))

    def test_get_client_returns_a_client(self):
        factory = self._make_factory()
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        with patch("stratum.aws_session.boto3.Session", return_value=mock_session):
            result = factory.get_client()
        assert result is mock_client

    def test_get_client_called_twice_returns_same_instance(self):
        factory = self._make_factory()
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        with patch("stratum.aws_session.boto3.Session", return_value=mock_session):
            first = factory.get_client()
            second = factory.get_client()
        assert first is second

    def test_boto3_session_constructed_only_once_on_repeated_calls(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch(
            "stratum.aws_session.boto3.Session", return_value=mock_session
        ) as mock_sess_cls:
            factory.get_client()
            factory.get_client()
            factory.get_client()
        mock_sess_cls.assert_called_once()

    def test_correct_region_passed_to_session(self):
        factory = self._make_factory(region="eu-west-2")
        mock_session = MagicMock()
        with patch(
            "stratum.aws_session.boto3.Session", return_value=mock_session
        ) as mock_sess_cls:
            factory.get_client()
        _, kwargs = mock_sess_cls.call_args
        assert kwargs["region_name"] == "eu-west-2"

    def test_correct_profile_passed_to_session(self):
        factory = self._make_factory(profile="prod-profile")
        mock_session = MagicMock()
        with patch(
            "stratum.aws_session.boto3.Session", return_value=mock_session
        ) as mock_sess_cls:
            factory.get_client()
        _, kwargs = mock_sess_cls.call_args
        assert kwargs["profile_name"] == "prod-profile"

    def test_none_profile_passed_through_to_session(self):
        factory = self._make_factory(profile=None)
        mock_session = MagicMock()
        with patch(
            "stratum.aws_session.boto3.Session", return_value=mock_session
        ) as mock_sess_cls:
            factory.get_client()
        _, kwargs = mock_sess_cls.call_args
        assert kwargs.get("profile_name") is None

    def test_session_client_called_with_s3(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch("stratum.aws_session.boto3.Session", return_value=mock_session):
            factory.get_client()
        mock_session.client.assert_called_once_with("s3")


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


class TestReset:
    def setup_method(self):
        S3ClientFactory._thread_local.__dict__.pop("client", None)

    def _make_factory(self) -> S3ClientFactory:
        return S3ClientFactory(make_config())

    def test_reset_clears_cached_client(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch("stratum.aws_session.boto3.Session", return_value=mock_session):
            factory.get_client()
        factory.reset()
        assert not hasattr(S3ClientFactory._thread_local, "client")

    def test_get_client_after_reset_constructs_new_instance(self):
        factory = self._make_factory()
        first_client = MagicMock()
        second_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.side_effect = [first_client, second_client]
        with patch("stratum.aws_session.boto3.Session", return_value=mock_session):
            c1 = factory.get_client()
            factory.reset()
            c2 = factory.get_client()
        assert c1 is first_client
        assert c2 is second_client
        assert c1 is not c2

    def test_boto3_session_constructed_twice_after_reset(self):
        factory = self._make_factory()
        mock_session = MagicMock()
        with patch(
            "stratum.aws_session.boto3.Session", return_value=mock_session
        ) as mock_sess_cls:
            factory.get_client()
            factory.reset()
            factory.get_client()
        assert mock_sess_cls.call_count == 2

    def test_reset_before_any_get_client_is_safe(self):
        factory = self._make_factory()
        factory.reset()  # should not raise
        assert not hasattr(S3ClientFactory._thread_local, "client")


# ---------------------------------------------------------------------------
# Thread safety — per-thread client isolation (STRAT-303)
# ---------------------------------------------------------------------------


class TestThreadLocalClients:
    def test_get_client_returns_distinct_client_per_thread(self):
        """get_client() from N concurrent threads must return N distinct objects."""
        N = 4
        factory = S3ClientFactory(make_config())
        collected: list = []
        collect_lock = threading.Lock()
        barrier = threading.Barrier(N)
        call_index = [0]
        call_lock = threading.Lock()
        mock_clients = [MagicMock(name=f"s3_client_{i}") for i in range(N)]

        def make_session(*args, **kwargs):
            sess = MagicMock()
            with call_lock:
                idx = call_index[0]
                call_index[0] += 1
            sess.client.return_value = mock_clients[idx]
            return sess

        def worker():
            barrier.wait()
            c = factory.get_client()
            with collect_lock:
                collected.append(c)

        with patch("stratum.aws_session.boto3.Session", side_effect=make_session):
            threads = [threading.Thread(target=worker) for _ in range(N)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(collected) == N
        assert len({id(c) for c in collected}) == N, "Each thread must get a distinct client"

    def test_reset_in_one_thread_does_not_affect_cached_client_in_another(self):
        """reset() clears only the calling thread's cache; other threads are unaffected."""
        factory = S3ClientFactory(make_config())
        mock_session = MagicMock()
        barrier_both_cached = threading.Barrier(2)
        barrier_a_reset = threading.Barrier(2)
        client_before: list = [None]
        client_after: list = [None]

        def thread_a():
            factory.get_client()
            barrier_both_cached.wait()  # wait for B to cache its client
            factory.reset()
            barrier_a_reset.wait()  # signal B that A has reset

        def thread_b():
            client_before[0] = factory.get_client()
            barrier_both_cached.wait()  # signal A that B has cached
            barrier_a_reset.wait()  # wait for A to reset
            client_after[0] = factory.get_client()

        with patch("stratum.aws_session.boto3.Session", return_value=mock_session):
            ta = threading.Thread(target=thread_a)
            tb = threading.Thread(target=thread_b)
            ta.start()
            tb.start()
            ta.join()
            tb.join()

        assert client_before[0] is client_after[0], (
            "Thread B's client must survive thread A's reset"
        )
