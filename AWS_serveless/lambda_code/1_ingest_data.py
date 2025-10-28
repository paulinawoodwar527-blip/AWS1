import boto3
import time
import os
import json

# Initialize AWS service clients
sagemaker = boto3.client("sagemaker")
s3 = boto3.client("s3")
glue = boto3.client("glue")
sns = boto3.client("sns")

def lambda_handler(event, context):
    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
    job_name = f"ml-process-job-{timestamp}"
    data_crawler = "data_crawler"

    sns_topic_arn = os.getenv("SNS_TOPIC_ARN")  # Optional for notifications

    # Define SageMaker processing configuration
    try:
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

        print(f"🚀 SageMaker job {job_name} started successfully.")

    except Exception as e:
        print(f"❌ SageMaker job failed to start: {str(e)}")
        if sns_topic_arn:
            sns.publish(
                TopicArn=sns_topic_arn,
                Subject="SageMaker Job Launch Failed",
                Message=f"Failed to start processing job: {str(e)}"
            )
        return {"statusCode": 500, "message": str(e)}

    # Wait until job finishes
    print("⌛ Waiting for SageMaker job to complete...")
    while True:
        desc = sagemaker.describe_processing_job(ProcessingJobName=job_name)
        status = desc["ProcessingJobStatus"]
        if status in ["Completed", "Failed", "Stopped"]:
            break
        time.sleep(30)

    print(f"✅ SageMaker job {job_name} finished with status: {status}")

    # Error handling for SageMaker job
    if status != "Completed":
        reason = desc.get("FailureReason", "Unknown")
        if sns_topic_arn:
            sns.publish(
                TopicArn=sns_topic_arn,
                Subject=f"SageMaker Job Failed: {job_name}",
                Message=f"Job {job_name} failed. Reason: {reason}"
            )
        return {
            "statusCode": 500,
            "message": f"Job failed or stopped. Reason: {reason}"
        }

    # Start Glue Crawler after successful job
    try:
        glue.start_crawler(Name=data_crawler)
        print(f"🚀 Glue Crawler '{data_crawler}' started successfully.")
    except glue.exceptions.CrawlerRunningException:
        print(f"⚠️ Crawler '{data_crawler}' is already running.")
        status_message = f"Crawler '{data_crawler}' already running."
    except Exception as e:
        print(f"❌ Failed to start Glue Crawler: {str(e)}")
        if sns_topic_arn:
            sns.publish(
                TopicArn=sns_topic_arn,
                Subject="Glue Crawler Failed",
                Message=f"Failed to start Glue Crawler: {str(e)}"
            )
        return {"statusCode": 500, "message": str(e)}
    else:
        status_message = f"Glue Crawler '{data_crawler}' launched."

    # Optional: publish notification when all succeeds
    if sns_topic_arn:
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject="Pipeline Completed Successfully",
            Message=f"SageMaker job '{job_name}' completed successfully. {status_message}"
        )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"✅ Job '{job_name}' completed successfully and {status_message}"
        })
    }
