terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region for deployment"
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment name"
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  default     = "appalti-batch"
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

locals {
  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
  }
}

# ECR Repository for Docker images
resource "aws_ecr_repository" "batch_jobs" {
  name                 = "${var.project_name}-jobs"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# VPC and Networking (using default VPC for simplicity)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_security_group" "default" {
  vpc_id = data.aws_vpc.default.id
  name   = "default"
}

# IAM Roles for Batch
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

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "batch_service_role" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# ECS Task Execution Role
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-task-execution-role"

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

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Policy for execution role to access secrets
resource "aws_iam_role_policy" "ecs_secrets_policy" {
  name = "${var.project_name}-ecs-secrets-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.batch_secrets.arn
        ]
      }
    ]
  })
}

# Job Role for containers
resource "aws_iam_role" "batch_job_role" {
  name = "${var.project_name}-batch-job-role"

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

  tags = local.common_tags
}

# AWS Secrets Manager for secure configuration
resource "aws_secretsmanager_secret" "batch_secrets" {
  name        = "appalti-batch-secrets"
  description = "Secrets for AWS Batch jobs (extractMetricComputation.py)"
  
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "batch_secrets" {
  secret_id = aws_secretsmanager_secret.batch_secrets.id
  
  # Placeholder JSON structure - will be overwritten by GitHub Actions
  secret_string = jsonencode({
    MONGO_URI      = "placeholder-will-be-set-by-github-actions"
    SMTP_HOST      = "smtp.gmail.com"
    SMTP_PORT      = "587"
    SMTP_USER      = "placeholder-will-be-set-by-github-actions"
    SMTP_PASSWORD  = "placeholder-will-be-set-by-github-actions"
    EMAIL_FROM     = "placeholder-will-be-set-by-github-actions"
    GOOGLE_API_KEY = "placeholder-will-be-set-by-github-actions"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Policy for job role (add S3, Secrets Manager permissions)
resource "aws_iam_role_policy" "batch_job_policy" {
  name = "${var.project_name}-batch-job-policy"
  role = aws_iam_role.batch_job_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::private-tender-documents",
          "arn:aws:s3:::private-tender-documents/*",
          "arn:aws:s3:::metric-computation-documents",
          "arn:aws:s3:::metric-computation-documents/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.batch_secrets.arn
        ]
      }
    ]
  })
}

# Batch Compute Environment
resource "aws_batch_compute_environment" "main" {
  compute_environment_name = "${var.project_name}-compute-env"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role            = aws_iam_role.batch_service_role.arn

  compute_resources {
    type               = "FARGATE"
    max_vcpus          = 256
    security_group_ids = [data.aws_security_group.default.id]
    # Using specific subnets instead of all default VPC subnets to fix network issues
    subnets           = [
      "subnet-058c2403ce4f3053c",  # eu-central-1a (public subnet with IGW)
      "subnet-09f310b71fc64e81e",  # eu-central-1b (public subnet with IGW)
      "subnet-01d7d747b6e40c3c0"   # eu-central-1c (public subnet with IGW)
    ]
  }

  tags = local.common_tags
}

# Batch Job Queue
resource "aws_batch_job_queue" "main" {
  name                 = "${var.project_name}-job-queue"
  state                = "ENABLED"
  priority             = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.main.arn
  }

  tags = local.common_tags
}

# Job Definition for Metric Computation
resource "aws_batch_job_definition" "metric_computation" {
  name = "${var.project_name}-metric-computation"
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch_jobs.repository_url}:latest"
    
    jobRoleArn       = aws_iam_role.batch_job_role.arn
    executionRoleArn = aws_iam_role.ecs_task_execution_role.arn
    
    fargatePlatformConfiguration = {
      platformVersion = "LATEST"
    }
    
    networkConfiguration = {
      assignPublicIp = "ENABLED"
    }
    
    resourceRequirements = [
      {
        type  = "VCPU"
        value = "1"
      },
      {
        type  = "MEMORY"
        value = "2048"
      }
    ]
    
    # Secrets from AWS Secrets Manager
    secrets = [
      {
        name      = "MONGO_URI"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:MONGO_URI::"
      },
      {
        name      = "SMTP_HOST"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:SMTP_HOST::"
      },
      {
        name      = "SMTP_PORT"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:SMTP_PORT::"
      },
      {
        name      = "SMTP_USER"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:SMTP_USER::"
      },
      {
        name      = "SMTP_PASSWORD"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:SMTP_PASSWORD::"
      },
      {
        name      = "EMAIL_FROM"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:EMAIL_FROM::"
      },
      {
        name      = "GOOGLE_API_KEY"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:GOOGLE_API_KEY::"
      }
    ]
    
    environment = [
      {
        name  = "JOB_TYPE"
        value = "extractMetricComputation"
      },
      {
        name  = "AWS_REGION"
        value = var.aws_region
      },
      {
        name  = "DATABASE_NAME"
        value = "appalti_e_commesse"
      }
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/aws/batch/${var.project_name}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "metric-computation"
      }
    }
  })

  tags = local.common_tags
}

# Job Definition for Metadata Extraction
resource "aws_batch_job_definition" "metadata_extraction" {
  name = "${var.project_name}-metadata-extraction"
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = "${aws_ecr_repository.batch_jobs.repository_url}:latest"
    
    jobRoleArn       = aws_iam_role.batch_job_role.arn
    executionRoleArn = aws_iam_role.ecs_task_execution_role.arn
    
    fargatePlatformConfiguration = {
      platformVersion = "LATEST"
    }
    
    networkConfiguration = {
      assignPublicIp = "ENABLED"
    }
    
    resourceRequirements = [
      {
        type  = "VCPU"
        value = "0.25"
      },
      {
        type  = "MEMORY"
        value = "512"
      }
    ]
    
    # Secrets from AWS Secrets Manager
    secrets = [
      {
        name      = "GOOGLE_API_KEY"
        valueFrom = "${aws_secretsmanager_secret.batch_secrets.arn}:GOOGLE_API_KEY::"
      }
    ]
    
    environment = [
      {
        name  = "JOB_TYPE"
        value = "extractMetadata"
      },
      {
        name  = "AWS_REGION"
        value = var.aws_region
      }
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/aws/batch/${var.project_name}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "metadata-extraction"
      }
    }
  })

  tags = local.common_tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "batch_logs" {
  name              = "/aws/batch/${var.project_name}"
  retention_in_days = 7

  tags = local.common_tags
}

# Outputs
output "ecr_repository_url" {
  value = aws_ecr_repository.batch_jobs.repository_url
}

output "job_queue_arn" {
  value = aws_batch_job_queue.main.arn
}

output "job_queue_name" {
  value = aws_batch_job_queue.main.name
}

output "metric_computation_job_definition" {
  value = aws_batch_job_definition.metric_computation.name
}

output "metadata_extraction_job_definition" {
  value = aws_batch_job_definition.metadata_extraction.name
}

output "region" {
  value = var.aws_region
}