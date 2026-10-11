resource "aws_ecr_repository" "api" {
  name                 = "agriculture-rag"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

output "ecr_registry" {
  value = split("/", aws_ecr_repository.api.repository_url)[0]
}
