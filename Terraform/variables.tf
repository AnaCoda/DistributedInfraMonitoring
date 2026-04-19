variable "project_name" {
  description = "Prefix applied to created AWS resources."
  type        = string
  default     = "distinfra"
}

variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr" {
  description = "CIDR block for the deployment VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for the application subnet."
  type        = string
  default     = "10.42.1.0/24"
}

variable "availability_zone" {
  description = "Optional availability zone for the subnet."
  type        = string
  default     = null
}

variable "allowed_ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH into the instances."
  type        = list(string)
  default     = []
}

variable "allowed_frontend_cidr_blocks" {
  description = "CIDR blocks allowed to reach capital websocket ports from outside AWS."
  type        = list(string)
  default     = []
}

variable "key_name" {
  description = "Optional EC2 key pair name."
  type        = string
  default     = null
}

variable "assign_public_ip" {
  description = "Whether to assign public IPs to instances."
  type        = bool
  default     = true
}

variable "instance_type_capital" {
  description = "EC2 type for capital replicas."
  type        = string
  default     = "t3.small"
}

variable "instance_type_region" {
  description = "EC2 type for regional replicas."
  type        = string
  default     = "t3.small"
}

variable "capital_base_port" {
  description = "Base port range for capital replicas."
  type        = number
  default     = 4000
}

variable "region_base_port" {
  description = "Base port range for regional replicas."
  type        = number
  default     = 3050
}

variable "app_repo_url" {
  description = "Git repository URL."
  type        = string
  default     = "https://github.com/AnaCoda/DistributedInfraMonitoring"
}

variable "app_repo_ref" {
  description = "Git branch/tag/commit to deploy."
  type        = string
  default     = "hosting"
}

variable "app_dir" {
  description = "Directory where the repository is cloned."
  type        = string
  default     = "/opt/DistributedInfraMonitoring"
}

variable "app_user" {
  description = "OS user that runs the application services."
  type        = string
  default     = "ec2-user"
}