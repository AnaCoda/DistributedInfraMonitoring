import asyncio
import argparse
from json import dumps, loads
from colorama import Fore
import websockets

from backend.common.layers.networking.networking_layer import MessagePackingResult




async def client():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', help='The IP address to connect to', required=True)
    parser.add_argument('--name', help='The name to use for connection.', required=True)
    parser.add_argument('--route', help='The route to connect to.', required=True)
    parser.add_argument('--body', help='JSON payload', default='{}')

    # parser.add_argument()
    args = parser.parse_args()

    uri = f"ws://{args.ip}"

    async with websockets.connect(uri) as websocket:
        await websocket.send(dumps({ "name": args.name }))

        # recv = await websocket.recv()
        # console.

        response = loads(await websocket.recv())
        if 'status' in response and 'name' in response:
            print(f'Connection {Fore.GREEN}SUCCESS{Fore.RESET}')
            print(f'  Name:\t\t{Fore.YELLOW}{args.name}{Fore.RESET}')
            print(f'  Target:\t{Fore.YELLOW}{response["name"]}{Fore.RESET}')
            print(f'  Status:\t{Fore.YELLOW}{response["status"]}{Fore.RESET}')
        else:
            print(f'Connection {Fore.RED}FAILED{Fore.RESET}')
            print(f'  Msg:\t{Fore.RED}{response}{Fore.RESET}')
            return
    
        packed = MessagePackingResult.pack_msg(route=args.route, body=loads(args.body), fireforget=False)
        print(f'Packed: {Fore.LIGHTBLACK_EX}{packed}{Fore.RESET}')

        await websocket.send(dumps(packed.message))

        response = dumps(loads(await websocket.recv()), indent=4)

        print(f'Response:{Fore.CYAN}\n{response}{Fore.RESET}')


        # print(f'Response: {Fore.LIGHTBLACK_EX}{await websocket.recv()}{Fore.}')

        # print("Received:", response)

asyncio.run(client())
