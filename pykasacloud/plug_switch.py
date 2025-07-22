"""Kasa Plug class."""

import re

from typing import Any

from .device import KasaDevice
from .api import KasaCloudApi


class KasaPlug(KasaDevice):
    """Kasa Plug class."""

    def __init__(self, api: KasaCloudApi, data: dict[str, Any]) -> None:
        """Initialize the Kasa Plug."""
        if not isinstance(self, KasaSwitch) and not (
            data.get("deviceType") == "IOT.SMARTPLUGSWITCH"
            and re.search("Plug", str(data.get("deviceName"))) is not None
        ):
            raise ValueError("Invalid device type for Kasa Plug")
        super().__init__(api, data)

    async def is_on(self) -> bool:
        """Check if the plug is on."""
        # Ensure the device info is up to date
        await self._get_info()
        if self.info.get("relay_state") is not None:
            return self.info["relay_state"] == 1
        return self.data.get("status") == 1

    async def turn_on(self) -> None:
        """Turn the plug on."""
        await self._async_passthrough_request("system", "set_relay_state", {"state": 1})
        self.info["relay_state"] = 1

    async def turn_off(self) -> None:
        """Turn the plug on."""
        await self._async_passthrough_request("system", "set_relay_state", {"state": 0})
        self.info["relay_state"] = 0

    async def toggle(self) -> None:
        """Turn the plug on."""
        if await self.is_on():
            await self.turn_off()
        else:
            await self.turn_on()


class KasaSwitch(KasaPlug):
    """Kasa Switch class."""

    def __init__(self, api: KasaCloudApi, data: dict[str, Any]) -> None:
        """Initialize the Kasa Plug."""
        if not (
            data.get("deviceType") == "IOT.SMARTPLUGSWITCH"
            and re.search("Switch", str(data.get("deviceName"))) is not None
        ):
            raise ValueError("Invalid device type for Kasa Switch")
        super().__init__(api, data)
