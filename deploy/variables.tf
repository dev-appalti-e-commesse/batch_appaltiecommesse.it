# Terraform variables for AWS Batch infrastructure

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "appalti-batch"
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

# ECR Configuration
variable "ecr_repository_name" {
  description = "ECR repository name for Docker images"
  type        = string
  default     = "appalti-batch-jobs"
}

# Batch Configuration
variable "compute_environment_name" {
  description = "Name of the AWS Batch compute environment"
  type        = string
  default     = "appalti-batch-compute-env"
}

variable "job_queue_name" {
  description = "Name of the AWS Batch job queue"
  type        = string
  default     = "appalti-batch-job-queue"
}

variable "job_definition_metric_computation" {
  description = "Name of the metric computation job definition"
  type        = string
  default     = "appalti-batch-metric-computation"
}

variable "job_definition_metadata_extraction" {
  description = "Name of the metadata extraction job definition"
  type        = string
  default     = "appalti-batch-metadata-extraction"
}

# Container Configuration
variable "container_vcpus" {
  description = "Number of vCPUs for batch jobs"
  type        = number
  default     = 1
}

variable "container_memory" {
  description = "Memory in MB for batch jobs"
  type        = number
  default     = 2048
}

variable "max_compute_environments" {
  description = "Maximum number of compute environments"
  type        = number
  default     = 10
}

# VPC Configuration (optional - can use default VPC)
variable "vpc_id" {
  description = "VPC ID for batch compute environment (optional)"
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Subnet IDs for batch compute environment (optional)"
  type        = list(string)
  default     = []
}