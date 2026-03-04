from .base_site import base_site

class fuel_depot(base_site):

    # Pass up to base_site then define self as a fuel depot
    def __init__(self, name, region_name):
        super().__init__(name, region_name)
        self.resource_type = "Fuel Depot"
        self.resource_value = 100           # % of fuel for the locale
