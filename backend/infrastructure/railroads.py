from .base_site import base_site

class railroads(base_site):

    # Pass up to base_site then define self as a railroad system
    def __init__(self, name, region_name):
        super().__init__(name, region_name)
        self.resource_type = "Railroad"
        self.resource_value = "Operational"         # operational, semi-operational, or non-operational
