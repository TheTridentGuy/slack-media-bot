import os
import shutil
import time
import uuid
from pathlib import Path

import dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError

from cobalt_api import CobaltAPIClient, CobaltAPIError, CobaltAPIClientException

dotenv.load_dotenv()
app = App(token=os.environ["SLACK_BOT_TOKEN"])
client = app.client
cobalt_client = CobaltAPIClient(os.environ["COBALT_API_INSTANCE"], os.environ.get("COBALT_API_KEY"))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")


def recursive_url_search(elements):
    if elements is None:
        return []
    urls = []
    for element in elements:
        if element.get("type") == "link":
            urls.append(element["url"])
        else:
            urls.extend(recursive_url_search(element.get("elements")))
    return urls


@app.event("message")
def raw_file_reply(message):
    blocks = message.get("blocks")
    if not blocks:
        return
    urls = recursive_url_search(blocks)
    print(urls)
    ts = message["ts"]
    for url in urls:
        save_path = None
        if not cobalt_client.supports_url(url):
            continue
        try:
            cobalt_response = cobalt_client.post(url)
            save_path = str(Path(OUTPUT_DIR) / Path(str(uuid.uuid4())))
            cobalt_response.stream_to_file(save_path)
            permalink = client.files_upload_v2(file=save_path, filename=cobalt_response.filename)["file"]["permalink"]
            blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Shared by <@{message['user']}> | <{permalink}|Link to file> | <https://github.com/TheTridentGuy/slack-cobalt|:star: on GitHub>"
                        }
                    ]
                }
            ]
            client.chat_postMessage(channel=message["channel"], thread_ts=ts, blocks=blocks)
            os.remove(save_path)
        except (CobaltAPIError, CobaltAPIClientException) as e:
            if save_path:
                os.remove(save_path)
            print(e, url)


def clean_output_dir():
    try:
        shutil.rmtree(OUTPUT_DIR)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    try:
        clean_output_dir()
        os.mkdir(OUTPUT_DIR)
        SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    except KeyboardInterrupt:
        clean_output_dir()
