import boto3
import time
import json
import base64
import uuid
from datetime import datetime

# Initialize AWS clients
ec2 = boto3.client('ec2', region_name='us-west-1')
autoscaling = boto3.client('autoscaling', region_name='us-west-1')
elbv2 = boto3.client('elbv2', region_name='us-west-1')
iam = boto3.client('iam', region_name='us-west-1')
ecr = boto3.client('ecr', region_name='us-west-1')
route53 = boto3.client('route53', region_name='us-west-1')
lambda_client = boto3.client('lambda', region_name='us-west-1')
s3 = boto3.client('s3', region_name='us-west-1')
events = boto3.client('events', region_name='us-west-1')

# Load infrastructure details from previous script if available
try:
    with open('infrastructure_details.json', 'r') as f:
        infrastructure = json.load(f)
    print("Loaded existing infrastructure details")
    vpc_id = infrastructure['vpc']['vpc_id']
except FileNotFoundError:
    print("No existing infrastructure details found, please run the VPC setup script first")
    exit(1)

def deploy_backend_services():
    """Configure and deploy backend services with Auto Scaling Group"""
    print("Deploying backend services...")
    
    # Auto Scaling Group and related components should already be set up from the previous script
    
    # Update existing ASG with lifecycle hooks for graceful termination
    autoscaling.put_lifecycle_hook(
        AutoScalingGroupName=infrastructure['auto_scaling_group']['asg_name'],
        LifecycleHookName='terminate-backend-hook',
        LifecycleTransition='autoscaling:EC2_INSTANCE_TERMINATING',
        HeartbeatTimeout=300  # 5 minutes to complete shutdown
    )
    
    # Configure scaling policies based on schedule
    autoscaling.put_scheduled_update_group_action(
        AutoScalingGroupName=infrastructure['auto_scaling_group']['asg_name'],
        ScheduledActionName='scale-up-morning',
        DesiredCapacity=4,
        StartTime=datetime(2025, 6, 1, 8, 0, 0),  # 8 AM, adjust as needed
        Recurrence='0 8 * * MON-FRI'  # cron expression for weekdays at 8 AM
    )
    
    autoscaling.put_scheduled_update_group_action(
        AutoScalingGroupName=infrastructure['auto_scaling_group']['asg_name'],
        ScheduledActionName='scale-down-evening',
        DesiredCapacity=2,
        StartTime=datetime(2025, 6, 1, 20, 0, 0),  # 8 PM, adjust as needed
        Recurrence='0 20 * * MON-FRI'  # cron expression for weekdays at 8 PM
    )
    
    print("Backend services deployment configured")
    return {
        'status': 'Backend ASG configured with lifecycle hooks and scheduled scaling'
    }

def set_up_load_balancer():
    """Set up additional load balancer configurations"""
    # The load balancer should already be created from the previous script
    alb_arn = infrastructure['load_balancer']['alb_arn']
    
    # Enable cross-zone load balancing for better distribution
    elbv2.modify_load_balancer_attributes(
        LoadBalancerArn=alb_arn,
        Attributes=[
            {
                'Key': 'load_balancing.cross_zone.enabled',
                'Value': 'true'
            }
        ]
    )
    
    # Add HTTPS listener with a self-signed certificate for development
    # In production, you would use a proper certificate from AWS Certificate Manager
    
    print("Load balancer configured with additional settings")
    return {
        'alb_arn': alb_arn,
        'alb_dns': infrastructure['load_balancer']['alb_dns']
    }

