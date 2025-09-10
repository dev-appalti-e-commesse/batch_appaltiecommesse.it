#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Starting AWS Batch deployment...${NC}"

# Check if AWS credentials are configured
aws sts get-caller-identity > /dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform is not installed${NC}"
    exit 1
fi

# Navigate to deploy directory
cd deploy

# Initialize Terraform
echo -e "${YELLOW}🔧 Initializing Terraform...${NC}"
terraform init

# Validate configuration
echo -e "${YELLOW}✅ Validating Terraform configuration...${NC}"
terraform validate

# Plan deployment
echo -e "${YELLOW}📋 Creating Terraform plan...${NC}"
terraform plan -out=tfplan

# Ask for confirmation
echo -e "${YELLOW}❓ Do you want to apply this plan? (y/N)${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    # Apply plan
    echo -e "${YELLOW}🚀 Applying Terraform plan...${NC}"
    terraform apply tfplan
    
    # Save outputs
    echo -e "${YELLOW}💾 Saving Terraform outputs...${NC}"
    terraform output -json > ../terraform-outputs.json
    
    echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
    echo -e "${GREEN}📄 Outputs saved to terraform-outputs.json${NC}"
    
    # Display key outputs
    echo -e "${YELLOW}🔑 Key Resources Created:${NC}"
    echo -e "${GREEN}ECR Repository:${NC} $(terraform output -raw ecr_repository_url)"
    echo -e "${GREEN}Job Queue:${NC} $(terraform output -raw job_queue_name)"
    echo -e "${GREEN}Region:${NC} $(terraform output -raw region)"
    
else
    echo -e "${YELLOW}⏹️  Deployment cancelled${NC}"
    rm -f tfplan
fi