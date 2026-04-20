import asyncio
import http
import os
import signal

from websockets.asyncio.server import serve

PORT = int(os.environ.get("PORT", "8080"))

async def echo(websocket):
    async for message in websocket:
        await websocket.send(message)

def health_check(connection, request):
    if request.path == "/healthz":
        return connection.respond(http.HTTPStatus.OK, "OK\n")

async def main():
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)

    print(f'LISTENING {os.environ.get("INSTANCE_NAME", "unknown")} on 0.0.0.0:{PORT}', flush=True)

    async with serve(
        echo,
        host="",
        port=PORT,
        process_request=health_check,
    ):
        await stop

if __name__ == "__main__":
    asyncio.run(main())