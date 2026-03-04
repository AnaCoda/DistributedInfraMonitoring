from .base_site import base_site

class hospital(base_site):

    # Pass up to base_site then define self as a hospital
    def __init__(self, name, region_name):
        super().__init__(name, region_name)
        self.resource_type = "Hospital"
        self.resource_value = 100               # % of hospital beds for the populace
