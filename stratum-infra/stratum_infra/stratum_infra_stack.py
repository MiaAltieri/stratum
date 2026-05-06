from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
)
from constructs import Construct


class StratumInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        # This is where we will:
        #  create the S3 bucket and its associated policies and lifecycle rules

        # example resource
        # queue = sqs.Queue(
        #     self, "StratumInfraQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
