# PyKasaCloud

![PyPI - Version](https://img.shields.io/pypi/v/pykasacloud)

This is a library wrapper that allows you to connect to *some* TPLink/Kasa/Tapo devices via the cloud utilizing the excellent [python-kasa](https://pypi.org/project/python-kasa/) library.  Essentially this adds a transport and protocol class to facilitate this.  This appears to only work on "iot" protocol (legacy) devices rather than "smart" protocol devices (tapo and some newer kasa devices).

This library was written to support the [TPLink Cloud Integration](https://github.com/iluvdata/tplink_cloud).

## Usage

Rather than use discovery like `python-kasa` you must get connect to the cloud (providing credentials) to obtain a token.
```python
cloud: KasaCloud = await KasaCloud.kasacloud(username="username", password="password")
```
You can then get a list of device dictionaries which you can then use to get a `kasa.Device`:
```python
devices: list[DeviceDict] = cloud.get_device_list()
device: Device = cloud.get_device(devices[0])
```
You can then interact with these devices like python-kasa devices.

### Caching tokens

To cache tokens to a json file, provide a path.
```python
cloud: KasaCloud = await KasaCloud.kasacloud(username="username", password="password", token_storage_file=".kasacloud.json")
```
Subsequent authenication can be accomplished just using the `token_storage_file` parameter.
```python
cloud: KasaCloud = await KasaCloud.kasacloud( token_storage_file=".kasacloud.json")
```
### Refesh Token and Callbacks
If you are storing the token externally, say in a HomeAssistant Config Entry simply pass a `Token` object (inside `async_setup_entry` in `__init__.py` of a given integration)
```python

async def update_token(token: Token) -> None:
    data = entry.data | {TOKEN: token}
    result = hass.config_entries.async_update_entry(
        entry=entry, data=data, unique_id=entry.unique_id
    )
    if not result:
        raise TokenUpdateError("Unable to update token in config entry")

    try:
        cloud: KasaCloud = await KasaCloud.kasacloud(
            token=entry.data.get(TOKEN), token_update_callback=update_token
        )
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
```



