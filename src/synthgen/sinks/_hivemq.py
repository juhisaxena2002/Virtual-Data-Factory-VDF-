from __future__ import annotations
import json
import ssl
import paho.mqtt.client as mqtt
from ..types import Record

class HiveMQSink:
    def __init__(
        self,
        host: str,
        port: int = 8883,
        username: str = "",
        password: str = "",
        topic: str = "synthgen/stream",
        qos: int = 1,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._topic = topic
        self._qos = qos
        self._client: mqtt.Client | None = None

    def open(self) -> None:
        self._client = mqtt.Client(
            client_id="synthgen",
            protocol=mqtt.MQTTv5,
        )
        self._client.username_pw_set(self._username, self._password)
        # TLS required for HiveMQ Cloud port 8883
        self._client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def write(self, record: Record) -> None:
        if self._client is None:
            raise RuntimeError("HiveMQSink not opened. Call open() first.")
        payload = json.dumps(record, default=str)
        self._client.publish(self._topic, payload, qos=self._qos)

    def close(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
