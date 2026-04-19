locals {
  capital_nodes = {
    "rm-1" = { private_ip = "10.42.1.10", port = 4001 }
    "rm-2" = { private_ip = "10.42.1.11", port = 4002 }
    "rm-3" = { private_ip = "10.42.1.12", port = 4003 }
  }

  regional_nodes = {
    # "Carstairs-r1" = {
    #   private_ip  = "10.42.1.20"
    #   port        = 3051
    #   region_name = "Carstairs"
    #   replica_set = ["Carstairs-r1", "Carstairs-r2"]
    # }
    # "Carstairs-r2" = {
    #   private_ip  = "10.42.1.21"
    #   port        = 3052
    #   region_name = "Carstairs"
    #   replica_set = ["Carstairs-r1", "Carstairs-r2"]
    # }

    # "Airdrie-r1" = {
    #   private_ip  = "10.42.1.30"
    #   port        = 3061
    #   region_name = "Airdrie"
    #   replica_set = ["Airdrie-r1", "Airdrie-r2"]
    # }
    # "Airdrie-r2" = {
    #   private_ip  = "10.42.1.31"
    #   port        = 3062
    #   region_name = "Airdrie"
    #   replica_set = ["Airdrie-r1", "Airdrie-r2"]
    # }

    # "Cochrane-r1" = {
    #   private_ip  = "10.42.1.40"
    #   port        = 3071
    #   region_name = "Cochrane"
    #   replica_set = ["Cochrane-r1", "Cochrane-r2"]
    # }
    # "Cochrane-r2" = {
    #   private_ip  = "10.42.1.41"
    #   port        = 3072
    #   region_name = "Cochrane"
    #   replica_set = ["Cochrane-r1", "Cochrane-r2"]
    # }
  }

  infra_nodes = {
    # "Hospital-1" = {
    #   private_ip  = "10.42.1.50"
    #   node_type   = "hospital"
    #   region_name = "Carstairs"
    #   regions     = ["Carstairs-r1", "Carstairs-r2"]
    # }
    # "Powerplant-1" = {
    #   private_ip  = "10.42.1.51"
    #   node_type   = "powerplant"
    #   region_name = "Carstairs"
    #   regions     = ["Carstairs-r1", "Carstairs-r2"]
    # }
    # "WaterTreatment-1" = {
    #   private_ip  = "10.42.1.52"
    #   node_type   = "watertreatmentplant"
    #   region_name = "Carstairs"
    #   regions     = ["Carstairs-r1", "Carstairs-r2"]
    # }
    # "FuelDepot-1" = {
    #   private_ip  = "10.42.1.53"
    #   node_type   = "fueldepot"
    #   region_name = "Carstairs"
    #   regions     = ["Carstairs-r1", "Carstairs-r2"]
    # }

    # "Hospital-2" = {
    #   private_ip  = "10.42.1.60"
    #   node_type   = "hospital"
    #   region_name = "Airdrie"
    #   regions     = ["Airdrie-r1", "Airdrie-r2"]
    # }
    # "Powerplant-2" = {
    #   private_ip  = "10.42.1.61"
    #   node_type   = "powerplant"
    #   region_name = "Airdrie"
    #   regions     = ["Airdrie-r1", "Airdrie-r2"]
    # }
    # "WaterTreatment-2" = {
    #   private_ip  = "10.42.1.62"
    #   node_type   = "watertreatmentplant"
    #   region_name = "Airdrie"
    #   regions     = ["Airdrie-r1", "Airdrie-r2"]
    # }
    # "FuelDepot-2" = {
    #   private_ip  = "10.42.1.63"
    #   node_type   = "fueldepot"
    #   region_name = "Airdrie"
    #   regions     = ["Airdrie-r1", "Airdrie-r2"]
    # }

    # "Hospital-3" = {
    #   private_ip  = "10.42.1.70"
    #   node_type   = "hospital"
    #   region_name = "Cochrane"
    #   regions     = ["Cochrane-r1", "Cochrane-r2"]
    # }
    # "Powerplant-3" = {
    #   private_ip  = "10.42.1.71"
    #   node_type   = "powerplant"
    #   region_name = "Cochrane"
    #   regions     = ["Cochrane-r1", "Cochrane-r2"]
    # }
    # "WaterTreatment-3" = {
    #   private_ip  = "10.42.1.72"
    #   node_type   = "watertreatmentplant"
    #   region_name = "Cochrane"
    #   regions     = ["Cochrane-r1", "Cochrane-r2"]
    # }
    # "FuelDepot-3" = {
    #   private_ip  = "10.42.1.73"
    #   node_type   = "fueldepot"
    #   region_name = "Cochrane"
    #   regions     = ["Cochrane-r1", "Cochrane-r2"]
    # }
  }

  capital_peers = [
    for name, node in local.capital_nodes : {
      name = name
      address = {
        ip   = node.private_ip
        port = node.port
      }
    }
  ]

  regional_peers_by_node = {
    for name, node in local.regional_nodes :
    name => [
      for peer_name in node.replica_set : {
        name = peer_name
        address = {
          ip   = local.regional_nodes[peer_name].private_ip
          port = local.regional_nodes[peer_name].port
        }
      }
    ]
  }

  infra_regions_by_node = {
    for name, node in local.infra_nodes :
    name => [
      for region_name in node.regions : {
        name = region_name
        address = {
          ip   = local.regional_nodes[region_name].private_ip
          port = local.regional_nodes[region_name].port
        }
      }
    ]
  }
}