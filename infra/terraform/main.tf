resource "aws_key_pair" "deploy" {
  key_name   = "agriculture-rag-deploy"
  public_key = var.ssh_public_key
}

resource "aws_security_group" "alb" {
  name   = "agriculture-rag-alb"
  vpc_id = var.vpc_id

  ingress {
    description = "HTTPS from approved clients"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "api" {
  name   = "agriculture-rag-api"
  vpc_id = var.vpc_id

  ingress {
    description     = "API traffic from the load balancer only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Restricted deployment SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "ec2" {
  name = "agriculture-rag-ec2"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "bedrock" {
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
      Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
    }, {
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParameters"]
      Resource = "arn:aws:ssm:${var.aws_region}:*:parameter${var.app_config_parameter_name}"
    }, {
      Effect   = "Allow"
      Action   = [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "agriculture-rag-ec2"
  role = aws_iam_role.ec2.name
}

resource "aws_instance" "api" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.api.id]
  key_name                    = aws_key_pair.deploy.key_name
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  associate_public_ip_address = false
  user_data                   = file("${path.module}/user_data.sh")

  tags = {
    Name = "agriculture-rag-api"
  }
}

resource "aws_lb" "api" {
  name               = "agriculture-rag-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.alb_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name     = "agriculture-rag-api"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_target_group_attachment" "api" {
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = aws_instance.api.id
  port             = 8000
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_wafv2_web_acl" "api" {
  name  = "agriculture-rag-api"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit"
    priority = 1
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "agriculture-rag-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "agriculture-rag-api"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_lb.api.arn
  web_acl_arn  = aws_wafv2_web_acl.api.arn
}
