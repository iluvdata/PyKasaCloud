"""KasaCloud."""

import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from kasa import Device, DeviceType
from kasa.iot import (
    IotBulb,
    IotDevice,
    IotDimmer,
    IotLightStrip,
    IotPlug,
    IotStrip,
    IotWallSwitch,
)

from .exceptions import KasaCloudError

from .protocols import CloudProtocol
from .transports import CloudTransport, Token

_GET_DEVICES_QUERY: dict[str, str] = {
   "method": "getDeviceList"
}

GET_SYSINFO_QUERY: dict[str, dict[str, dict]] = {
    "system": {"get_sysinfo": {}},
}

_LOGGER = logging.getLogger(__name__)

class KasaCloud:
    """Class to instantiate and get devices."""

    _transport: CloudTransport

    @classmethod
    async def kasacloud(
        cls,
        *,
        username: str | None = None,
        password: str | None = None,
        token: dict[str, Any] | None = None,
        token_storage_file: str | None = None,
        token_update_callback: Callable[[Token], Coroutine] | None = None,
    ) -> "KasaCloud":
        """Get module kasacloud."""

        self = cls()

        ctoken: Token | None = Token(**token) if token else None
        self._transport = await CloudTransport.auth(
            username=username,
            password=password,
            token=ctoken,
            token_storage_file=token_storage_file,
            token_update_callback=token_update_callback
        )

        return self

    async def get_devices(self) -> dict[str, Device]:
        """Get kasa devices from cloud."""

        protocol: CloudProtocol = CloudProtocol(transport=self._transport)

        resp: dict = await protocol.query(_GET_DEVICES_QUERY)

        if "deviceList" not in resp:
            raise KasaCloudError(f"Invalid result {resp}")

        device_list: list[dict[str, Any]] = resp["deviceList"]

        device_dict: dict[str, Device] = {}
        for device in device_list:
            if device["status"]:
                device_dict[device["deviceId"]] = await self._get_device(device)

        return device_dict

    async def _get_device(self, device_dict: dict[str, Any]) -> Device:
        """Initantiate and populate the device.  
        Taken from device_factory.py in python-kasa."""
        debug_enabled = _LOGGER.isEnabledFor(logging.DEBUG)
        if debug_enabled:
            start_time = time.perf_counter()

        def _perf_log(has_params: bool, perf_type: str) -> None:
            nonlocal start_time
            if debug_enabled:
                end_time = time.perf_counter()
                _LOGGER.debug(
                    "Device %s with connection params %s took %.2f seconds to %s",
                    device_dict["deviceId"],
                    has_params,
                    end_time - start_time,
                    perf_type,
                )
                start_time = time.perf_counter()

        device_class: type[Device] | None
        device: Device | None = None

        protocol: CloudProtocol = CloudProtocol(transport=self._transport)
        protocol.attach_device(device_dict)

        info = await protocol.query(GET_SYSINFO_QUERY)
        _perf_log(True, "get_sysinfo")

        device_class = _get_device_class_from_sys_info(info)
        device = device_class(device_dict["deviceId"], protocol=protocol)
        device.update_from_discover_info(info)
        await device.update()
        _perf_log(True, "update")
        return device

def _get_device_class_from_sys_info(sysinfo: dict[str, Any]) -> type[IotDevice]:
    """Find SmartDevice subclass for device described by passed data."""
    TYPE_TO_CLASS = { # pylint: disable=invalid-name
        DeviceType.Bulb: IotBulb,
        DeviceType.Plug: IotPlug,
        DeviceType.Dimmer: IotDimmer,
        DeviceType.Strip: IotStrip,
        DeviceType.WallSwitch: IotWallSwitch,
        DeviceType.LightStrip: IotLightStrip,
        # Disabled until properly implemented
        # DeviceType.Camera: IotCamera,
    }
    return TYPE_TO_CLASS[IotDevice._get_device_type_from_sys_info(sysinfo)] # pylint: disable=protected-access
