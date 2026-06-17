from typing import BinaryIO, Any

import requests
import re


_COBALT_HOST_REGEX = re.compile(
    r"(?:m\.)?bilibili\.com"
    r"|(?:profile\.)?bsky\.app"
    r"|dailymotion\.com"
    r"|(?:web|m\.)?facebook\.com"
    r"|fb\.watch"
    r"|(?:ddinstagram\.com|instagram\.com)"
    r"|loom\.com"
    r"|ok\.ru"
    r"|pinterest\.com"
    r"|pin\.it"
    r"|newgrounds\.com"
    r"|reddit\.com"
    r"|(?:rutube\.ru|rutube\.com)"
    r"|snapchat\.com"
    r"|(?:on|m\.)?soundcloud\.com"
    r"|streamable\.com"
    r"|(?:vt|vm|m|t|pro\.)?tiktok\.com"
    r"|(?:tumblr\.com|www\.tumblr\.com)"
    r"|(?:clips|www|m\.)?twitch\.tv"
    r"|(?:x\.com|twitter\.com|vxtwitter\.com|fixvx\.com|fixupx\.com)"
    r"|(?:player\.)?vimeo\.com"
    r"|(?:vk\.com|vkvideo\.ru|vk\.ru)"
    r"|youtu\.be"
    r"|(?:music|m\.)?youtube\.com",
    re.IGNORECASE
)


class CobaltAPIStreamableResponse:
    def __init__(self, stream: requests.Response, original_response_json: Any) -> None:
        self.stream = stream
        self._original_response_json = original_response_json

    @property
    def filename(self) -> str:
        return self._original_response_json["filename"]

    def stream_to_file(self, file: BinaryIO | str, chunk_size=8192) -> None:
        if isinstance(file, str):
            file = open(file, "wb")
        with file as f:
            for chunk in self.stream.iter_content(chunk_size=chunk_size):
                f.write(chunk)
            if f.tell() == 0:
                raise CobaltAPIClientException("Response stream was empty.")


class CobaltAPITunnelResponse(CobaltAPIStreamableResponse):
    pass


class CobaltAPIRedirectResponse(CobaltAPIStreamableResponse):
    pass


class CobaltAPIClient:
    def __init__(self, instance_url: str, api_key: str = None) -> None:
        self.instance_url = instance_url
        self.api_key = api_key

    def post(self, url: str) -> CobaltAPITunnelResponse | CobaltAPIRedirectResponse:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"}
        if self.api_key:
            headers.update({
                               "Authorization": f"Api-Key {self.api_key}"})
        response = requests.post(self.instance_url, json={
            "url": url}, headers=headers).json()
        status = response["status"]
        if status == "error":
            raise CobaltAPIError(response["error"]["code"])
        elif status == "tunnel":
            stream = requests.get(response["url"], stream=True)
            try:
                stream.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise CobaltAPIError(f"Tunnel URL errored out: {e}")
            return CobaltAPITunnelResponse(stream, response)
        elif status == "redirect":
            stream = requests.get(response["url"], stream=True)
            try:
                stream.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise CobaltAPIError(f"Redirect URL errored out: {e}")
            return CobaltAPIRedirectResponse(stream, response)
        else:
            raise CobaltAPIClientException(f"Unsupported non-error status: {status}")

    @staticmethod
    def supports_url(url: str) -> bool:
        return False if _COBALT_HOST_REGEX.search(url) is None else True


class CobaltAPIError(Exception):
    pass


class CobaltAPIClientException(Exception):
    pass
