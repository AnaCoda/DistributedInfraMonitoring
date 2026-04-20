data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["137112412989"] # Amazon

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_instance" "capital" {
  for_each = local.capital_nodes

  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type_capital
  subnet_id                   = aws_subnet.app.id
  vpc_security_group_ids      = [aws_security_group.cluster.id]
  private_ip                  = each.value.private_ip
  associate_public_ip_address = var.assign_public_ip
  key_name                    = var.key_name
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/userdata/capital.sh.tpl", {
    node_name    = each.key
    capital_name = "rm"
    node_port    = each.value.port
    node_ip      = each.value.private_ip
    peers_json   = jsonencode(local.capital_peers)
    repo_url     = var.app_repo_url
    repo_ref     = var.app_repo_ref
    app_dir      = var.app_dir
    app_user     = var.app_user
    dns_name     = var.domain_name == null ? "" : "${lower(each.key)}.${var.domain_name}"
  })

  tags = {
    Name = each.key
    Role = "capital"
  }
}

resource "aws_instance" "regional" {
  for_each = local.regional_nodes

  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type_region
  subnet_id                   = aws_subnet.app.id
  vpc_security_group_ids      = [aws_security_group.cluster.id]
  private_ip                  = each.value.private_ip
  associate_public_ip_address = var.assign_public_ip
  key_name                    = var.key_name
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/userdata/regional.sh.tpl", {
    node_name     = each.key
    region_name   = each.value.region_name
    node_port     = each.value.port
    node_ip       = each.value.private_ip
    peers_json    = jsonencode(local.regional_peers_by_node[each.key])
    capitals_json = jsonencode(local.capital_peers)
    repo_url      = var.app_repo_url
    repo_ref      = var.app_repo_ref
    app_dir       = var.app_dir
    app_user      = var.app_user
    dns_name      = var.domain_name == null ? "" : "${lower(each.key)}.${var.domain_name}"
  })

  tags = {
    Name = each.key
    Role = "regional"
  }
}

resource "aws_instance" "infra" {
  for_each = local.infra_nodes

  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type_infra
  subnet_id                   = aws_subnet.app.id
  vpc_security_group_ids      = [aws_security_group.cluster.id]
  private_ip                  = each.value.private_ip
  associate_public_ip_address = var.assign_public_ip
  key_name                    = var.key_name
  user_data_replace_on_change = true

  user_data = templatefile("${path.module}/userdata/infra.sh.tpl", {
    node_name    = each.key
    node_type    = each.value.node_type
    regions_json = jsonencode(local.infra_regions_by_node[each.key])
    repo_url     = var.app_repo_url
    repo_ref     = var.app_repo_ref
    app_dir      = var.app_dir
    app_user     = var.app_user
    node_ip      = each.value.private_ip
    node_port    = 4000
    dns_name     = var.domain_name == null ? "" : "${lower(each.key)}.${var.domain_name}"
  })

  tags = {
    Name = each.key
    Role = "infra"
  }
}