def configure_dns(domain_name, alb_dns):
    """Set up DNS using Route 53"""
    print(f"Configuring DNS for {domain_name} pointing to {alb_dns}...")
    
    # Check if hosted zone exists, otherwise create it
    try:
        response = route53.list_hosted_zones_by_name(
            DNSName=domain_name
        )
        
        hosted_zone = None
        for zone in response['HostedZones']:
            if zone['Name'] == f"{domain_name}." or zone['Name'] == domain_name:
                hosted_zone = zone
                break
        
        if not hosted_zone:
            # Create hosted zone
            hosted_zone = route53.create_hosted_zone(
                Name=domain_name,
                CallerReference=str(uuid.uuid4()),
                HostedZoneConfig={
                    'Comment': f'Hosted zone for {domain_name}',
                    'PrivateZone': False
                }
            )['HostedZone']
            print(f"Created new hosted zone for {domain_name}")
        
        hosted_zone_id = hosted_zone['Id'].split('/')[-1]
        
        # Create DNS record
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': domain_name,
                            'Type': 'A',
                            'AliasTarget': {
                                'HostedZoneId': 'Z368ELLRRE2KJ0',  # us-west-1 ELB hosted zone ID
                                'DNSName': alb_dns,
                                'EvaluateTargetHealth': True
                            }
                        }
                    },
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': f"www.{domain_name}",
                            'Type': 'A',
                            'AliasTarget': {
                                'HostedZoneId': 'Z368ELLRRE2KJ0',  # us-west-1 ELB hosted zone ID
                                'DNSName': alb_dns,
                                'EvaluateTargetHealth': True
                            }
                        }
                    }
                ]
            }
        )
        
        print(f"DNS records created/updated for {domain_name} and www.{domain_name}")
        
        return {
            'domain_name': domain_name,
            'hosted_zone_id': hosted_zone_id,
            'nameservers': hosted_zone.get('DelegationSet', {}).get('NameServers', [])
        }
    
    except Exception as e:
        print(f"Error configuring DNS: {str(e)}")
        return {
            'error': str(e)
        }

def deploy_frontend():
    """Deploy frontend on EC2 instances"""
    print("Deploying frontend service...")
    
    # Create security group for frontend
    frontend_sg = ec2.create_security_group(
        GroupName='ProjectOrc-Frontend-SG',
        Description='Security group for frontend service',
        VpcId=vpc_id,
        TagSpecifications=[
            {
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': 'ProjectOrc-Frontend-SG'}]
            }
        ]
    )
    frontend_sg_id = frontend_sg['GroupId']
    
    # Allow HTTP and HTTPS inbound
    ec2.authorize_security_group_ingress(
        GroupId=frontend_sg_id,
        IpPermissions=[
            {
                'IpProtocol': 'tcp',
                'FromPort': 80,
                'ToPort': 80,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            },
            {
                'IpProtocol': 'tcp',
                'FromPort': 443,
                'ToPort': 443,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }
        ]
    )
    
    # Create user data script for frontend instances
    user_data = """#!/bin/bash
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker
amazon-linux-extras install -y aws-cli
aws ecr get-login-password --region us-west-1 | docker login --username AWS --password-stdin 975050024946.dkr.ecr.us-west-1.amazonaws.com
docker pull 975050024946.dkr.ecr.us-west-1.amazonaws.com/aakash/project-orc-b:frontendforkubernetes
docker run -d -p 80:80 -e BACKEND_URL=http://BACKEND_ALB_DNS 975050024946.dkr.ecr.us-west-1.amazonaws.com/aakash/project-orc-b:frontendforkubernetes
"""
    
    # Replace placeholder with actual backend ALB DNS
    user_data = user_data.replace('BACKEND_ALB_DNS', infrastructure['load_balancer']['alb_dns'])
    encoded_user_data = base64.b64encode(user_data.encode()).decode()
    
    # Create launch template for frontend
    frontend_lt = ec2.create_launch_template(
        LaunchTemplateName='ProjectOrc-FrontendLT',
        VersionDescription='Initial version',
        TagSpecifications=[
            {
                'ResourceType': 'launch-template',
                'Tags': [{'Key': 'Name', 'Value': 'ProjectOrc-FrontendLT'}]
            }
        ],
        LaunchTemplateData={
            'ImageId': 'ami-0c110e13b02dea71a',  # Amazon Linux 2 in us-west-1, update as needed
            'InstanceType': 't2.micro',
            'SecurityGroupIds': [frontend_sg_id],
            'IamInstanceProfile': {
                'Name': infrastructure['iam']['instance_profile_name']
            },
            'UserData': encoded_user_data,
            'TagSpecifications': [
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': 'ProjectOrc-Frontend'}]
                }
            ]
        }
    )
    
    frontend_lt_id = frontend_lt['LaunchTemplate']['LaunchTemplateId']
    
    # Create auto scaling group for frontend
    frontend_asg = autoscaling.create_auto_scaling_group(
        AutoScalingGroupName='ProjectOrc-Frontend-ASG',
        LaunchTemplate={
            'LaunchTemplateId': frontend_lt_id,
            'Version': '$Latest'
        },
        MinSize=2,
        MaxSize=4,
        DesiredCapacity=2,
        VPCZoneIdentifier=','.join(infrastructure['vpc']['subnets']['public']),
        Tags=[
            {
                'Key': 'Name',
                'Value': 'ProjectOrc-Frontend-ASG',
                'PropagateAtLaunch': True
            }
        ]
    )
    
    # Create scaling policy for frontend
    autoscaling.put_scaling_policy(
        AutoScalingGroupName='ProjectOrc-Frontend-ASG',
        PolicyName='ProjectOrc-Frontend-ScaleUp',
        PolicyType='TargetTrackingScaling',
        TargetTrackingConfiguration={
            'PredefinedMetricSpecification': {
                'PredefinedMetricType': 'ASGAverageCPUUtilization'
            },
            'TargetValue': 70.0
        }
    )
    
    print("Frontend service deployed with auto scaling")
    return {
        'frontend_sg_id': frontend_sg_id,
        'frontend_lt_id': frontend_lt_id,
        'frontend_asg_name': 'ProjectOrc-Frontend-ASG'
    }

