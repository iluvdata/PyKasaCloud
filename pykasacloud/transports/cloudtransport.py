"""Kasa Cloud API module for PyKasaCloud."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any, TypedDict, cast
import uuid

from aiohttp import ClientSession
import anyio
from kasa import (
    AuthenticationError,
    BaseTransport,
    DeviceConfig,
    DeviceError,
    KasaException,
)
from kasa.exceptions import _RetryableError
from kasa.httpclient import HttpClient
from kasa.json import dumps as json_dumps, loads as json_loads
from yarl import URL

from pykasacloud.const import (
    API_URL,
    APPSERVERURL,
    APPTYPE,
    CLIENT_ID,
    REFRESH_TOKEN,
    TOKEN,
    USERAGENT,
)
from pykasacloud.exceptions import CloudErrorCode, KasaCloudError

# _LOGGER = logging.getLogger(__name__)


@dataclass
class Token(TypedDict):
    """Token dataclass."""

    token: str
    refresh_token: str
    client_id: str
    account_id: int


class CloudTransport(BaseTransport):
    """CloudTransport."""

    COMMON_HEADERS = {"User-Agent": USERAGENT}

    _token: Token
    _token_storage_file: str | None
    _token_update_callback: Callable[[Token], Coroutine] | None
    _url: URL = URL(API_URL)
    _http_client: HttpClient

    @classmethod
    async def auth(
        cls,
        *,
        client_session: ClientSession,
        username: str | None = None,
        password: str | None = None,
        token: Token | None = None,
        token_storage_file: str | None = None,
        token_update_callback: Callable[[Token], Coroutine] | None = None,
    ) -> "CloudTransport":
        """Create a CloudTransport Class."""

        self = cls(
            config=DeviceConfig(host="TPLink/Kasa Cloud", http_client=client_session),
        )

        self._token_storage_file = token_storage_file
        self._token_update_callback = token_update_callback

        self._http_client = HttpClient(config=self._config)

        if not token:
            if not username:
                if not token_storage_file:
                    raise AuthenticationError(
                        "Username/password or tokens must be provided"
                    )
                # Try and load from file cache
                try:
                    async with await anyio.open_file(
                        token_storage_file, "r", encoding="utf-8"
                    ) as f:
                        self._token = Token(**json.loads(await f.read()))
                        await f.aclose()

                except FileNotFoundError as ex:
                    raise AuthenticationError(
                        "Username/password or tokens must be provided"
                    ) from ex

            else:
                if not password:
                    raise AuthenticationError(
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
                auth_results = await self._send_request(payload)
                self._token = Token(
                    token=auth_results["token"],
                    refresh_token=auth_results["refreshToken"],
                    client_id=client_id,
                    account_id=auth_results["accountId"],
                )
                await self._cache_tokens()
        else:
            self._token = token

        return self

    @property
    def token(self) -> Token:
        """Return the current token."""
        return self._token

    async def _cache_tokens(self) -> None:
        if self._token_storage_file:
            async with await anyio.open_file(
                self._token_storage_file, "w", encoding="utf-8"
            ) as f:
                json.dump(self._token, f, ensure_ascii=False, indent=4)
                await f.aclose()
        if self._token_update_callback:
            await self._token_update_callback(self._token)

    async def _handle_cloud_response_error_code(self, resp_dict: Any) -> None:
        """Handle response errors to request reauth etc."""

        try:
            cloud_error_code = CloudErrorCode(resp_dict["error_code"])
        except ValueError as ex:
            raise KasaCloudError(f"Got unknown error: {resp_dict}") from ex

        if cloud_error_code == CloudErrorCode.SUCCESS:
            return

        msg = resp_dict["msg"]
        if cloud_error_code == CloudErrorCode.TOKEN_EXPIRED:
            await self._refresh_token()
            raise _RetryableError(
                "{msg}: {self._host}: {error_code.name}({code})",
                error_code=cloud_error_code,
            )
        if cloud_error_code == CloudErrorCode.DEVICE_OFFLINE:
            raise DeviceError(f"{msg}: {cloud_error_code.value}")
        if cloud_error_code == CloudErrorCode.INVALID_EMAIL_OR_PASSWORD:
            raise AuthenticationError(resp_dict)
        raise KasaCloudError(
            f"{msg}: {cloud_error_code.name}({cloud_error_code.value})"
        )

    async def send(self, request: str) -> dict[str, Any]:
        """Not implemented."""
        return {}

    async def send_request(
        self,
        payload: dict[str, Any],
        device_id: str | None = None,
        url: URL | None = None,
    ) -> dict[str, Any]:
        """Send request to Kasa Cloud."""
        cpayload: dict[str, Any] = {"params": {}}
        cpayload["params"]["token"] = self._token[TOKEN]
        if device_id:
            cpayload["method"] = "passthrough"
            cpayload["params"]["deviceId"] = device_id
            cpayload["params"]["requestData"] = json_dumps(payload)
        else:
            cpayload["method"] = payload["method"]
        return await self._send_request(cpayload, url)

    async def _send_request(
        self, payload: dict[str, Any], url: URL | None = None
    ) -> dict[str, Any]:
        """Send a request."""
        if "params" not in payload:
            payload["params"] = {}
        payload["params"]["appType"] = APPTYPE

        if not url:
            url = self._url

        status_code, resp_dict = await self._http_client.post(
            url=url, json=payload, headers=self.COMMON_HEADERS
        )

        if status_code != 200:
            raise KasaException(
                f"{self._host} responded with an unexpected status code {status_code}"
            )

        # _LOGGER.debug("Response with %s: %r", status_code, resp_dict)

        await self._handle_cloud_response_error_code(resp_dict)

        if TYPE_CHECKING:
            resp_dict = cast(dict[str, Any], resp_dict)

        if "result" in resp_dict:
            resp_dict = resp_dict["result"]
            if resp_dict and "deviceList" in resp_dict and resp_dict["deviceList"]:
                # get the url
                self._url = URL(resp_dict["deviceList"][0][APPSERVERURL])

        if "responseData" in resp_dict:
            resp_dict = resp_dict["responseData"]
            if isinstance(resp_dict, str):
                resp_dict = json_loads(resp_dict)

        # await self.close()

        return resp_dict

    async def _refresh_token(self) -> None:
        if not self._token[REFRESH_TOKEN]:
            raise AuthenticationError(
                "No tokens or refresh token available for refreshing"
            )
        if not self._token[CLIENT_ID]:
            raise AuthenticationError("No client_id available for refreshing token")
        payload: dict[str, Any] = {
            "method": "refreshToken",
            "params": {
                "refreshToken": self._token[REFRESH_TOKEN],
                "terminalUUID": self._token[CLIENT_ID],
            },
        }
        new_token: dict[str, Any] = await self._send_request(payload)
        self._token[TOKEN] = new_token[TOKEN]
        await self._cache_tokens()

    @property
    def default_port(self) -> int:
        """Default port is irrevelant for cloud operations."""
        return 443

    @property
    def credentials_hash(self) -> str | None:
        """Cloud doesn't use credentials hash."""
        return None

    async def close(self) -> None:
        """Close the transport."""
        await self._http_client.close()

    async def reset(self) -> None:
        """This does nothing."""
