from .base_site import base_site

class powerplant(base_site):

    # Pass up to base_site then define self as a powerplant
    def __init__(self, name, region_name):
        super().__init__(name, region_name)
        self.resource_type = "Powerplant"
        self.resource_value = "Stable"              # is power stable, semi-stable, unstable or gone
