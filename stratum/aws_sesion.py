# TODO
# pretty sure this should be a context manager
import boto3

from stratum.config import UploadConfig


class S3ClientFactory:
    """S3 client factory for s3 uploads.

    Note we are not creating this as a context manager because boto manages open connections under
    the hood, so we don't need to worry about leaking connections.
    """

    def __init__(self, config: UploadConfig):
        self.config = config
        self.client = None

    def get_client(self):
        """Return cached client."""
        # If profile is None, the default credential chain is used.
        if not self.client:
            self.client = boto3.Session(
                region_name=self.config.region, profile_name=self.config.profile
            ).client("s3")

        return self.client

    def reset(self):
        """Clear cached client."""
        self.client = None
