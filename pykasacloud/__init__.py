"""PyKasaCloud - A Python library for interacting with Kasa Cloud API."""

class KasaCloudError(Exception):
    """Exception raised for errors in the Kasa Cloud API interaction."""
    def __init__(self, msg:str) -> None:
        super().__init__(msg)
