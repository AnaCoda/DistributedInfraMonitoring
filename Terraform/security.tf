resource "aws_security_group" "cluster" {
  name        = "${var.project_name}-cluster-sg"
  description = "Security group for capitals, regions, and hosted infra"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "Intra-VPC application traffic"
    from_port   = 3000
    to_port     = 4100
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  dynamic "ingress" {
    for_each = length(var.allowed_ssh_cidr_blocks) > 0 ? [1] : []
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.allowed_ssh_cidr_blocks
    }
  }

  dynamic "ingress" {
    for_each = length(var.allowed_frontend_cidr_blocks) > 0 ? [1] : []
    content {
      description = "Frontend access to capital websocket ports"
      from_port   = 4000
      to_port     = 4003
      protocol    = "tcp"
      cidr_blocks = var.allowed_frontend_cidr_blocks
    }
  }

  ingress {
    description     = "ALB to application websocket port"
    from_port       = 4000
    to_port         = 4000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-cluster-sg"
  }
}

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Security group for public HTTPS/WSS load balancer"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTPS / WSS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}
