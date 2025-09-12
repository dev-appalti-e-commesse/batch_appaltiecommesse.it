# AWS Batch Job Definitions with Secrets Manager integration

# Job Definition for Metric Computation
resource "aws_batch_job_definition" "metric_computation" {
  name = var.job_definition_metric_computation
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}:latest"
    
    # Fargate requires these specific resource requirements
    resourceRequirements = [
      {
        type  = "VCPU"
        value = tostring(var.container_vcpus)
      },
      {
        type  = "MEMORY"
        value = tostring(var.container_memory)
      }
    ]

    # Job role for accessing AWS services (S3, Secrets Manager)
    jobRoleArn       = aws_iam_role.batch_job_role.arn
    executionRoleArn = aws_iam_role.batch_execution_role.arn

    # Network configuration for Fargate
    networkConfiguration = {
      assignPublicIp = "ENABLED"
    }

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

    # Environment variables (non-sensitive configuration)
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

    # Logging configuration
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "metric-computation"
      }
    }
  })

  retry_strategy {
    attempts = 1
  }

  timeout {
    attempt_duration_seconds = 3600  # 1 hour timeout
  }

  tags = {
    JobType = "metricComputation"
  }
}

# Job Definition for Metadata Extraction
resource "aws_batch_job_definition" "metadata_extraction" {
  name = var.job_definition_metadata_extraction
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}:latest"
    
    resourceRequirements = [
      {
        type  = "VCPU"
        value = tostring(var.container_vcpus)
      },
      {
        type  = "MEMORY"
        value = tostring(var.container_memory)
      }
    ]

    jobRoleArn       = aws_iam_role.batch_job_role.arn
    executionRoleArn = aws_iam_role.batch_execution_role.arn

    networkConfiguration = {
      assignPublicIp = "ENABLED"
    }

    # Basic secrets for metadata extraction
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
        "awslogs-group"         = aws_cloudwatch_log_group.batch_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "metadata-extraction"
      }
    }
  })

  retry_strategy {
    attempts = 1
  }

  timeout {
    attempt_duration_seconds = 1800  # 30 minutes timeout
  }

  tags = {
    JobType = "metadataExtraction"
  }
}

# IAM role for batch jobs (to access S3, Secrets Manager, etc.)
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
}

# Policy for job role to access S3 and other AWS services
resource "aws_iam_policy" "batch_job_policy" {
  name        = "${var.project_name}-batch-job-policy"
  description = "Policy for AWS Batch jobs to access required AWS services"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 Access
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::private-tender-documents/*",
          "arn:aws:s3:::metric-computation-documents/*",
          "arn:aws:s3:::private-tender-documents",
          "arn:aws:s3:::metric-computation-documents"
        ]
      },
      # CloudWatch Logs
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_job_policy_attachment" {
  role       = aws_iam_role.batch_job_role.name
  policy_arn = aws_iam_policy.batch_job_policy.arn
}

# Attach secrets policy to job role
resource "aws_iam_role_policy_attachment" "batch_job_secrets_policy_attachment" {
  role       = aws_iam_role.batch_job_role.name
  policy_arn = aws_iam_policy.batch_secrets_policy.arn
}

# CloudWatch Log Group for batch jobs
resource "aws_cloudwatch_log_group" "batch_logs" {
  name              = "/aws/batch/${var.project_name}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-batch-logs"
  }
}

# Outputs
output "metric_computation_job_definition_arn" {
  description = "ARN of the metric computation job definition"
  value       = aws_batch_job_definition.metric_computation.arn
}

output "metadata_extraction_job_definition_arn" {
  description = "ARN of the metadata extraction job definition"
  value       = aws_batch_job_definition.metadata_extraction.arn
}

output "batch_job_role_arn" {
  description = "ARN of the batch job role"
  value       = aws_iam_role.batch_job_role.arn
}