def create_lambda_functions():
    """Create AWS Lambda functions for specific tasks"""
    print("Creating Lambda functions...")
    
    # Create S3 bucket for database backups
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
        RoleName='ProjectOrc-Lambda-Role',
        AssumeRolePolicyDocument=json.dumps(lambda_role_policy),
        Description='Role for Lambda functions to access RDS and S3',
        Tags=[{'Key': 'Name', 'Value': 'ProjectOrc-Lambda-Role'}]
    )
    
    lambda_role_name = lambda_role['Role']['RoleName']
    lambda_role_arn = lambda_role['Role']['Arn']
    
    # Attach policies for S3 and RDS access
    iam.attach_role_policy(
        RoleName=lambda_role_name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess'
    )
    
    iam.attach_role_policy(
        RoleName=lambda_role_name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonRDSFullAccess'
    )
    
    # Attach CloudWatch Logs policy
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
    # RDS client
    rds = boto3.client('rds')
    s3 = boto3.client('s3')
    
    # Configuration
    db_instance_identifier = os.environ['DB_INSTANCE_ID']  # Get from environment variable
    s3_bucket = os.environ['S3_BUCKET']  # Get from environment variable
    
    # Generate timestamp for backup file
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    snapshot_id = f"backup-{db_instance_identifier}-{timestamp}"
    
    try:
        # Create DB snapshot
        print(f"Creating snapshot {snapshot_id}")
        rds.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_id,
            DBInstanceIdentifier=db_instance_identifier
        )
        
        # Wait for snapshot to complete - for demo purposes only
        # In production, you'd use Step Functions or another mechanism
        waiter = rds.get_waiter('db_snapshot_available')
        print("Waiting for snapshot to complete...")
        waiter.wait(
            DBSnapshotIdentifier=snapshot_id
        )
        
        # Export to S3
        # Note: This is a simplified example. In real-world scenarios,
        # you might need to handle export tasks differently.
        export_task_id = f"export-{timestamp}"
        
        # Get snapshot ARN
        snapshots = rds.describe_db_snapshots(
            DBSnapshotIdentifier=snapshot_id
        )
        snapshot_arn = snapshots['DBSnapshots'][0]['DBSnapshotArn']
        
        # Export to S3
        s3_prefix = f"backups/{db_instance_identifier}/{timestamp}"
        export_response = rds.start_export_task(
            ExportTaskIdentifier=export_task_id,
            SourceArn=snapshot_arn,
            S3BucketName=s3_bucket,
            IamRoleArn=context.invoked_function_arn,
            KmsKeyId='alias/aws/s3',
            S3Prefix=s3_prefix
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Backup initiated with task ID: {export_task_id}",
                'snapshotId': snapshot_id,
                's3Location': f"s3://{s3_bucket}/{s3_prefix}"
            })
        }
    except Exception as e:
        print(f"Error creating backup: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f"Error creating backup: {str(e)}"
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
        Description='Lambda function to backup RDS database to S3',
        Timeout=300,  # 5 minutes
        MemorySize=256,
        Environment={
            'Variables': {
                'DB_INSTANCE_ID': 'project-orc-db',  # Replace with your actual DB instance ID
                'S3_BUCKET': bucket_name
            }
        },
        Tags={
            'Name': 'ProjectOrc-DB-Backup'
        }
    )
    
    lambda_function_arn = lambda_response['FunctionArn']
    print(f"Created Lambda function: {lambda_function_arn}")
    
    # Create CloudWatch Events rule to trigger Lambda on schedule
    rule_response = events.put_rule(
        Name='ProjectOrc-Nightly-Backup',
        ScheduleExpression='cron(0 3 * * ? *)',  # Run at 3 AM UTC every day
        State='ENABLED',
        Description='Trigger DB backup Lambda function nightly'
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
        Rule='ProjectOrc-Nightly-Backup',
        Targets=[
            {
                'Id': 'ProjectOrc-DB-Backup-Target',
                'Arn': lambda_function_arn
            }
        ]
    )
    
    print("Scheduled nightly DB backups via CloudWatch Events")
    
    return {
        'lambda_role_name': lambda_role_name,
        'lambda_role_arn': lambda_role_arn,
        'lambda_function_name': 'ProjectOrc-DB-Backup',
        'lambda_function_arn': lambda_function_arn,
        's3_bucket': bucket_name,
        'cloudwatch_rule': 'ProjectOrc-Nightly-Backup'
    }

