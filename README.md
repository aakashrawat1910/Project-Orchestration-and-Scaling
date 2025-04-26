# 🧱 MERN Microservices Orchestration & Scaling Project

This project demonstrates how to build, containerize, orchestrate, and scale a MERN stack microservices application using **Docker**, **AWS (EC2/ECR/EKS)**, **Python (Boto3)**, **Jenkins**, and **ChatOps**.

---

## 📁 Project Structure

```
Project-Orchestration-and-Scaling/
├── backend/
│   ├── helloservice/
│   ├── profileservice/
│   └── docker-compose.yml
├── frontend/
├── boto3-iac-script.py
├── complete-deployment-script.py
├── lambda-backup-script.py
├── Jenkins.groovy
└── README.md
```

---

## 🧠 Architecture Overview

### 🗂 Architecture Flow
1. **Frontend** in React → Hosted on EC2
2. **Two Backend Microservices**:
   - `helloservice`
   - `profileservice`
   → Hosted on EC2/Auto Scaling Group
3. **Dockerized & Stored in ECR**
4. **CI/CD** with Jenkins (GitHub → Jenkins → Docker/ECR → Deploy via Boto3)
5. **ELB** handles routing
6. **CloudWatch** logs and monitors everything
7. **S3** + Lambda for DB backups
8. **SNS + Slack** for ChatOps notifications

✅ Architecture Diagram

![Architecture](https://github.com/user-attachments/assets/111f5b27-e267-41fd-b867-fb527b098018)

---

## 🏁 Quick Start – Local Setup

### 1. Clone Repository
```bash
git clone https://github.com/aakashrawat1910/Project-Orchestration-and-Scaling.git
cd Project-Orchestration-and-Scaling
```

### 2. Run Backend Locally (with Docker)
```bash
cd backend
docker-compose up --build
```

### 3. Run Frontend Locally
```bash
cd frontend
npm install
npm start
```

---

## ☁️ AWS Setup

### Configure AWS CLI:
```bash
aws configure
# Add your AWS Access Key, Secret, Region
```

---

## 🐳 Docker & ECR Commands

### 1. Authenticate Docker to ECR:
```bash
aws ecr get-login-password --region us-west-1 | docker login --username AWS --password-stdin <your-aws-id>.dkr.ecr.us-west-1.amazonaws.com
```

### 2. Build & Push Images
```bash
# Backend
docker build -t helloservice ./backend/helloservice
docker tag helloservice:latest <ECR_REPO_URL>/helloservice
docker push <ECR_REPO_URL>/helloservice

docker build -t profileservice ./backend/profileservice
docker tag profileservice:latest <ECR_REPO_URL>/profileservice
docker push <ECR_REPO_URL>/profileservice

# Frontend
docker build -t frontend ./frontend
docker tag frontend:latest <ECR_REPO_URL>/frontend
docker push <ECR_REPO_URL>/frontend
```

---

## 🤖 Jenkins Setup (CI/CD)

### Jenkins URL:
📍 http://jekins:8080  
👤 Username: `username`  
🔐 Password: `password`

### Jenkins Groovy Pipeline (`Jenkins.groovy`)
- Clones repo
- Builds Docker image
- Pushes to ECR
- Triggers Boto3 deployment

> 💡 **Add Webhook to GitHub Repo** to auto-trigger builds

---

## 🧾 Infrastructure via Boto3

### 1. Set Up Infra
```bash
python boto3-iac-script.py
```

Creates:
- VPC
- Subnets
- Security Groups
- Launch Configuration
- Auto Scaling Group
- ELB

### 2. Full Deployment
```bash
python complete-deployment-script.py
```

Deploys everything: infra + Docker containers

---

## ☁️ AWS Lambda (Backups)

### Backup Script
```bash
python lambda-backup-script.py
```

- Automates Lambda creation for DB backup
- Stores in S3 with timestamp
- Schedule with CloudWatch Events

---

## 🛰 Kubernetes (EKS - Optional)

### Create EKS Cluster:
```bash
eksctl create cluster --name mern-cluster --region us-west-1
```

### Deploy with Helm:
```bash
helm install mern-app ./chart/
```

---

## 🔔 ChatOps Setup

1. **Create SNS Topics** (e.g., `deployment-success`, `deployment-failure`)
2. **Lambda Function** reads deployment logs → sends to SNS
3. **Slack Integration**: Use webhook URLs to push SNS alerts to Slack or Teams

---

## 📊 Monitoring & Logging

- Enable **CloudWatch Alarms** for:
  - CPU > 80%
  - Memory spike
- Enable **CloudWatch Logs** for:
  - EC2 logs
  - Lambda logs

---

## ✅ Final Testing

- `curl <LoadBalancerDNS>/hello`
- Open React frontend → confirm data loads
- Check Jenkins job results
- Check S3 for Lambda backup logs

---

## 💡 Useful Links

- [How to Pull Changes from Forked Repo](https://stackoverflow.com/questions/3903817/pull-new-updates-from-original-github-repository-into-forked-github-repository)
- [Amazon EKS Docs](https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html)
- [Helm Charts Guide](https://helm.sh/docs/intro/using_helm/)
