#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 AWS Batch Complete Setup${NC}"
echo -e "${BLUE}================================${NC}"

# Step 1: Check prerequisites
echo -e "\n${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed${NC}"
    exit 1
fi

# Check Terraform
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform is not installed${NC}"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

# Check AWS credentials
aws sts get-caller-identity > /dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo -e "${YELLOW}💡 Run: aws configure${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites OK${NC}"

# Step 2: Setup environment
echo -e "\n${YELLOW}Step 2: Setting up environment files...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📄 Creating .env from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  PLEASE EDIT .env with your AWS credentials${NC}"
    read -p "Press Enter after editing .env..."
fi

if [ ! -f "deploy/terraform.tfvars" ]; then
    echo -e "${YELLOW}📄 Using default terraform.tfvars${NC}"
fi

# Step 3: Deploy infrastructure
echo -e "\n${YELLOW}Step 3: Deploying AWS infrastructure...${NC}"
./scripts/deploy.sh

# Step 4: Build and push Docker image
echo -e "\n${YELLOW}Step 4: Building and pushing Docker image...${NC}"
./scripts/build-and-push.sh

# Step 5: Test setup
echo -e "\n${YELLOW}Step 5: Testing setup...${NC}"
cd nodejs-integration

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 Installing Node.js dependencies...${NC}"
    npm install
fi

echo -e "${YELLOW}🧪 Running test job...${NC}"
node -e "
const BatchClient = require('./batch-client');
const client = new BatchClient();

async function test() {
    try {
        console.log('🚀 Submitting test job...');
        const result = await client.submitMetricComputationJob({
            test: true,
            timestamp: new Date().toISOString()
        });
        console.log('✅ Job submitted successfully:', result.jobId);
        
        // Check status after 10 seconds
        setTimeout(async () => {
            try {
                const status = await client.getJobStatus(result.jobId);
                console.log('📊 Job status:', status.status);
            } catch (e) {
                console.error('Error checking status:', e.message);
            }
        }, 10000);
        
    } catch (error) {
        console.error('❌ Test failed:', error.message);
        process.exit(1);
    }
}

test();
" &

cd ..

echo -e "\n${GREEN}🎉 Setup completed successfully!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Infrastructure deployed${NC}"
echo -e "${GREEN}✅ Docker image built and pushed${NC}"
echo -e "${GREEN}✅ Test job submitted${NC}"
echo -e "\n${YELLOW}💡 Check CloudWatch logs at:${NC}"
echo -e "${BLUE}/aws/batch/appalti-batch${NC}"
echo -e "\n${YELLOW}💡 Monitor jobs with:${NC}"
echo -e "${BLUE}aws batch list-jobs --job-queue appalti-batch-job-queue${NC}"