import boto3
import time
import os

def lambda_handler(event, context):
    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
    job_name = f"ml-process-job-{timestamp}"

    sagemaker = boto3.client("sagemaker")
    sns = boto3.client("sns")  # used for notifications (optional)

    sns_topic_arn = os.getenv("SNS_TOPIC_ARN", None)

    # Step 1: Start Processing Job
    response = sagemaker.create_processing_job(
        ProcessingJobName=job_name,
        RoleArn="arn:aws:iam::514475511198:role/LabRole",
        AppSpecification={
            "ImageUri": "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1",
            "ContainerEntrypoint": ["python3", "/opt/ml/processing/input/code/ml_code.py"]
        },
        ProcessingResources={
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": "ml.m5.large",
                "VolumeSizeInGB": 20
            }
        },
        ProcessingInputs=[
            {
                "InputName": "code",
                "S3Input": {
                    "S3Uri": "s3://my-code-sc171/ml_code.py",
                    "LocalPath": "/opt/ml/processing/input/code/",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File"
                }
            },
            {
                "InputName": "input-data",
                "S3Input": {
                    "S3Uri": "s3://myresult-sc171/ml_data.csv",
                    "LocalPath": "/opt/ml/processing/input/",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File"
                }
            }
        ],
        ProcessingOutputConfig={
            "Outputs": [
                {
                    "OutputName": "model-output",
                    "S3Output": {
                        "S3Uri": "s3://ml-model-sc171/",
                        "LocalPath": "/opt/ml/processing/output/",
                        "S3UploadMode": "EndOfJob"
                    }
                }
            ]
        }
    )

    print(f"Job {job_name} started. Monitoring progress...")

    # Step 2: Monitor until job completes
    while True:
        desc = sagemaker.describe_processing_job(ProcessingJobName=job_name)
        status = desc["ProcessingJobStatus"]
        if status in ["Completed", "Failed", "Stopped"]:
            break
        time.sleep(30)

    print(f"Job {job_name} ended with status: {status}")

    # Step 3: Error handling and notifications
    if status != "Completed":
        failure_reason = desc.get("FailureReason", "Unknown")
        print(f"Error: Job failed or stopped. Reason: {failure_reason}")

        # Optional: send SNS alert
        if sns_topic_arn:
            sns.publish(
                TopicArn=sns_topic_arn,
                Subject=f"SageMaker Job {status}: {job_name}",
                Message=f"The job {job_name} ended with status {status}. Reason: {failure_reason}"
            )

        # Return error response
        return {
            "statusCode": 500,
            "body": f"Job {job_name} failed/stopped. Reason: {failure_reason}"
        }

    # Step 4: Success return
    return {
        "statusCode": 200,
        "body": f"SageMaker Processing Job {job_name} completed successfully."
    }
