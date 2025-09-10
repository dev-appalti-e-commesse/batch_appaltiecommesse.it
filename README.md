# AWS Batch System - Appalti e Commesse

Simple and efficient AWS Batch system for processing Italian procurement data with Node.js integration.

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with credentials
- Docker installed
- Terraform installed
- Node.js 18+ (for integration)
- Python 3.12.4

### 1. Build and Push Docker Image

```bash
# Login to ECR
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin [YOUR_ACCOUNT_ID].dkr.ecr.eu-central-1.amazonaws.com

# Build Docker image
docker build -t appalti-batch-jobs -f docker/Dockerfile .

# Tag image for ECR
docker tag appalti-batch-jobs:latest [YOUR_ACCOUNT_ID].dkr.ecr.eu-central-1.amazonaws.com/appalti-batch-jobs:latest

# Push to ECR
docker push [YOUR_ACCOUNT_ID].dkr.ecr.eu-central-1.amazonaws.com/appalti-batch-jobs:latest
```

### 2. Deploy AWS Infrastructure

```bash
cd deploy

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Deploy (one command!)
terraform apply -auto-approve

# Save outputs for Node.js integration
terraform output -json > ../terraform-outputs.json
```

### 3. Test Locally

```bash
# Test Metric Computation job
docker run -e JOB_TYPE=extractMetricComputation -e JOB_PARAMS='{"test":true}' appalti-batch-jobs

# Test Metadata extraction job
docker run -e JOB_TYPE=extractMetadata -e JOB_PARAMS='{"source":"local"}' appalti-batch-jobs
```

## 📦 Project Structure

```
batch_appaltiecommesse.it/
├── jobs/                        # Python batch jobs
│   ├── extractMetricComputation.py
│   └── extractMetadata.py
├── docker/                      # Container configuration
│   ├── Dockerfile
│   └── run.sh
├── deploy/                      # Infrastructure as Code
│   └── batch-setup.tf
├── nodejs-integration/          # Node.js integration code
│   └── batch-client.js
├── requirements.txt             # Python dependencies
└── README.md
```

## 🔧 Node.js Server Integration

### Install dependencies in your Node.js project

```bash
npm install aws-sdk dotenv
```

### Basic Integration

```javascript
const BatchClient = require("./batch_appaltiecommesse.it/nodejs-integration/batch-client");

// Initialize client (reads from .env file)
const batchClient = new BatchClient();

// Submit a metric computation job
const result = await batchClient.submitMetricComputationJob({
  source: "api",
  userId: "123",
});

console.log("Job ID:", result.jobId);

// Check job status
const status = await batchClient.getJobStatus(result.jobId);
console.log("Job Status:", status.status);
```

### Express.js Integration

```javascript
const express = require("express");
const BatchClient = require("./batch-client");

const app = express();
app.use(express.json());

const batchClient = new BatchClient();

// Auto-setup all routes
BatchClient.setupExpressRoutes(app, batchClient);

// Routes created:
// POST   /api/batch/metric-computation
// POST   /api/batch/metadata-extraction
// GET    /api/batch/jobs/:jobId
// DELETE /api/batch/jobs/:jobId
// GET    /api/batch/jobs

app.listen(3000, () => {
  console.log("Server running on port 3000");
});
```

## 📊 Job Types

### 1. Metric Computation (`extractMetricComputation`)

- Processes metrics from procurement data
- Accepts parameters via `JOB_PARAMS` environment variable
- Outputs: processed items, processing time, success rate

### 2. Metadata Extraction (`extractMetadata`)

- Extracts metadata from various sources
- Accepts source configuration via parameters
- Outputs: records extracted, extraction time, format

## 🔍 Monitoring

### CloudWatch Logs

Jobs automatically log to CloudWatch:

- Log Group: `/aws/batch/appalti-batch`
- Stream Prefix: `metric-computation` or `metadata-extraction`

### View Logs

```bash
# Recent logs for metric computation
aws logs tail /aws/batch/appalti-batch --follow --filter-pattern metric-computation

# Recent logs for metadata extraction
aws logs tail /aws/batch/appalti-batch --follow --filter-pattern metadata-extraction
```

## 🛠️ Development

### Local Testing

```bash
# Run job locally with Docker
docker build -t appalti-batch-jobs -f docker/Dockerfile .
docker run -e JOB_TYPE=extractMetricComputation -e JOB_PARAMS='{"test":true}' appalti-batch-jobs
```

### Add New Job Type

1. Create new Python script in `jobs/`
2. Update `docker/run.sh` to handle new JOB_TYPE
3. Add new job definition in `deploy/batch-setup.tf`
4. Add integration method in `nodejs-integration/batch-client.js`

## 📝 Environment Variables

### For Jobs (set via AWS Batch)

- `JOB_TYPE`: Type of job to run (`extractMetricComputation` or `extractMetadata`)
- `JOB_PARAMS`: JSON string with job parameters
- `AWS_BATCH_JOB_ID`: Automatically set by AWS Batch
- `AWS_BATCH_JQ_NAME`: Automatically set by AWS Batch

### For Node.js Integration

- `AWS_REGION`: AWS region (default: `eu-central-1`)
- `BATCH_JOB_QUEUE`: Job queue name
- `METRIC_COMPUTATION_JOB_DEF`: Metric computation job definition name
- `METADATA_EXTRACTION_JOB_DEF`: Metadata extraction job definition name

## 🚨 Troubleshooting

### Job Fails to Start

```bash
# Check job status
aws batch describe-jobs --jobs <job-id>

# Check compute environment
aws batch describe-compute-environments --compute-environments appalti-batch-compute-env
```

### Docker Image Issues

```bash
# Rebuild with no cache
docker build --no-cache -t appalti-batch-jobs -f docker/Dockerfile .

# Test locally before pushing
docker run -e JOB_TYPE=extractMetricComputation appalti-batch-jobs
```

### Terraform Issues

```bash
# Destroy and recreate
terraform destroy
terraform apply
```

## 🧹 Cleanup

To remove all AWS resources:

```bash
cd deploy
terraform destroy -auto-approve
```

To delete ECR repository:

```bash
aws ecr delete-repository --repository-name appalti-batch-jobs --force
```

## 📄 License

MIT

## 🤝 Support

For issues, check CloudWatch logs first:

- Log Group: `/aws/batch/appalti-batch`
- Job definitions: `appalti-batch-metric-computation`, `appalti-batch-metadata-extraction`
- Queue: `appalti-batch-job-queue`
