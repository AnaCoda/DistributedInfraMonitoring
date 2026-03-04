from .base_site import base_site

class water_treatment_plant(base_site):

    # Pass up to base_site then define self as a water_treatment_plant
    def __init__(self, name, region_name):
        super().__init__(name, region_name)
        self.resource_type = "Water Treatment Plant"
        self.resource_value = 100           # % of water needed for locale being produced
