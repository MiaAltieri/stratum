from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class StratumInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket_name = self.node.try_get_context("bucket_name")
        is_prod = self.node.try_get_context("is_prod")

        # bucket removal policy should be RETAIN in production context and DESTROY only when a destroy_on_removal context flag is explicitly set. Do not default to DESTROY.
        removal_policy = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY

        lifecycle_rules = [
            s3.LifecycleRule(
                prefix="stratum/meta/",
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                        transition_after=Duration.days(30),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                        transition_after=Duration.days(90),
                    ),
                ],
            )
        ]

        #  create the S3 bucket and its associated policies and lifecycle rules
        bucket = s3.Bucket(
            self,
            "StratumBucket",
            bucket_name=bucket_name,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=removal_policy,
            auto_delete_objects=not is_prod,
            lifecycle_rules=lifecycle_rules,
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

        # export essential info for orchestrator / CI
        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            export_name="MyStack-BucketName",
        )

        CfnOutput(
            self, "BucketArn", value=bucket.bucket_arn, export_name="MyStack-BucketArn"
        )
