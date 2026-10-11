output "instance_public_ip" {
  value = aws_instance.api.public_ip
}

output "api_url" {
  value = "https://${aws_lb.api.dns_name}"
}
