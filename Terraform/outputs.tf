output "capital_public_ips" {
  value = {
    for name, instance in aws_instance.capital : name => instance.public_ip
  }
}

output "capital_private_ips" {
  value = {
    for name, instance in aws_instance.capital : name => instance.private_ip
  }
}

output "regional_public_ips" {
  value = {
    for name, instance in aws_instance.regional : name => instance.public_ip
  }
}

output "regional_private_ips" {
  value = {
    for name, instance in aws_instance.regional : name => instance.private_ip
  }
}

output "infra_public_ips" {
  value = {
    for name, instance in aws_instance.infra : name => instance.public_ip
  }
}

output "infra_private_ips" {
  value = {
    for name, instance in aws_instance.infra : name => instance.private_ip
  }
}

data "aws_caller_identity" "current" {}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_arn" {
  value = data.aws_caller_identity.current.arn
}

output "aws_user_id" {
  value = data.aws_caller_identity.current.user_id
}