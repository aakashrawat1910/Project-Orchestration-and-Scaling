pipeline {
    agent any

    environment {
        GIT_URL = 'https://github.com/aakashrawat1910/Project-Orchestration-and-Scaling.git'
        GIT_BRANCH = 'main'
        AWS_ACCESS_KEY_ID = 'AKIA6GBMCU7ZMXDQYE2R' // AWS Access Key ID stored in Jenkins
        AWS_SECRET_ACCESS_KEY = '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' // AWS Secret Access Key stored in Jenkins
        AWS_REGION = 'us-west-1' // AWS region where the cluster is located
        
    }

    stages {
        stage('Checkout Code') {
            steps {
                echo 'Checking out code from GitHub...'
                git url: "${env.GIT_URL}", branch: "${env.GIT_BRANCH}"
            }
        }

        stage('Build Docker Images') {
            steps {
                script {
                    echo 'Building Docker images...'
                    sh '''
                        cd backend
                        docker-compose build
                    '''
                }
            }
}
        stage('Authenticate to AWS ECR') {
            steps {
                script {
                    echo 'Authenticating with AWS ECR...'
                    sh '''
                        aws ecr get-login-password --region us-west-1 | docker login --username AWS --password-stdin 975050024946.dkr.ecr.us-west-1.amazonaws.com
                    '''
                }
            }
        }
        stage('Tag Docker Images') {
            steps {
                script {
                    echo 'Tagging Docker images for AWS ECR...'
                    sh '''
                        docker tag backend-helloservice:latest 975050024946.dkr.ecr.us-west-1.amazonaws.com/aakash/project-orc-b:hello-latest
                        docker tag backend-profileservice:latest 975050024946.dkr.ecr.us-west-1.amazonaws.com/aakash/project-orc-b:profile-latest
                    '''
                }
            }
        }
        stage('Push Docker Images to ECR') {
            steps {
                script {
                    echo 'Pushing Docker images to AWS ECR...'
                    sh '''
                        docker push 975050024946.dkr.ecr.us-west-1.amazonaws.com/aakash/project-orc-b:hello-latest
                        docker push 975050024946.dkr.ecr.us-west-1.amazonaws.com/aakash/project-orc-b:profile-latest
                    '''
                }
            }
        }

        
    }
}