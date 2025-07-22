"""Kasa Cloud API wrapper for managing devices."""

import json
import re

from typing import Any

from pykasacloud import KasaCloudError
from pykasacloud.api import KasaCloudApi
from pykasacloud.const import API_URL
from pykasacloud.device import KasaDevice
from pykasacloud.plug_switch import KasaPlug, KasaSwitch
from pykasacloud.light import KasaLight


class PyKasaCloud:
    """Kasa Cloud API wrapper for managing devices."""

    def __init__(
        self, kasacloudapi: KasaCloudApi, file_cache: str | None = None
    ) -> None:
        self._kasacloudapi: KasaCloudApi = kasacloudapi
        self._cache: dict[str, KasaDevice] = {}
        self._file_cache = file_cache

    async def async_get_devices(self) -> dict[str, Any]:
        """Get all devices from the Kasa Cloud API associated with account.
        If a file cache is provided, it will be used to load/save the devices."""

        if not self._cache:
            if self._file_cache:
                try:
                    with open(self._file_cache, "r", encoding="utf-8") as f:
                        devices = json.load(f)
                        f.close()
                        if (
                            devices
                            and devices.get("deviceList")
                            and devices["deviceList"][0].get("accountApiUrl")
                        ):
                            self._kasacloudapi.update_url(
                                devices["deviceList"][0].get("accountApiUrl")
                            )
                        self._cache = {
                            device["deviceId"]: self._async_get_device(device)
                            for device in devices["deviceList"]
                        }
                        return self._cache
                except FileNotFoundError:
                    pass
            await self.async_refresh_devices()
        return self._cache

    async def async_refresh_devices(self) -> None:
        """Refresh the device list from the Kasa Cloud API."""

        payload: dict[str, Any] = {"method": "getDeviceList"}
        devices = await self._kasacloudapi.async_request(payload=payload, url=API_URL)

        # Get the account specific api url
        if (
            devices
            and devices.get("deviceList")
            and devices["deviceList"][0].get("accountApiUrl")
        ):
            self._kasacloudapi.update_url(devices["deviceList"][0].get("accountApiUrl"))

        self._cache = {
            device["deviceId"]: self._async_get_device(device)
            for device in devices["deviceList"]
        }

        if self._file_cache:
            with open(self._file_cache, "w", encoding="utf-8") as f:
                json.dump(devices, f, ensure_ascii=False, indent=4)
                f.close()

    def _async_get_device(self, device: dict[str, Any]) -> KasaDevice:
        """Initialize a KasaDevice from the api response."""
        if (
            device.get("deviceType") == "IOT.SMARTPLUGSWITCH"
            and re.search("Plug", str(device.get("deviceName"))) is not None
        ):
            return KasaPlug(self._kasacloudapi, device)
        elif (
            device.get("deviceType") == "IOT.SMARTPLUGSWITCH"
            and re.search("Switch", str(device.get("deviceName"))) is not None
        ):
            return KasaSwitch(self._kasacloudapi, device)
        elif device.get("deviceType") == "IOT.SMARTBULB":
            return KasaLight(self._kasacloudapi, device)
        raise KasaCloudError(
            f"Unknown device type: {device.get('deviceId')}, {device.get('deviceModel')}," +
                "{device.get('deviceName')}, {device.get('deviceType')}"
        )
