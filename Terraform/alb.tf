locals {
  public_ws_targets = var.domain_name == null ? {} : merge(
    {
      for name, node in local.capital_nodes :
      name => {
        hostname    = "${lower(name)}.${var.domain_name}"
        instance_id = aws_instance.capital[name].id
        port        = node.port
      }
    },
    {
      for name, node in local.regional_nodes :
      name => {
        hostname    = "${lower(name)}.${var.domain_name}"
        instance_id = aws_instance.regional[name].id
        port        = node.port
      }
    },
    {
      for name, node in local.infra_nodes :
      name => {
        hostname    = "${lower(name)}.${var.domain_name}"
        instance_id = aws_instance.infra[name].id
        port        = 4000
      }
    }
  )
}

resource "aws_acm_certificate" "wildcard" {
  count = var.domain_name == null ? 0 : 1

  domain_name               = "*.${var.domain_name}"
  subject_alternative_names = [var.domain_name]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = var.domain_name == null ? {} : {
    for option in aws_acm_certificate.wildcard[0].domain_validation_options :
    option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main[0].zone_id
}

resource "aws_acm_certificate_validation" "wildcard" {
  count = var.domain_name == null ? 0 : 1

  certificate_arn         = aws_acm_certificate.wildcard[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

resource "aws_lb" "public_ws" {
  count = var.domain_name == null ? 0 : 1

  name               = "${var.project_name}-ws-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.app.id, aws_subnet.alb.id]

  tags = {
    Name = "${var.project_name}-ws-alb"
  }
}

resource "aws_lb_target_group" "public_ws" {
  for_each = local.public_ws_targets

  name        = substr("${var.project_name}-${replace(lower(each.key), "_", "-")}", 0, 32)
  port        = each.value.port
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = aws_vpc.this.id

  health_check {
    enabled  = true
    matcher  = "200"
    path     = "/health"
    port     = "traffic-port"
    protocol = "HTTP"
  }
}

resource "aws_lb_target_group_attachment" "public_ws" {
  for_each = local.public_ws_targets

  target_group_arn = aws_lb_target_group.public_ws[each.key].arn
  target_id        = each.value.instance_id
  port             = each.value.port
}

resource "aws_lb_listener" "https" {
  count = var.domain_name == null ? 0 : 1

  load_balancer_arn = aws_lb.public_ws[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.wildcard[0].certificate_arn

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "No matching websocket host"
      status_code  = "404"
    }
  }
}

resource "aws_lb_listener_rule" "public_ws" {
  for_each = local.public_ws_targets

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 100 + index(sort(keys(local.public_ws_targets)), each.key)

  condition {
    host_header {
      values = [each.value.hostname]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.public_ws[each.key].arn
  }
}
