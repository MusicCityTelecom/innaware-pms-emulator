"""Own accepted sockets until asyncio has transferred them to stream transports."""
from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Callable


class OwnedTcpListener:
    def __init__(self) -> None:
        self.sockets: list[socket.socket] = []
        self._tasks: list[asyncio.Task] = []
        self._closed = False

    @classmethod
    async def start(cls, connected: Callable, host: str, port: int) -> OwnedTcpListener:
        listener = cls()
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(
            host or None, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE,
        )
        try:
            for family, kind, protocol, _, address in set(addresses):
                sock = socket.socket(family, kind, protocol)
                listener.sockets.append(sock)
                if os.name != "nt":
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if family == socket.AF_INET6:
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                sock.setblocking(False)
                sock.bind(address)
                sock.listen(100)  # Preserve asyncio.start_server's default backlog.
            listener._tasks = [
                asyncio.create_task(listener._accept(sock, connected))
                for sock in listener.sockets
            ]
            return listener
        except BaseException:
            listener.close()
            await listener.wait_closed()
            raise

    async def _accept(self, sock: socket.socket, connected: Callable) -> None:
        loop = asyncio.get_running_loop()
        accepted = None
        try:
            while not self._closed:
                accepted, _ = await loop.sock_accept(sock)
                reader = asyncio.StreamReader()
                protocol = asyncio.StreamReaderProtocol(reader, connected)
                # The accept task owns this socket until transport creation has
                # completed. Stop cancels/awaits this task before returning, so
                # a queued accept cannot escape shutdown before callback tracking.
                await loop.connect_accepted_socket(lambda: protocol, accepted)
                accepted = None  # The stream transport now owns the socket.
        finally:
            if accepted is not None:
                accepted.close()

    def close(self) -> None:
        self._closed = True
        for task in self._tasks:
            task.cancel()
        for sock in self.sockets:
            sock.close()

    async def wait_closed(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
