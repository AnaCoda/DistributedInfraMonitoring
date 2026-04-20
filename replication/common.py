from dataclasses import dataclass
from json import loads
import subprocess
from typing import List

from colorama import Fore, Style

def _error(msg: str):
    print(f'{Fore.RED}{Style.BRIGHT}[ERROR]{Style.NORMAL} {msg}{Fore.RESET}')


def _success(header: str, msg: str):
    print(f'{Fore.GREEN}{Style.BRIGHT}>>{Style.NORMAL} {Fore.YELLOW}({header}){Fore.RESET} {msg}')


@dataclass
class UpdateTarget:
    name: str
    hostname: str
    service: str

def harvest_terraform_ips(data: dict, group: str, service: str) -> list[UpdateTarget]:
    output = []
    for name, ip in data[group]['value'].items():
        output.append(UpdateTarget(
            hostname=ip,
            name=name,
            service=service
        ))
    return output

def get_terraform_files(
    
) -> List[UpdateTarget]:
    
    output = []
    out = subprocess.run(['terraform', 'output', '-json'], capture_output=True, text=True, cwd='Terraform/')
    data = loads(out.stdout)

    output += harvest_terraform_ips(data, 'infra_public_ips', 'distinfra-infra.service')
    output += harvest_terraform_ips(data, 'regional_public_ips', 'distinfra-regional.service')
    output += harvest_terraform_ips(data, 'capital_public_ips', 'distinfra-capital.service')    

    _success('Terraform', f'Identified {len(output)} update targets')
    return output
