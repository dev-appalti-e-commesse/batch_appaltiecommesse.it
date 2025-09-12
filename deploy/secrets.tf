# AWS Secrets Manager configuration for batch job secrets
# These secrets will be populated by GitHub Actions and used by AWS Batch containers

# Create the secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "batch_secrets" {
  name        = "appalti-batch-secrets"
  description = "Secrets for AWS Batch jobs (extractMetricComputation.py)"
  
  # Enable automatic rotation if needed
  # rotation_rules {
  #   automatically_after_days = 90
  # }

  tags = {
    Project     = "appalti-e-commesse"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Create a secret version with placeholder values
# Real values will be set by GitHub Actions
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

# IAM policy for batch jobs to read secrets
resource "aws_iam_policy" "batch_secrets_policy" {
  name        = "appalti-batch-secrets-policy"
  description = "Allows AWS Batch jobs to read secrets from Secrets Manager"

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

  tags = {
    Project     = "appalti-e-commesse"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Output the secret ARN for use in job definitions
output "batch_secrets_arn" {
  description = "ARN of the batch secrets in AWS Secrets Manager"
  value       = aws_secretsmanager_secret.batch_secrets.arn
}

output "batch_secrets_policy_arn" {
  description = "ARN of the IAM policy for accessing batch secrets"
  value       = aws_iam_policy.batch_secrets_policy.arn
}