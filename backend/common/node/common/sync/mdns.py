from dataclasses import dataclass

@dataclass
class DnsEntry:
    name: str
    ip: str
    port: int