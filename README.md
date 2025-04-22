# 🧱 MERN Microservices Orchestration & Scaling Project

This project demonstrates how to build, containerize, orchestrate, and scale a MERN stack microservices application using **Docker**, **AWS (ECS/EC2/EKS)**, **Boto3**, **Jenkins**, and **ChatOps**.

## 📁 Project Structure

```
Project-Orchestration-and-Scaling/
├── backend/
│   ├── helloservice/         # Microservice 1
│   │   ├── Dockerfile
│   │   ├── index.js
│   │   └── package.json
│   ├── profileservice/       # Microservice 2
│   │   ├── Dockerfile
│   │   ├── index.js
│   │   └── package.json
│   └── docker-compose.yml
├── frontend/                 # React frontend
│   ├── Dockerfile
│   ├── package.json
│   └── public/, src/
├── boto3-automation/
│   ├── boto3-iac-script.py                # IaC using Boto3
│   ├── complete-deployment-script.py     # Full automation with Boto3
│   └── lambda-backup-script.py           # Lambda script for DB backups
├── Jenkins.groovy            # Jenkins CI/CD Pipeline script
├── README.md                 # 📄 You are here!
```

---

## 🧠 Architecture Overview

### 📌 Architecture Diagram
![Architecture Diagram](ea57fffa-6cda-4942-a4e5-99aac6b02d92.png)

### 🛠 Components Used

- **Frontend**: React
- **Backend Microservices**: Node.js (helloservice, profileservice)
- **Containerization**: Docker
- **Orchestration**: Docker Compose → ECS/EKS
- **Automation & IaC**: Python Boto3 Scripts
- **CI/CD**: Jenkins (on EC2)
- **Monitoring**: AWS CloudWatch
- **Notification**: SNS + Lambda + Slack (ChatOps)
- **Storage**: S3
- **Load Balancing**: AWS ELB

---

## 🧪 Run Locally

### 1. Clone Repo
```bash
git clone https://github.com/aakashrawat1910/Project-Orchestration-and-Scaling.git
cd Project-Orchestration-and-Scaling
```

### 2. Start Containers Locally
```bash
cd backend
docker-compose up --build
```

---

## 🪄 Deployment Steps

### 🔧 Step 1: Set Up AWS

- Install and configure AWS CLI:
```bash
aws configure
```

- Install required Python packages:
```bash
pip install boto3
```

---

### 🐳 Step 2: Containerize App

Each microservice and frontend has its own Dockerfile. Use:
```bash
docker-compose build
```

---

### 📦 Step 3: Push to Amazon ECR

```bash
aws ecr get-login-password --region us-west-1 | docker login --username AWS --password-stdin <ECR_URL>

docker build -t aakash/project-orc .
docker tag aakash/project-orc:latest <ECR_URL>/aakash/project-orc:latest
docker push <ECR_URL>/aakash/project-orc:latest
```

---

### 🤖 Step 4: Setup Jenkins on EC2

- Access Jenkins: [http://3.111.188.91:8080](http://3.111.188.91:8080)
  - Username: `herovired`
  - Password: `herovired`

- Jenkins job executes `Jenkins.groovy`:
  - Builds Docker images
  - Pushes to ECR
  - Triggers Boto3 deployment

---

### ☁️ Step 5: Infrastructure as Code (Boto3)

Use:
- `boto3-iac-script.py` – Creates VPC, subnets, ASG, ELB.
- `complete-deployment-script.py` – Automates full stack deployment.
- `lambda-backup-script.py` – Creates a Lambda to backup DB to S3 with timestamp.

---

### 🚀 Step 6: Deployment Strategy

- Backend: EC2 via Auto Scaling Group
- Frontend: EC2 instance
- Load Balancer setup (ELB)
- DNS via Route 53

---

### ☸️ Step 10: Kubernetes (Optional)

Use Helm + `eksctl`:
```bash
eksctl create cluster --name mern-cluster --region us-west-1
helm install mern-chart ./chart/
```

---

### 📈 Step 11: Monitoring & Logging

- Use **CloudWatch** for metrics & logs.
- Set alarms for failures or high CPU.

---

### 💬 Step 14: ChatOps Integration

1. **SNS**: Create topics (success/failure).
2. **Lambda**: Trigger notifications based on events.
3. **Slack/Teams**: Integrate SNS with messaging platforms.
4. **SES**: For email alerts.

---

## 🧪 Final Check

- Ensure containers are up.
- Validate frontend is reachable.
- Test endpoints of each microservice.

---

## 🔗 Useful Links

- GitHub: [SampleMERNwithMicroservices](https://github.com/UnpredictablePrashant/SampleMERNwithMicroservices)
- Fork Instructions: [How to pull changes from original repo](https://stackoverflow.com/questions/3903817/pull-new-updates-from-original-github-repository-into-forked-github-repository)

---

## 🤝 Contributing

If you're learning DevOps and MERN, this repo is for you! Fork, experiment, break things, and rebuild. That's the spirit!

