"""Shutdown owns even a connection accepted before transport registration."""
import asyncio
import socket

from innaware_pms_emulator.models import InterfaceConfig
from innaware_pms_emulator.sessions import InterfaceManager


def test_selector_stop_during_accepted_transport_registration():
    async def exercise():
        loop = asyncio.get_running_loop()
        queued = asyncio.Event()
        release = asyncio.Event()
        errors = []
        trace = []
        original_factory = loop.get_task_factory()
        original_handler = loop.get_exception_handler()

        async def deferred(coro):
            trace.append("accepted-before-transport")
            queued.set()
            await release.wait()
            return await coro

        def factory(loop, coro, **kwargs):
            if getattr(getattr(coro, "cr_code", None), "co_name", None) == "_accept_connection2":
                coro = deferred(coro)
            return asyncio.Task(coro, loop=loop, **kwargs)

        loop.set_task_factory(factory)
        loop.set_exception_handler(lambda _loop, context: errors.append(type(context.get("exception")).__name__))
        manager = InterfaceManager()
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        runtime = await manager.create(InterfaceConfig(
            name="accept-shutdown", purpose="pms", protocol="FIAS",
            transport="tcp_server", bind_host="127.0.0.1", port=port,
        ))
        reader = writer = None
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await asyncio.wait_for(queued.wait(), 1)
            trace.append("stop")
            await manager.stop(runtime.config.name)
            release.set()
            try:
                result = await asyncio.wait_for(reader.read(), 1)
            except TimeoutError:
                result = "timeout"
            trace.append("stopped")
            assert (result, errors) == (b"", []), (trace, result, errors)
            assert runtime.state == "stopped"
            assert not runtime.clients and not runtime.client_tasks
        finally:
            release.set()
            await manager.stop(runtime.config.name)
            if writer:
                writer.close()
                await writer.wait_closed()
            loop.set_task_factory(original_factory)
            loop.set_exception_handler(original_handler)

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())
