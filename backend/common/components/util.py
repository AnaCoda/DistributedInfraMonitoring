from pydantic import BaseModel

class NetworkAddress(BaseModel):
    ip: str
    port: int

    def to_tuple(self) -> tuple[str, int]:
        return (self.ip, self.port)

class NetworkUrl(BaseModel):
    url: str

class NetworkEntry(BaseModel):
    name: str
    address: NetworkAddress | NetworkUrl

    