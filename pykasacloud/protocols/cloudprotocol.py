"""Cloud Protocol."""

import logging
from pprint import pformat as pf
from typing import Any, cast

from kasa import IotProtocol
from kasa.json import loads as json_loads
from kasa.protocols.iotprotocol import REDACTORS
from kasa.protocols.protocol import redact_data
from yarl import URL

from pykasacloud.transports import CloudTransport

_LOGGER = logging.getLogger(__name__)


class CloudProtocol(IotProtocol):
    """Cloud Protocol Class."""

    _device_id: str | None = None
    _url: URL | None = None

    def attach_device(self, device_dict: dict[str, Any]) -> None:
        """Update the appServerUrl (from a device)."""
        self._url = URL(device_dict["appServerUrl"])
        self._device_id = device_dict["deviceId"]

    async def _execute_query(self, request: str, retry_count: int) -> dict:
        debug_enabled = _LOGGER.isEnabledFor(logging.DEBUG)

        if debug_enabled:
            _LOGGER.debug(
                "%s >> %s",
                self._host,
                request,
            )
        transport: CloudTransport = cast(CloudTransport, self._transport)

        resp = await transport.send_request(
            json_loads(request), self._device_id, self._url
        )

        if debug_enabled:
            data = redact_data(resp, REDACTORS) if self._redact_data else resp
            _LOGGER.debug(
                "%s << %s",
                self._host,
                pf(data),
            )
        return resp
