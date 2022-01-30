import os
import time
import json
import aiohttp
import asyncio
import logging
import multiprocessing
import signal

from bot.bot import BotClient
from core import static


LOG_FORMATTER = logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s")
log = logging.getLogger("Launcher")
log.setLevel(logging.DEBUG)
hdlr = logging.StreamHandler()
hdlr.setFormatter(LOG_FORMATTER)
fhdlr = logging.FileHandler("./logs/launcher.log", encoding="utf-8")
fhdlr.setFormatter(LOG_FORMATTER)
log.handlers = [hdlr, fhdlr]


CLUSTER_NAMES = (
    "Apple", "Banana", "Broccoli", "Cabbage",
    "Cacao", "Cherry", "Coconut", "Corn",
    "Cotton", "Cranberry", "Cucumber", "Eggplant",
    "Garlic", "Ginger", "Grape", "Hazelnut",
    "Indigo", "Jasmine", "Lettuce", "Lime",
    "Mango", "Mushroom", "Nectarine", "Olive"
)
NAMES = iter(CLUSTER_NAMES)


class Launcher:
    def __init__(self, loop) -> None:
        log.info("Launching...")
        self.config = self._load_config()

        self.cluster_queue = []
        self.clusters = []

        self.fut = None
        self.loop = loop
        self.alive = True

        self.keep_alive = None
        self.init_time = time.perf_counter()

    def _load_config(self) -> dict:
        with open(static.CONFIG_PATH, "r") as file:
            return json.load(file)

    async def get_shard_count(self) -> int:
        headers = {
            "Authorization": "Bot " + self.config['bot']['discord-token'],
            "User-Agent": f"Discord Farm Bot {self.config['bot']['version']} ({static.GIT_REPO})"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/gateway/bot", headers=headers) as resp:
                json_body = await resp.json()

        if resp.status != 200:
            log.critical(f"Discord returned: {resp.status}")
            self.loop.stop()

        log.info(
            f"Successfully got shard count of {json_body['shards']} "
            f"({resp.status}, {resp.reason})"
        )
        return json_body['shards']

    def start(self) -> None:
        self.fut = asyncio.ensure_future(self.startup(), loop=self.loop)

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.shutdown())
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        self.loop.stop()

    def task_complete(self, task) -> None:
        if task.exception():
            task.print_stack()
            self.keep_alive = self.loop.create_task(self.rebooter())
            self.keep_alive.add_done_callback(self.task_complete)

    async def startup(self) -> None:
        shards = list(range(await self.get_shard_count()))
        size = [shards[x:x + 4] for x in range(0, len(shards), 4)]
        log.info(f"Preparing {len(size)} clusters")

        for shard_ids in size:
            self.cluster_queue.append(Cluster(self, next(NAMES), shard_ids, len(shards)))

        await self.start_cluster()

        self.keep_alive = self.loop.create_task(self.rebooter())
        self.keep_alive.add_done_callback(self.task_complete)
        log.info(f"Startup completed in {time.perf_counter() - self.init_time}s")

    async def shutdown(self) -> None:
        log.info("Shutting down clusters")
        self.alive = False

        if self.keep_alive:
            self.keep_alive.cancel()

        for cluster in self.clusters:
            cluster.stop()

        self.cleanup()

    async def rebooter(self) -> None:
        while self.alive:
            if not self.clusters:
                log.warning("All clusters appear to be dead")
                asyncio.ensure_future(self.shutdown())

            to_remove = []
            for cluster in self.clusters:
                if not cluster.process.is_alive():
                    if cluster.process.exitcode != 0:
                        # ignore safe exits
                        log.info(
                            f"Cluster#{cluster.name} exited "
                            f"with code {cluster.process.exitcode}"
                        )
                        log.info(f"Restarting cluster#{cluster.name}")

                        await cluster.start()
                    else:
                        log.info(f"Cluster#{cluster.name} found dead")
                        to_remove.append(cluster)
                        cluster.stop()  # ensure stopped

            for rem in to_remove:
                self.clusters.remove(rem)

            await asyncio.sleep(5)

    async def start_cluster(self) -> None:
        if self.cluster_queue:
            cluster = self.cluster_queue.pop(0)
            log.info(f"Starting Cluster#{cluster.name}")
            await cluster.start()
            self.clusters.append(cluster)

            log.info("Done!")
            await self.start_cluster()
        else:
            log.info("All clusters launched")


class Cluster:
    def __init__(self, launcher, name, shard_ids, max_shards):
        self.launcher = launcher
        self.process = None
        self.kwargs = dict(
            shard_ids=shard_ids,
            shard_count=max_shards,
            cluster_name=name,
            config=launcher.config
        )
        self.name = name

        self.log = logging.getLogger(f"Cluster#{name}")
        self.log.setLevel(logging.DEBUG)
        hdlr = logging.StreamHandler()
        hdlr.setFormatter(LOG_FORMATTER)
        fhdlr = logging.FileHandler("./logs/cluster-Launcher.log", encoding="utf-8")
        fhdlr.setFormatter(LOG_FORMATTER)
        self.log.handlers = [hdlr, fhdlr]
        self.log.info(f"Initialized with shard ids {shard_ids}, total shards {max_shards}")

    def wait_close(self) -> None:
        self.process.join()

    async def start(self, *, force=False) -> bool:
        if self.process and self.process.is_alive():
            if not force:
                self.log.warning(
                    "Start called with already running cluster, pass `force=True` to override"
                )
                return False

            self.log.info("Terminating existing process")
            self.process.terminate()
            self.process.close()

        stdout, stdin = multiprocessing.Pipe()
        kwargs = self.kwargs
        kwargs['pipe'] = stdin

        self.process = multiprocessing.Process(target=BotClient, kwargs=kwargs, daemon=True)
        self.process.start()
        self.log.info(f"Process started with PID {self.process.pid}")

        if await self.launcher.loop.run_in_executor(None, stdout.recv) == 1:
            stdout.close()
            self.log.info("Process started successfully")

        return True

    def stop(self, sign=signal.SIGINT) -> None:
        self.log.info(f"Shutting down with signal {sign!r}")
        try:
            os.kill(self.process.pid, sign)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    Launcher(loop).start()
