variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "ami_id" {
  type        = string
  description = "Amazon Linux 2023 AMI ID for the target region."
}

variable "instance_type" {
  type    = string
  default = "t3.medium"
}

variable "ssh_public_key" {
  type      = string
  sensitive = true
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "allowed_cidr" {
  type        = string
  description = "CIDR allowed to reach the public HTTPS load balancer."
}

variable "ssh_cidr" {
  type        = string
  description = "Trusted deployment source CIDR for SSH. Prefer a bastion or SSM instead."
}

variable "alb_subnet_ids" {
  type        = list(string)
  description = "At least two public subnet IDs for the HTTPS load balancer."
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for the API hostname."
}

variable "bedrock_model_id" {
  type    = string
  default = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "app_config_parameter_name" {
  type        = string
  default     = "/agriculture-rag/production/env"
  description = "SSM SecureString containing the container environment file."
}

variable "waf_rate_limit" {
  type        = number
  default     = 2000
  description = "Requests per five minutes per IP before AWS WAF blocks."
}
