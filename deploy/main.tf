# Main Terraform configuration for AWS Batch infrastructure

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Configure S3 backend for state storage (recommended for production)
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "appalti-batch/terraform.tfstate"
  #   region = "eu-central-1"
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}

# IAM role for AWS Batch jobs
resource "aws_iam_role" "batch_execution_role" {
  name = "${var.project_name}-batch-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Attach the AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "batch_execution_role_policy" {
  role       = aws_iam_role.batch_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Attach our custom secrets policy
resource "aws_iam_role_policy_attachment" "batch_secrets_policy_attachment" {
  role       = aws_iam_role.batch_execution_role.name
  policy_arn = aws_iam_policy.batch_secrets_policy.arn
}

# IAM role for AWS Batch service
resource "aws_iam_role" "batch_service_role" {
  name = "${var.project_name}-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "batch.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_service_role_policy" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# Security group for batch compute environment
resource "aws_security_group" "batch_security_group" {
  name_prefix = "${var.project_name}-batch-sg"
  description = "Security group for AWS Batch compute environment"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-batch-security-group"
  }
}

# Get default VPC and subnets if not provided
data "aws_vpc" "default" {
  count   = var.vpc_id == null ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = length(var.subnet_ids) == 0 ? 1 : 0
  
  filter {
    name   = "vpc-id"
    values = [var.vpc_id == null ? data.aws_vpc.default[0].id : var.vpc_id]
  }
}

locals {
  vpc_id     = var.vpc_id == null ? data.aws_vpc.default[0].id : var.vpc_id
  subnet_ids = length(var.subnet_ids) == 0 ? data.aws_subnets.default[0].ids : var.subnet_ids
}

# AWS Batch Compute Environment
resource "aws_batch_compute_environment" "main" {
  compute_environment_name = var.compute_environment_name
  type                    = "MANAGED"
  state                   = "ENABLED"

  compute_resources {
    type               = "FARGATE"
    max_vcpus          = var.max_compute_environments
    security_group_ids = [aws_security_group.batch_security_group.id]
    subnets            = local.subnet_ids
  }

  service_role = aws_iam_role.batch_service_role.arn
  
  depends_on = [aws_iam_role_policy_attachment.batch_service_role_policy]
}

# AWS Batch Job Queue
resource "aws_batch_job_queue" "main" {
  name     = var.job_queue_name
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.main.arn
  }
}

# Outputs
output "compute_environment_arn" {
  description = "ARN of the AWS Batch compute environment"
  value       = aws_batch_compute_environment.main.arn
}

output "job_queue_arn" {
  description = "ARN of the AWS Batch job queue"
  value       = aws_batch_job_queue.main.arn
}

output "execution_role_arn" {
  description = "ARN of the batch execution role"
  value       = aws_iam_role.batch_execution_role.arn
}