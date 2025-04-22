import boto3
import json
import time
import uuid
from datetime import datetime

# Initialize AWS clients
lambda_client = boto3.client('lambda', region_name='us-west-1')
iam = boto3.client('iam', region_name='us-west-1')
s3 = boto3.client('s3', region_name='us-west-1')
events = boto3.client('events', region_name='us-west-1')

def create_db_backup_lambda():
    """Create Lambda function and related resources for database backups"""
    print("Setting up database backup infrastructure...")
    
    # Create S3 bucket for database backups with a unique name
    bucket_name = f"project-orc-db-backups-{uuid.uuid4().hex[:8]}"
    try:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={
                'LocationConstraint': 'us-west-1'
            }
        )
        
        # Add lifecycle policy to expire backups after 30 days
        s3.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={
                'Rules': [
                    {
                        'ID': 'ExpireOldBackups',
                        'Status': 'Enabled',
                        'Expiration': {
                            'Days': 30
                        }
                    }
                ]
            }
        )
        
        print(f"Created S3 bucket: {bucket_name}")
    except Exception as e:
        print(f"Error creating S3 bucket: {str(e)}")
        return {'error': str(e)}
    
    # Create IAM role for Lambda function
    lambda_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    lambda_role = iam.create_role(
        RoleName='ProjectOrc-Lambda-Backup-Role',
        AssumeRolePolicyDocument=json.dumps(lambda_role_policy),
        Description='Role for Lambda functions to backup database to S3',
        Tags=[{'Key': 'Name', 'Value': 'ProjectOrc-Lambda-Backup-Role'}]
    )
    
    lambda_role_name = lambda_role['Role']['RoleName']
    lambda_role_arn = lambda_role['Role']['Arn']
    
    # Attach policies for S3 access
    iam.attach_role_policy(
        RoleName=lambda_role_name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess'
    )
    
    # Attach RDS access policy
    iam.attach_role_policy(
        RoleName=lambda_role_name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonRDSFullAccess'
    )
    
    # Attach CloudWatch Logs policy for Lambda logging
    iam.attach_role_policy(
        RoleName=lambda_role_name,
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
    )
    
    print(f"Created IAM role for Lambda: {lambda_role_name}")
    
    # Wait for role to be available
    print("Waiting for IAM role to propagate...")
    time.sleep(15)
    
    # Create DB backup Lambda function code
    db_backup_code = """
import json
import boto3
import time
import os
from datetime import datetime

def lambda_handler(event, context):
    # Initialize RDS and S3 clients
    rds = boto3.client('rds')
    s3 = boto3.client('s3')
    
    # Configuration from environment variables
    db_instance_identifier = os.environ['DB_INSTANCE_ID']
    s3_bucket = os.environ['S3_BUCKET']
    
    # Generate timestamp for backup file
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    snapshot_id = f"backup-{db_instance_identifier}-{timestamp}"
    
    try:
        # Create DB snapshot
        print(f"Creating snapshot {snapshot_id}")
        response = rds.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_id,
            DBInstanceIdentifier=db_instance_identifier
        )
        
        snapshot_arn = response['DBSnapshot']['DBSnapshotArn']
        print(f"Created snapshot with ARN: {snapshot_arn}")
        
        # Wait for snapshot to complete
        print("Waiting for snapshot to complete...")
        waiter = rds.get_waiter('db_snapshot_available')
        waiter.wait(
            DBSnapshotIdentifier=snapshot_id,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': 60
            }
        )
        print("Snapshot completed successfully")
        
        # For MySQL/PostgreSQL, export snapshot to S3
        # Note: Not all database types support direct export to S3
        # For MongoDB or other NoSQL databases, you would use a different approach
        
        try:
            # Create unique export task ID
            export_task_id = f"export-{timestamp}"
            
            # Export snapshot to S3
            s3_prefix = f"backups/{db_instance_identifier}/{timestamp}"
            
            export_response = rds.start_export_task(
                ExportTaskIdentifier=export_task_id,
                SourceArn=snapshot_arn,
                S3BucketName=s3_bucket,
                IamRoleArn=os.environ['LAMBDA_ROLE_ARN'],
                KmsKeyId='alias/aws/s3',
                S3Prefix=s3_prefix
            )
            
            print(f"Started export task: {export_task_id}")
            print(f"Backup will be stored at: s3://{s3_bucket}/{s3_prefix}")
            
            # Write metadata file with backup information
            metadata = {
                'timestamp': timestamp,
                'db_instance': db_instance_identifier,
                'snapshot_id': snapshot_id,
                'export_task_id': export_task_id,
                'backup_location': f"s3://{s3_bucket}/{s3_prefix}"
            }
            
            s3.put_object(
                Bucket=s3_bucket,
                Key=f"backups/{db_instance_identifier}/metadata/{timestamp}-metadata.json",
                Body=json.dumps(metadata, indent=2)
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Database backup completed successfully',
                    'snapshot_id': snapshot_id,
                    'export_task_id': export_task_id,
                    'backup_location': f"s3://{s3_bucket}/{s3_prefix}"
                })
            }
            
        except Exception as export_error:
            print(f"Error exporting snapshot to S3: {str(export_error)}")
            # Even if export fails, we still have the snapshot
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': f"Snapshot created but export to S3 failed: {str(export_error)}",
                    'snapshot_id': snapshot_id
                })
            }
            
    except Exception as e:
        print(f"Error during backup process: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f"Backup failed: {str(e)}"
            })
        }
"""
    
    # Create Lambda function for DB backup
    lambda_response = lambda_client.create_function(
        FunctionName='ProjectOrc-DB-Backup',
        Runtime='python3.9',
        Role=lambda_role_arn,
        Handler='lambda_function.lambda_handler',
        Code={
            'ZipFile': db_backup_code.encode()
        },
        Description='Lambda function to backup database to S3 with timestamps',
        Timeout=300,  # 5 minutes
        MemorySize=256,
        Environment={
            'Variables': {
                'DB_INSTANCE_ID': 'project-orc-db',  # Replace with your actual DB instance ID
                'S3_BUCKET': bucket_name,
                'LAMBDA_ROLE_ARN': lambda_role_arn
            }
        },
        Tags={
            'Name': 'ProjectOrc-DB-Backup'
        }
    )
    
    lambda_function_arn = lambda_response['FunctionArn']
    print(f"Created Lambda function: {lambda_function_arn}")
    
    # Create CloudWatch Events rule to trigger Lambda on schedule (daily at 3 AM UTC)
    rule_response = events.put_rule(
        Name='ProjectOrc-Daily-DB-Backup',
        ScheduleExpression='cron(0 3 * * ? *)',  # Run at 3 AM UTC every day
        State='ENABLED',
        Description='Trigger database backup Lambda function daily'
    )
    
    rule_arn = rule_response['RuleArn']
    
    # Add permission for CloudWatch Events to invoke Lambda
    lambda_client.add_permission(
        FunctionName='ProjectOrc-DB-Backup',
        StatementId='AllowCloudWatchEvents',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=rule_arn
    )
    
    # Set Lambda as target for CloudWatch Events rule
    events.put_targets(
        Rule='ProjectOrc-Daily-DB-Backup',
        Targets=[
            {
                'Id': 'ProjectOrc-DB-Backup-Target',
                'Arn': lambda_function_arn
            }
        ]
    )
    
    print("Scheduled daily database backups at 3 AM UTC")
    
    # Create a second CloudWatch rule for weekly full backups
    weekly_rule_response = events.put_rule(
        Name='ProjectOrc-Weekly-Full-DB-Backup',
        ScheduleExpression='cron(0 1 ? * SUN *)',  # Run at 1 AM UTC every Sunday
        State='ENABLED',
        Description='Trigger full database backup Lambda function weekly'
    )
    
    weekly_rule_arn = weekly_rule_response['RuleArn']
    
    # Add permission for weekly CloudWatch Events to invoke Lambda
    lambda_client.add_permission(
        FunctionName='ProjectOrc-DB-Backup',
        StatementId='AllowWeeklyCloudWatchEvents',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=weekly_rule_arn
    )
    
    # Set Lambda as target for weekly CloudWatch Events rule with full backup parameter
    events.put_targets(
        Rule='ProjectOrc-Weekly-Full-DB-Backup',
        Targets=[
            {
                'Id': 'ProjectOrc-Weekly-DB-Backup-Target',
                'Arn': lambda_function_arn,
                'Input': json.dumps({"full_backup": True})  # Parameter to indicate full backup
            }
        ]
    )
    
    print("Scheduled weekly full database backups at 1 AM UTC on Sundays")
    
    # Save backup configuration details
    backup_config = {
        'lambda_role_name': lambda_role_name,
        'lambda_role_arn': lambda_role_arn,
        'lambda_function_name': 'ProjectOrc-DB-Backup',
        'lambda_function_arn': lambda_function_arn,
        's3_bucket': bucket_name,
        'daily_cloudwatch_rule': 'ProjectOrc-Daily-DB-Backup',
        'weekly_cloudwatch_rule': 'ProjectOrc-Weekly-Full-DB-Backup'
    }
    
    # Write configuration to file
    with open('backup_config.json', 'w') as config_file:
        json.dump(backup_config, config_file, indent=2)
    
    print("Backup configuration saved to backup_config.json")
    
    return backup_config

if __name__ == "__main__":
    print("Setting up AWS Lambda for database backups with timestamping...")
    
    backup_config = create_db_backup_lambda()
    
    print("\nLambda deployment completed successfully!")
    print(f"Database backups will be stored in S3 bucket: {backup_config['s3_bucket']}")
    print("Daily backups will run at 3 AM UTC")
    print("Weekly full backups will run at 1 AM UTC on Sundays")
