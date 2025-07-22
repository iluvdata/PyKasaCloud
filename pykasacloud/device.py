"""Base class for Kasa devices."""

from abc import abstractmethod, ABC

from enum import Flag, auto
from typing import Any

from pykasacloud import KasaCloudError
from pykasacloud.api import KasaCloudApi


class Capabilities(Flag):
    """Capabilities of Kasa devices."""
    NONE = 0
    DIMMABLE = auto()
    NETINFO = auto()
    COLOR = auto()
    COLOR_TEMP = auto()


class KasaDevice(ABC):
    """Base class for Kasa devices."""

    info: dict[str, Any] = {}
    net_info: dict[str, Any] = {}

    def __init__(self, kasacloudapi: KasaCloudApi, data: dict[str, Any]):
        self.data: dict[str, Any] = data
        self._kasacloudapi: KasaCloudApi = kasacloudapi
        if not self.data.get("deviceId"):
            raise KasaCloudError("Invalid device")
        self.device_id: str = self.data["deviceId"]

    async def capabilities(self) -> Capabilities:
        """Get the capabilities of the device."""

        features: Capabilities = Capabilities.NONE
        if self.data["deviceModel"] != "HS100(US)" or (
            self.data["deviceModel"] == "HS100(US)"
            and self.data["deviceHwVer"] != "1.0"
        ):
            features |= Capabilities.NETINFO
        if self.data["deviceType"] == "IOT.SMARTBULB":
            await self._check_info()
            if self.info["is_dimmable"]:
                features |= Capabilities.DIMMABLE
            if self.info["is_color"]:
                features |= Capabilities.COLOR
            if self.info["is_variable_color_temp"]:
                features |= Capabilities.COLOR_TEMP
        return features

    async def _async_passthrough_request(
        self, request_type: str, subrequest_type: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a passthrough request to the device."""

        return await self._kasacloudapi.async_passthrough_request(
            self.device_id,
            request_type,
            subrequest_type,
            request=request,
            url=self.data["appServerUrl"],
        )

    @abstractmethod
    async def turn_on(self) -> None:
        """Turn the device on or off."""
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the device on or off."""
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    async def toggle(self) -> None:
        """Toggle the device state."""
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def online(self) -> bool:
        """Check if the device is online."""
        return bool(self.data.get("status"))

    async def _check_info(self) -> None:
        if not self.info:
            await self._get_info()

    async def _get_info(self) -> dict[str, Any]:
        if not self.online:
            raise KasaCloudError("Device must be online")
        self.info = await self._async_passthrough_request("system", "get_sysinfo", {})
        return self.info

    async def _get_netif(self) -> None:
        if Capabilities.NETINFO not in await self.capabilities():
            raise KasaCloudError("Not supported by this device")
        if not self.online:
            raise KasaCloudError("Device must be online")
        self.net_info = await self._async_passthrough_request(
            "netif", "get_stainfo", {}
        )

    @abstractmethod
    async def is_on(self) -> bool:
        """Check if the device is on."""
        raise NotImplementedError("Subclasses must implement this method")
