from requests.auth import AuthBase
from market_maker.utils.bitfinex.auth import generate_auth_headers_restv1


class BitfinexAPIKeyAuthWithExpires(AuthBase):

    """Attaches API Key Authentication to the given Request object."""
    def __init__(self, apiKey, apiSecret, endpoint, sData):
        """Init with Key & Secret."""
        self.apiKey = apiKey
        self.apiSecret = apiSecret
        self.endpoint = endpoint
        self.sData = sData

    def __call__(self, r):
        """
        Called when forming a request - generates api key headers.
        """
        r.headers = generate_auth_headers_restv1(self.apiKey, self.apiSecret, self.endpoint, self.sData)
        r.headers["content-type"] = "application/json"

        return r
