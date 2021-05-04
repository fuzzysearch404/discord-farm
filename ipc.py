import json
import asyncio
import aioredis
import jsonpickle
from datetime import date, datetime

from core.cluster import Cluster
from core.ipc_message import IPCMessage


class IPC:
    def __init__(self) -> None:
        self._loop = asyncio.get_event_loop()
        
        self._config = self._load_config()

        ipc_config = self._config['ipc']
        self.ipc_name = ipc_config['ipc-author']
        self.cluster_inactive_timeout = ipc_config['cluster-inactive-timeout']
        self.cluster_check_delay = ipc_config['cluster-check-delay']
        self.cluster_update_delay = ipc_config['cluster-update-delay']

        redis_channels = self._config['redis']['channels']
        self.global_channel = redis_channels['global-channel-name']
        self.cluster_channels = redis_channels['cluster-channel-prefix'] + "*"

        self.active_clusters = []
        self.total_guild_count = 0

        self.redis = self._connect_redis()
        self.redis_pubsub = self.redis.pubsub()

    def start(self) -> None:
        self._loop.create_task(self._main_loop())

        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            self._loop.run_until_complete(self.stop())

    async def stop(self) -> None:
        await self._unregister_redis_channels()

        self._loop.stop()

    def _load_config(self) -> dict:
        with open("config.json") as file:
            return json.load(file)

    def _connect_redis(self) -> aioredis.Redis:
        pool = aioredis.ConnectionPool.from_url(
            self._config['redis']['auth']['host'],
            password=self._config['redis']['auth']['password']
        )

        return aioredis.Redis(connection_pool=pool)

    async def _register_redis_channels(self) -> None:
        await self.redis_pubsub.subscribe(self.global_channel)
        await self.redis_pubsub.psubscribe(self.cluster_channels)

    async def _unregister_redis_channels(self) -> None:
        await self.redis_pubsub.unsubscribe(self.global_channel)
        await self.redis_pubsub.punsubscribe(self.cluster_channels)

    async def _redis_event_handler(self) -> None:
        async for message in self.redis_pubsub.listen():
            if message['type'] != 'message' and message['type'] != 'pmessage':
                continue

            try:
                ipc_message = jsonpickle.decode(message['data'])
            except TypeError:
                continue
            
            if ipc_message.author == self.ipc_name:
                continue

            if ipc_message.action == "ping":
                self._update_cluster_status(ipc_message)

    async def _main_loop(self) -> None:
        await self._register_redis_channels()
        self._loop.create_task(self._redis_event_handler())
        self._loop.create_task(self._cluster_check_task())
        self._loop.create_task(self._cluster_update_task())
  
        while not self._loop.is_closed():
            cluster = Cluster(
                name="bot1",
                latencies=[1, 2, 3],
                guild_count=22,
                last_ping=datetime.now()
            )

            message = IPCMessage(
                author="bot",
                action="ping",
                data=jsonpickle.encode(cluster)
            )

            print("publish")
            await self.redis.publish("cluster-1", jsonpickle.encode(message))
            await asyncio.sleep(10)
            print(self.active_clusters)

    def _update_cluster_status(self, message: IPCMessage) -> None:
        cluster = jsonpickle.decode(message.data)
        
        for saved_cluster in self.active_clusters:
            if cluster.name == saved_cluster.name:
                self.active_clusters.remove(saved_cluster)
                break
        
        self.active_clusters.append(cluster)

    async def _cluster_check_task(self) -> None:
        while not self._loop.is_closed():
            await asyncio.sleep(self.cluster_check_delay)

            guild_count = 0
            for cluster in self.active_clusters:
                delta_time = datetime.now() - cluster.last_ping
                
                if delta_time.total_seconds() >= self.cluster_inactive_timeout:
                    self.active_clusters.remove(cluster)

                    continue

                guild_count += cluster.guild_count

            self.total_guild_count = guild_count

    async def _cluster_update_task(self) -> None:
        while not self._loop.is_closed():
            await asyncio.sleep(self.cluster_update_delay)

            message = IPCMessage(
                author=self.ipc_name,
                action="ping",
                data=jsonpickle.encode(self.active_clusters)
            )

            await self.redis.publish(
                self.global_channel,
                jsonpickle.encode(message)
            )

if __name__ == "__main__":
    ipc = IPC()
    ipc.start()
