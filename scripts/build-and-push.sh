#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION=${AWS_REGION:-eu-central-1}
PROJECT_NAME=${PROJECT_NAME:-appalti-batch}
ECR_REPO_NAME="${PROJECT_NAME}-jobs"

echo -e "${YELLOW}🚀 Starting build and push process...${NC}"

# Get AWS Account ID
echo -e "${YELLOW}🔍 Getting AWS Account ID...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Failed to get AWS Account ID. Check AWS credentials.${NC}"
    echo -e "${YELLOW}💡 Make sure you have run: aws configure${NC}"
    exit 1
fi

# Check if ECR repository exists
echo -e "${YELLOW}🔍 Checking if ECR repository exists...${NC}"
aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${AWS_REGION} > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ ECR repository ${ECR_REPO_NAME} not found in ${AWS_REGION}${NC}"
    echo -e "${YELLOW}💡 Run terraform apply first to create the repository${NC}"
    exit 1
fi

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo -e "${GREEN}✅ AWS Account ID: ${AWS_ACCOUNT_ID}${NC}"
echo -e "${GREEN}✅ ECR URI: ${ECR_URI}${NC}"

# Login to ECR
echo -e "${YELLOW}🔐 Logging in to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ ECR login failed${NC}"
    exit 1
fi

# Build Docker image
echo -e "${YELLOW}🏗️  Building Docker image...${NC}"
docker build -t ${ECR_REPO_NAME} -f docker/Dockerfile .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

# Tag image
echo -e "${YELLOW}🏷️  Tagging image...${NC}"
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest

# Push to ECR
echo -e "${YELLOW}📤 Pushing to ECR...${NC}"
docker push ${ECR_URI}:latest

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Push to ECR failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build and push completed successfully!${NC}"
echo -e "${GREEN}📦 Image available at: ${ECR_URI}:latest${NC}"