from aws_cdk import (
    # Duration,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_iam as iam,
)
from constructs import Construct


class StratumInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket_name = self.node.try_get_context("bucket_name")
        is_prod = self.node.try_get_context("is_prod")

        # bucket removal policy should be RETAIN in production context and DESTROY only when a destroy_on_removal context flag is explicitly set. Do not default to DESTROY.
        removal_policy = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY

        #  create the S3 bucket and its associated policies and lifecycle rules
        bucket = s3.Bucket(
            self,
            bucket_name=bucket_name,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            blockPublicAccess=s3.BlockPublicAccess.BLOCK_ALL,
            enforceSSL=True,
            RemovalPolicy=removal_policy,
        )

        # deny s3:PutObject where the server-side encryption header is absent.
        deny_unencrypted_uploads = iam.PolicyStatement(
            sid="DenyUnencryptedObjectUploads",
            effect=iam.Effect.DENY,
            principals=[iam.AnyPrincipal()],
            actions=["s3:PutObject"],
            resources=[bucket.arn_for_objects("*")],
            conditions={
                "Null": {"s3:x-amz-server-side-encryption": "true"}  # header is absent
            },
        )
        bucket.add_to_resource_policy(deny_unencrypted_uploads)

        # Next task (idk what file) is to create Lifecycle rule on prefix stratum/meta/
        # Last task CfnOutput exporting the bucket name and ARN (used by the orchestrator's config and by CI).

        # then this task should be done and we can proceed to testing by hand and then having claude add tests
