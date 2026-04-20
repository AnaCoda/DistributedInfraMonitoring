data "aws_route53_zone" "main" {
  count = var.domain_name == null ? 0 : 1

  name         = var.domain_name
  private_zone = false
}

resource "aws_route53_record" "capital" {
  for_each = var.domain_name == null ? {} : aws_instance.capital

  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "${each.key}.${var.domain_name}"
  type    = "A"
  ttl     = 60
  records = [each.value.public_ip]
}

resource "aws_route53_record" "regional" {
  for_each = var.domain_name == null ? {} : aws_instance.regional

  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "${lower(each.key)}.${var.domain_name}"
  type    = "A"
  ttl     = 60
  records = [each.value.public_ip]
}

resource "aws_route53_record" "infra" {
  for_each = var.domain_name == null ? {} : aws_instance.infra

  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "${lower(each.key)}.${var.domain_name}"
  type    = "A"
  ttl     = 60
  records = [each.value.public_ip]
}