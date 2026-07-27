from aiokafka import AIOKafkaProducer

from app.core.config import Settings


class KafkaProducerManager:
    def __init__(self, settings: Settings) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id=settings.kafka_client_id,
        )
        self.is_connected = False

    async def start(self) -> None:
        await self._producer.start()
        self.is_connected = True

    async def stop(self) -> None:
        try:
            await self._producer.stop()
        finally:
            self.is_connected = False
