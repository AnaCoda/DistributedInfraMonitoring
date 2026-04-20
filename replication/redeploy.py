import argparse
from ast import arg
from dataclasses import dataclass
from json import load, loads
import os
import time
from typing import List, Optional, Tuple
import paramiko

from colorama import Fore, Style
import paramiko.client
import subprocess

from replication.common import _error, _success, get_terraform_files



def run_command(
    client: paramiko.SSHClient,
    command: str,
    directory: Optional[str] = None,
    show_output: bool = False
):
    if directory is not None:
        command = f'cd {directory} && {command}'
    stdin, stdout, stderr = client.exec_command(command)

    # print(stderr.read().decode())
    # print(stdout.read().decode())


    exit_status = stdout.channel.recv_exit_status()

    if exit_status == 0:
        _success('command', f'Executed: {command}')
        if show_output:
            print(f'{Fore.LIGHTBLACK_EX}{stdout.read().decode()}{Fore.RESET}')
        return
    else:
        raise RuntimeError(f'(error during command "{command}") {stderr.read().decode().strip()}')
        # print(f"Failed with exit code {exit_status}")

def redeploy_sequence(
    hostname: str,
    username: str,
    keyfile: str,
    app_dir: str,
    git_branch: str,
    target_service: str
):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=hostname,
            username=username,
            key_filename=keyfile,
            port=22,
            banner_timeout=30,
            auth_timeout=30,
            look_for_keys=False,
            allow_agent=False
        )
        print(f'connected')
        
        run_command(client, 'git fetch origin', app_dir)
        run_command(client, f'git checkout {git_branch}', app_dir)
        run_command(client, 'git pull --ff-only', app_dir)
        run_command(client, f"sudo systemctl restart '{target_service}'")
        run_command(client, f"sudo systemctl --no-pager --full status '{target_service}' | head -n 20", show_output=True)
    except Exception as e:
        _error(str(e))
        raise
    finally:
        client.close()
        # time.sleep(10)



if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--key', required=True)
        parser.add_argument('--autocommit', action='store_true', default=False)
        args = parser.parse_args()

        if not os.path.exists('Terraform'):
            # Let us make sure that the Terraform instance actually
            # is there.
            _error('Could not find directory relative to path: \'Terraform/\'')
            exit(1)

        

        if not os.path.exists(args.key):
            # Let us make sure that the keyfile actually exists.
            _error(f'Could not find keyfile at path: {args.key}')
            exit(1)

        # if args.autocommit:
            # subprocess.run(['git', 'add . && git commit -m'])

        targets = get_terraform_files()
        for idx in range(len(targets)):
            print(f'{Fore.CYAN}({idx + 1}/{len(targets)}) Starting @ {targets[idx].name} (ip={targets[idx].hostname})')
            redeploy_sequence(
                hostname=targets[idx].hostname,
                app_dir='/opt/DistributedInfraMonitoring',
                git_branch='feature/backend-port',
                keyfile=args.key,
                target_service=targets[idx].service,
                username='ec2-user'
            )
        _success('redeploy', 'Finished redeploying infrastructure.')
    except Exception as e:
        _error(str(e))
        exit(1)