def update_infrastructure_details(new_details):
    """Update the infrastructure details file with new information"""
    infrastructure.update(new_details)
    
    with open('infrastructure_details.json', 'w') as f:
        json.dump(infrastructure, f, indent=2)
    
    print("Updated infrastructure details saved to infrastructure_details.json")

if __name__ == "__main__":
    print("Starting deployment of additional services...")
    
    # Deploy backend services
    backend_info = deploy_backend_services()
    
    # Set up load balancer
    lb_info = set_up_load_balancer()
    
    # Configure DNS - replace with your actual domain
    domain_name = "project-orc.example.com"  # Replace with your actual domain
    dns_info = configure_dns(domain_name, lb_info['alb_dns'])
    
    # Deploy frontend
    frontend_info = deploy_frontend()
    
    # Create Lambda functions
    lambda_info = create_lambda_functions()
    
    # Update infrastructure details with new information
    update_infrastructure_details({
        'backend_deployment': backend_info,
        'load_balancer_config': lb_info,
        'dns': dns_info,
        'frontend': frontend_info,
        'lambda': lambda_info
    })
    
    print("\nDeployment completed successfully!")
    print(f"Your application should be accessible at: http://{domain_name}")
    print("Note: DNS propagation may take up to 48 hours to complete.")
    print(f"In the meantime, you can access the application via the ALB DNS: {lb_info['alb_dns']}")
