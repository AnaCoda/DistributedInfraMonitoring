locals {
  capital_nodes = {
    "rm-1" = {
      private_ip = "10.42.1.10"
      port       = 4001
    }
    "rm-2" = {
      private_ip = "10.42.1.11"
      port       = 4002
    }
    "rm-3" = {
      private_ip = "10.42.1.12"
      port       = 4003
    }
  }

  regional_nodes = {
    "Carstairs-r1" = {
      private_ip = "10.42.1.20"
      port       = 3051
    }
    "Carstairs-r2" = {
      private_ip = "10.42.1.21"
      port       = 3052
    }
  }

  capital_peers = [
    for name, node in local.capital_nodes : {
      name    = name
      address = {
        ip   = node.private_ip
        port = node.port
      }
    }
  ]

  regional_peers = [
    for name, node in local.regional_nodes : {
      name    = name
      address = {
        ip   = node.private_ip
        port = node.port
      }
    }
  ]

  infra_regions = [
    for name, node in local.regional_nodes : {
      name    = name
      address = {
        ip   = node.private_ip
        port = node.port
      }
    }
  ]
}