import threading

import boto3

from stratum.config import UploadConfig


class S3ClientFactory:
    """S3 client factory for s3 uploads.

    A single factory instance is shared across threads. Each thread gets its own
    S3 client, created on first call to get_client() and cached thread-locally.
    reset() clears the cache for the calling thread only.
    """

    # It's the opposite of a lock. A lock says "only one thread touches this shared thing at a
    #  time. threading.local() says "there is no shared thing — everyone gets their own.
    _thread_local = threading.local()

    def __init__(self, config: UploadConfig):
        self.config = config

    def get_client(self):
        """Return cached client."""
        # If profile is None, the default credential chain is used.

        # check if our thread already has a client associated with it
        if not hasattr(S3ClientFactory._thread_local, "client"):
            S3ClientFactory._thread_local.client = boto3.Session(
                region_name=self.config.region, profile_name=self.config.profile
            ).client("s3")

        return S3ClientFactory._thread_local.client

    def reset(self):
        """Clear cached client for the calling thread only."""
        if hasattr(S3ClientFactory._thread_local, "client"):
            del S3ClientFactory._thread_local.client
