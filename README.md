# PyKasaCloud

This is a library wrapper that allows you to connect to *some* TPLink/Kasa/Tapo devices via the cloud utilizing the excellent [python-kasa](https://pypi.org/project/python-kasa/) library.  Essentially this adds a transport and protocol class to facilitate this.  This has not been tested extensively as I only have access to "iot" protocol devices and I'm not sure if other devices utilize passthrough mechanism via the cloud api.

## Usage

Rather than use discovery like `python-kasa` you must get connect to the cloud (providing credentials) to obtain a token.
```python
cloud: KasaCloud = await KasaCloud.auth(username="username", password="password")
```
You can then get a dictionary of devices.  The deviceId in the cloud will be the keys and the values will be `kasa.Device`s.
```python
devices: dict[str, Device] = cloud.getDevices()
```
You can then interact with these devices like python-kasa devices.

### Caching tokens

To cache tokens to a json file, provide a path.
```python
cloud: KasaCloud = await KasaCloud.auth(username="username", password="password", token_storage_file=".kasacloud.json")
```
Subsequent authenication can be accomplished just using the `token_storage_file` parameter.
```python
cloud: KasaCloud = await KasaCloud.auth( token_storage_file=".kasacloud.json")
```
### Refesh Token and Callbacks
If you are storing the token externally, say in a HomeAssistant Config Entry simply pass a `Token` object:
```python

def token_update_callback(config_entry: ConfigEntry) -> Callable:
    def updated_token(token: Token) -> None:
        config_entry["token"] <- token
    return update_token

token = Token(**config_entry.get("token"))
cloud: KasaCloud = await KasaCloud.auth(token=token, token_update_callback = token_update_callback(config_entry))
```



