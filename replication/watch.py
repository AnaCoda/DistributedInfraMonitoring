import argparse
import os
import time
from typing import List
import paramiko


from replication.common import UpdateTarget, _error, _success, get_terraform_files





if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--key', required=True)
        parser.add_argument('--service', required=True)
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

        targets: List[UpdateTarget] = get_terraform_files()
        service = filter(lambda x : x.name == args.service, targets).__next__()
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=service.hostname,
            username='ec2-user',
            key_filename=args.key
        )

        stdin, stdout, stderr = client.exec_command(f'sudo journalctl -u {service.service} -n 100000 -f -o cat')
        # while True:
        #     line = stdout.readline()
        #     print(f'{line}')

        channel = stdout.channel
        try:
            while True:
                if channel.recv_ready():
                    data = channel.recv(4096).decode(errors="replace")
                    print(data, end="", flush=True)
                elif channel.exit_status_ready():
                    break
                else:
                    time.sleep(0.1)
            # for line in iter(stdout.readline, ""):
                # print(line, end='')
        except KeyboardInterrupt:
            print(f'Keybaord')
        # _success('service', f'Found service with details: {service}')


        _success('redeploy', 'Finished redeploying infrastructure.')
    except KeyboardInterrupt as e:
        print(f'KEYBARD')

    except Exception as e:
        _error(str(e))
        exit(1)