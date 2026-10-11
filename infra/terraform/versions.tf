terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }

    # Configure this backend with -backend-config=backend.hcl.
    # The state bucket and lock table are created by infra/terraform/bootstrap_state.
    backend "s3" {
      encrypt        = true
      use_lockfile   = true
    }
  }
}

provider "aws" {
  region = var.aws_region
}
