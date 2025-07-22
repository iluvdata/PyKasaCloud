"""Kasa Cloud API module for PyKasaCloud."""

import json
import logging
import uuid
from typing import Any, Callable, Optional

import aiohttp

from . import KasaCloudError
from .const import API_URL, APPTYPE, USERAGENT

__LOGGER__ = logging.getLogger(__name__)


class MissingCredentials(KasaCloudError):
    """Exception raised when credentials are missing."""


class BadAuth(KasaCloudError):
    """Exception raised when authentication fails."""


class KasaCloudApi:
    """Class to handle Kasa Cloud API interactions."""

    _tokens: dict[str, Any]
    _token_storage_file: str
    _cache_token: bool = True
    _url: str = API_URL
    _token_update_callback: Callable[[dict[str, Any]], None] | None = None

    @classmethod
    async def auth(
        cls,
        username: Optional[str] = None,
        password: Optional[str] = None,
        tokens: dict[str, Any] = None,
        token_storage_file: str = ".kasacloud.json",
        cache_token: bool = True,
        token_update_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        """Authenticate with the Kasa Cloud API and return an instance of KasaCloudApi."""

        self = cls()
        self._tokens = tokens
        self._cache_token = cache_token
        self._token_storage_file = token_storage_file
        self._token_update_callback = token_update_callback

        if not self._tokens:
            if not username:
                # Try and load from file cache
                try:
                    with open(self._token_storage_file, "r", encoding="utf-8") as f:
                        self._tokens = json.load(f)
                        f.close()

                except FileNotFoundError as ex:
                    raise MissingCredentials(
                        "Username/password or tokens must be provided"
                    ) from ex

            else:
                if not password:
                    raise MissingCredentials(
                        "Username provided but password is missing"
                    )
                # login for the first time
                client_id: str = str(uuid.uuid4())
                payload: dict[str, Any] = {
                    "method": "login",
                    "params": {
                        "cloudUserName": username,
                        "cloudPassword": password,
                        "terminalUUID": client_id,
                        "refreshTokenNeeded": "true",
                    },
                }
                auth_results = await self._async_request(payload)
                self._tokens = {
                    "token": auth_results["token"],
                    "refresh_token": auth_results["refreshToken"],
                    "client_id": client_id,
                }
                if self._cache_token:
                    self._cache_tokens()
        return self

    def update_url(self, url: str) -> None:
        """Update the API URL. This is used to set the account specific API URL."""
        self._url = url

    @property
    def tokens(self) -> dict[str, Any]:
        """Return the current tokens."""
        return self._tokens

    def _cache_tokens(self) -> None:
        if self._cache_token:
            with open(self._token_storage_file, "w", encoding="utf-8") as f:
                json.dump(self.tokens, f, ensure_ascii=False, indent=4)
                f.close()

    async def async_passthrough_request(
        self,
        device_id: str,
        request_type: str,
        subrequest_type: str,
        request: dict[str, Any],
        url: str | None = None,
    ) -> dict[str, Any]:
        """Make a passthrough request to the api."""

        payload: dict[str, Any] = {
            "method": "passthrough",
            "params": {
                "deviceId": device_id,
                # Some devices will give JSON format error if you don't set
                # requestData as a jsonized string
                "requestData": json.dumps({request_type: {subrequest_type: request}}),
            },
        }

        response: dict[str, Any] = await self.async_request(payload=payload, url=url)

        request_response: dict[str, Any] | None = response.get(request_type)

        if request_response is None:
            raise KasaCloudError(f"No response for request type: {request_type}")

        subrequest_response: dict[str, Any] | None = request_response.get(
            subrequest_type
        )

        if subrequest_response is None:
            raise KasaCloudError(
                f"No response for request type: {request_type} and sub request {subrequest_type}"
            )

        if (
            subrequest_response.get("err_code") is not None
            and subrequest_response["err_code"] != 0
        ):
            raise KasaCloudError(f"Received error code {subrequest_response}")

        return subrequest_response

    async def async_request(
        self, payload: dict[str, Any], url: str | None = None
    ) -> dict[str, Any]:
        """Make a request to the Kasa Cloud API.
        This method adds the auth token to the payload and sends the request.
        """

        if not payload.get("params"):
            payload["params"] = {}
        payload["params"]["token"] = self._tokens["token"]
        return await self._async_request(payload, url)

    async def _async_request(
        self, payload: dict[str, Any], url: str | None = None
    ) -> dict[str, Any]:
        response: dict[str, Any] = {}
        async with aiohttp.ClientSession(headers={"User-Agent": USERAGENT}) as session:
            if not payload.get("params"):
                payload["params"] = {}
            payload["params"]["appType"] = APPTYPE
            __LOGGER__.debug("Sending request:\n%s", json.dumps(payload, indent=4))
            async with session.post(url if url else self._url, json=payload) as resp:
                response = await resp.json()

                if response["error_code"] != 0:
                    if response["error_code"] == -20651:
                        # token is expired
                        await self._async_refresh_token()
                        # try again
                        response = await self._async_request(payload, url)
                    else:
                        raise KasaCloudError(
                            f"Error code: {response['error_code']}, message: {response['msg']}"
                        )
                response = response["result"]
                if response.get("responseData"):
                    response = response["responseData"]
                    if isinstance(response, str):
                        response = json.loads(response)
                __LOGGER__.debug(
                    "Received response:\n%s", json.dumps(response, indent=4)
                )

                resp.close()
            await session.close()
        return response

    async def _async_refresh_token(self) -> None:
        payload: dict[str, Any] = {
            "method": "refreshToken",
            "params": {
                "refreshToken": self._tokens["resfresh_token"],
                "terminalUUID": self._tokens["client_id"],
            },
        }
        new_token: dict[str, Any] = await self._async_request(payload)
        self._tokens["token"] = new_token["token"]
        self._cache_tokens()
