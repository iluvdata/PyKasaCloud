"""Kasa Light class."""

from typing import Any

import re
import logging
from kasa.iot.iotbulb import TPLINK_KELVIN
from kasa.interfaces.light import HSV
from . import KasaCloudError
from .device import KasaDevice, Capabilities
from .api import KasaCloudApi

_LOGGER_ = logging.getLogger(__name__)

NON_COLOR_MODE_FLAGS = {"transition_period", "on_off"}

class KasaLight(KasaDevice):
    """Kasa Light class."""

    def __init__(self, api: KasaCloudApi, data: dict[str, Any]) -> None:
        """Initialize the Kasa Plug."""
        if not data.get("deviceType") == "IOT.SMARTBULB":
            raise ValueError("Invalid device type for Kasa Light")
        super().__init__(api, data)

    async def is_on(self) -> bool:
        """Check if the light is on."""
        await self._get_light_state()
        return self.info["light_state"]["on_off"] == 1

    async def turn_on(self) -> None:
        self.info["light_state"] = await self._set_light_state({"on_off": 1})

    async def turn_off(self) -> None:
        self.info["light_state"] = await self._set_light_state({"on_off": 0})

    async def toggle(self) -> None:
        """Toggle the light state."""
        if await self.is_on():
            await self.turn_off()
        else:
            await self.turn_on()

    async def get_light_details(self) -> dict[str, int]:
        """Get the light details."""
        return await self._async_passthrough_request(
            "smartlife.iot.smartbulb.lightingservice", "get_light_details", {}
        )

    async def set_color_temp(
        self, temp: int, *, brightness: int | None = None, transition: int | None = None
    ) -> dict[str, Any]:
        """Set the color temperature of the device in kelvin.

        :param int temp: The new color temperature, in Kelvin
        :param int transition: transition in milliseconds.
        """
        if Capabilities.COLOR_TEMP not in await self.capabilities():
            raise KasaCloudError("Bulb does not support color temperature.")

        await self._raise_for_invalid_temperature_range(temp)

        light_state = {"color_temp": temp}
        if brightness is not None:
            light_state["brightness"] = brightness

        return await self._set_light_state(light_state, transition=transition)

    async def get_color_temp(self) -> int:
        """Get the current color temperature in Kelvin."""
        if Capabilities.COLOR_TEMP not in await self.capabilities():
            raise KasaCloudError("Bulb does not support color temperature.")

        light_state: dict[str, Any] = await self._get_light_state()
        return light_state["color_temp"]

    async def _raise_for_invalid_temperature_range(self, temp:int) -> None:
        """Return the device-specific white temperature range (in Kelvin).

        :return: White temperature range in Kelvin (minimum, maximum)
        """
        if Capabilities.COLOR_TEMP not in await self.capabilities():
            raise KasaCloudError("Color temperature not supported")

        for model, temp_range in TPLINK_KELVIN.items():
            if re.match(model, self.data["model"]):
                if temp < temp_range[0] or temp > temp_range[1]:
                    raise ValueError(
                        f"Temperature should be between {temp_range[0]} and " +
                        "{temp_range[1]}, got {temp}"
                    )

        _LOGGER_.warning("Unknown color temperature range, fallback to 2700-5000")
        if temp < 2700 or temp > 5000:
            raise ValueError(
                f"Temperature should be between 2700 and 5000, got {temp}"
            )

    async def get_hsv(self) -> HSV:
        """Return the current HSV state of the bulb.

        :return: hue, saturation and value (degrees, %, %)
        """
        if Capabilities.COLOR not in await self.capabilities():
            raise KasaCloudError("Bulb does not support color.")

        light_state: dict[str, Any] = await self._get_light_state()

        hue:int = light_state["hue"]
        saturation:int = light_state["saturation"]
        value:int = light_state["brightness"]

        # Simple HSV(hue, saturation, value) is less efficent than below
        # due to the cpython implementation.
        return tuple.__new__(HSV, (hue, saturation, value))

    async def set_hsv(
        self,
        hue: int,
        saturation: int,
        value: int | None = None,
        *,
        transition: int | None = None,
    ) -> dict:
        """Set new HSV.

        :param int hue: hue in degrees
        :param int saturation: saturation in percentage [0,100]
        :param int value: value in percentage [0, 100]
        :param int transition: transition in milliseconds.
        """
        if Capabilities.COLOR not in await self.capabilities():
            raise KasaCloudError("Bulb does not support color.")

        if not 0 <= hue <= 360:
            raise ValueError(f"Invalid hue value: {hue} (valid range: 0-360)")

        if not 0 <= saturation <= 100:
            raise ValueError(
                f"Invalid saturation value: {saturation} (valid range: 0-100%)"
            )

        light_state = {
            "hue": hue,
            "saturation": saturation,
            "color_temp": 0,
        }

        if value is not None:
            self._raise_for_invalid_brightness(value)
            light_state["brightness"] = value

        return await self._set_light_state(light_state, transition=transition)

    async def get_brightness(self) -> int:
        """Get the current brightness in percentage."""
        if Capabilities.DIMMABLE not in await self.capabilities():
            raise KasaCloudError("Bulb does not support dimming.")

        light_state: dict[str, Any] = await self._get_light_state()
        return light_state["brightness"]

    async def set_brightness(
        self, brightness: int, *, transition: int | None = None
    ) -> dict[str, Any]:
        """Set the brightness of the device in percentage.

        :param int brightness: The new brightness, in percentage [0, 100]
        :param int transition: transition in milliseconds.
        """
        if Capabilities.DIMMABLE not in await self.capabilities():
            raise KasaCloudError("Bulb does not support dimming.")

        self._raise_for_invalid_brightness(brightness)

        # Note if the light support effects we should get the brightness from the effects

        return await self._set_light_state(
            {"brightness": brightness}, transition=transition
        )

    async def _get_light_state(self) -> dict[str, Any]:
        """Get the current light state."""
        self.info["light_state"] = await self._async_passthrough_request(
            "smartlife.iot.smartbulb.lightingservice", "get_light_state", {}
        )
        return self.info["light_state"]

    async def _set_light_state(
        self, state: dict[str, Any], *, transition: int | None = None
    ) -> dict[str, Any]:
        """Set the light state."""
        state = {**state}
        if transition is not None:
            state["transition_period"] = transition

        if "brightness" in state:
            self._raise_for_invalid_brightness(state["brightness"])

        # if no on/off is defined, turn on the light
        if "on_off" not in state:
            state["on_off"] = 1

        # If we are turning on without any color mode flags,
        # we do not want to set ignore_default to ensure
        # we restore the previous state.
        if state["on_off"] and NON_COLOR_MODE_FLAGS.issuperset(state):
            state["ignore_default"] = 0
        else:
            # This is necessary to allow turning on into a specific state
            state["ignore_default"] = 1

        return await self._async_passthrough_request(
            "smartlife.iot.smartbulb.lightingservice",
            "transition_light_state",
            state
        )

    def _raise_for_invalid_brightness(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("Brightness must be an integer")
        if not 0 <= value <= 100:
            raise ValueError(f"Invalid brightness value: {value} (valid range: 0-100%)")
