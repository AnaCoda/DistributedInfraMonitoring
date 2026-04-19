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