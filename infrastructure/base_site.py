from abc import ABC
import requests

class base_site(ABC):
    def __init__(self, name, region_name):
        """
        name is the unique ID for the site (in case more than 1)
        resource_key defines what kind of site
        initial_value initialises the value
        region_name tells us who this belongs to
        """
        self.name = name
        self.region_name = region_name

    @property
    def get_type(self):
        return self.resource_type
    
    def update_resource(self, new_value):
        self.resource_value = new_value

    # POST the heartbeat containing all infrastructure info to the regional address in charge
    def report(self):
        data = {
            "name":self.name,
            "region_name":self.region_name,
            "resource_type":self.resource_type,
            "resource_value":self.resource_value
        }

        # this needs to be updated when the hook up is ready.
        response = requests.post("INSERT REGIONAL ADDRESS?", json=data)

        # for logging purposes?
        print(f"Heartbeat sent: {response.status_code}")
