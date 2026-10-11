# AWS deployment

This directory provisions the production baseline:

- Private EC2 host running the API container
- Public Application Load Balancer with HTTPS
- ECR repository with scan-on-push
- Bedrock and SSM permissions for the EC2 role
- GitHub Actions OIDC deployment role
- AWS WAF rate limiting and CloudWatch alarms
- Encrypted S3 Terraform state bootstrap

Terraform 1.10 or newer is required because the S3 backend uses native state locking.

## Bootstrap state

Run this once from `bootstrap_state/` with a globally unique bucket name:

```bash
terraform -chdir=bootstrap_state init
terraform -chdir=bootstrap_state apply \
  -var='state_bucket_name=your-unique-state-bucket'
```

Copy `backend.hcl.example` to `backend.hcl`, set the bucket name, and initialize
the main stack:

```bash
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform validate
terraform plan -var-file=terraform.tfvars
```

## Application configuration

Create an SSM `SecureString` at the value of `app_config_parameter_name`. Its value
must be an environment-file payload containing at least:

```text
API_REQUIRE_AUTH=true
API_AUTH_MODE=local
JWT_SECRET=<random-value-at-least-32-characters>
API_ADMIN_PASSWORD_HASH=<PBKDF2 hash generated with python scripts/generate_password_hash.py>
RAG_PROVIDER=bedrock
AWS_REGION=<deployment-region>
BEDROCK_MODEL_ID=<approved-model-id>
```

For Cognito/Auth0/Okta, set `API_AUTH_MODE=oidc`, `OIDC_ISSUER`, and
`OIDC_AUDIENCE`; local `/auth/token` issuance is then disabled.

Do not commit this value or place it in Terraform variables. The EC2 role reads it
only during deployment through Systems Manager.

## GitHub environment

Create a protected `production` environment with:

- Secret `AWS_DEPLOY_ROLE_ARN`: output `github_deploy_role_arn`
- Secret `EC2_INSTANCE_ID`: output `aws_instance.api.id`
- Variable `AWS_REGION`
- Variable `APP_CONFIG_PARAMETER`

Require an approval before the deployment job can run.
