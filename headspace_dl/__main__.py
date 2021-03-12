import requests
import os
import click
import re
import logging
from typing import Union, List, Optional
from rich.console import Console
from rich.progress import track
from ast import literal_eval
from rich.traceback import install


install()

BASEDIR = os.path.dirname(os.path.realpath(__file__))
LOG_FILE = os.path.join(BASEDIR, "..", "debug.log")
BEARER = os.path.abspath(os.path.join(BASEDIR, "..", "bearer_id.txt"))

AUDIO_URL = "https://api.prod.headspace.com/content/activities/{}"
PACK_URL = "https://api.prod.headspace.com/content/activity-groups/{}"
SIGN_URL = "https://api.prod.headspace.com/content/media-items/{}/make-signed-url"
TECHNIQUE_URL = "https://api.prod.headspace.com/content/techniques/{}"

if not os.path.exists(BEARER):
    with open(BEARER, "w") as file:
        file.write("")

with open(BEARER, "r") as file:
    BEARER_ID = file.read().strip()


headers = {
    "authority": "api.prod.headspace.com",
    "accept": "application/vnd.api+json",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 Safari/537.36",
    "authorization": BEARER_ID,
    "hs-languagepreference": "en-US",
    "sec-gpc": "1",
    "origin": "https://my.headspace.com",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "referer": "https://my.headspace.com/",
    "accept-language": "en-US,en;q=0.9",
}

console = Console()
logging.basicConfig(filename=LOG_FILE, level=logging.INFO)

if not BEARER_ID:
    error = "Bearer id not found."
    console.print(f"[red]{error}[/red]")
    console.print(f"Location of bearer_id.txt file: {BEARER}")
    logging.critical(error)

session = requests.Session()
session.headers.update(headers)


class PythonLiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        try:
            out = literal_eval(value)
            if type(out) == int or type(out) == str:
                return [
                    out,
                ]
            return out
        except:
            raise click.BadParameter(value)


def request_url(
    url: str,
    *,
    id: Union[str, int] = None,
    mute: bool = False,
):
    url = url.format(id)
    if not mute:
        # console.print("Sending [green]GET[/green] request to {}".format(url))
        logging.info("Sending GET request to {}".format(url))

    response = session.get(url)
    response_js: dict = response.json()

    if not response.ok:
        console.print(response_js)
        if "errors" in response_js.keys():
            logging.error(response_js["errors"])
        else:
            logging.error(response_js)
        raise click.UsageError(f"HTTP error: status-code = {response.status_code}")
    return response_js


def round_off(time: int):
    time = time // 60000
    unit_place = time % 10

    if unit_place > 0 and unit_place < 5:
        time -= unit_place
    elif unit_place > 5:
        time -= unit_place - 5

    return time


def get_pack_attributes(
    *,
    pack_id: Union[str, int],
    duration: List[int],
    out: str,
    no_techniques: bool,
    no_meditation: bool,
):
    response = request_url(PACK_URL, id=pack_id)
    attributes: dict = response["data"]["attributes"]
    _pack_name: str = attributes["name"]
    # Logging
    logging.info(f"Downloading pack, name: {_pack_name}")

    # Printing
    console.print("Pack metadata: ")
    console.print(f'[green]Name: [/green] {attributes["name"]}')
    console.print(f'[green]Description: [/green] {attributes["description"]}')

    data = response["included"]
    for item in data:
        if item["type"] == "orderedActivities":
            if not no_meditation:
                id = item["relationships"]["activity"]["data"]["id"]
                download_pack_session(id, duration, _pack_name, out=out)
        elif item["type"] == "orderedTechniques":
            if not no_techniques:
                id = item["relationships"]["technique"]["data"]["id"]
                download_pack_techniques(id, pack_name=_pack_name, out=out)


def download_pack_session(
    id: Union[int, str], duration: List[int], pack_name: Optional[str], out: str
):
    response = request_url(AUDIO_URL, id=id)
    data = response["included"]

    for item in data:
        name = response["data"]["attributes"]["name"]
        if item["type"] != "mediaItems":
            continue
        duration_in_min = round_off(int(item["attributes"]["durationInMs"]))

        if duration_in_min not in duration:
            continue

        sign_id = item["id"]
        # Getting signed URL
        direct_url = request_url(SIGN_URL, id=sign_id)["url"]
        if len(duration) > 1:
            name += f"({duration_in_min} minutes)"
        download(direct_url, name, filename=name, pack_name=pack_name, out=out)


def download_pack_techniques(
    technique_id: Union[int, str], *, pack_name: Optional[str] = None, out: str
):
    response = request_url(TECHNIQUE_URL, id=technique_id)
    name = response["data"]["attributes"]["name"]
    for item in response["included"]:
        if not item["type"] == "mediaItems":
            continue
        if item["attributes"]["mimeType"] == "video/mp4":
            sign_id = item["id"]
            break
    direct_url = request_url(SIGN_URL, id=sign_id)["url"]
    download(direct_url, name, filename=name, pack_name=pack_name, out=out)


def download(
    direct_url: str,
    name: str,
    *,
    filename: str,
    pack_name: Optional[str] = None,
    out: str,
):
    console.print(f"[green]Downloading {name}[/green]")
    logging.info(f"Downloading {name}")
    logging.info(f"Sending GET request to {direct_url}")
    media = requests.get(direct_url, stream=True)

    if not media.ok:
        media_json = media.json()
        console.print(media_json)
        logging.error(media_json)
        raise click.UsageError(f"HTTP error: status-code = {response.status_code}")

    media_type = media.headers.get("content-type").split("/")[-1]
    filename += f".{media_type}"
    total_length = int(media.headers.get("content-length"))
    chunk_size = 1024

    if not os.path.exists(out) and os.path.isdir(out):
        raise click.BadOptionUsage(f"{out} path not valid")

    if pack_name:
        dir_path = os.path.join(out, pack_name)
        try:
            os.mkdir(dir_path)
        except FileExistsError:
            pass
        filepath = os.path.join(dir_path, filename)
    else:
        filepath = os.path.join(out, filename)

    with open(filepath, "wb") as file:
        for chunk in track(
            media.iter_content(chunk_size=chunk_size),
            description=f"[red]Downloading...[/red]",
            total=total_length // chunk_size,
        ):
            file.write(chunk)
            file.flush()


def find_id(pattern: str, url: str):
    try:
        id = int(re.findall(pattern, url)[-1])
    except ValueError:
        raise click.UsageError(
            "Cannot find the ID. Please use --id argument to provide the ID."
        )
    except IndexError:
        raise click.UsageError(
            "Cannot find the ID. Please use --id argument to provide the ID."
        )
    return id


@click.group()
def cli():
    """
    Download headspace packs or individual meditation and techniques.
    """
    pass


@cli.command("pack")
@click.argument("url", type=str, default="", required=False)
@click.option("--id", type=int, default=0, help="ID of video.")
@click.option(
    "-d",
    "--duration",
    cls=PythonLiteralOption,
    help="Duration or list of duration",
    default="[15,]",
)
@click.option(
    "--no_meditation",
    is_flag=True,
    help="Only download meditation session without techniques videos.",
    default=False,
)
@click.option(
    "--no_techniques",
    is_flag=True,
    help="Only download techniques and not meditation sessions.",
    default=False,
)
@click.option("--out", default="", help="Download directory")
def pack(
    id: int,
    duration: Union[list, tuple],
    out: str,
    no_techniques: bool,
    no_meditation: bool,
    url: str,
):
    """
    Download headspace pack with techniques videos.
    """
    if not type(duration) == list or type(duration) == tuple:
        raise click.BadParameter(duration)
    if url == "" and id_ <= 0:
        raise click.BadParameter("Please provide ID or URL.")

    duration = list(set(duration))

    for idx, d in enumerate(duration):
        try:
            d = int(d)
            duration[idx] = d
        except:
            raise click.BadParameter(duration)

        if not (d == 10 or d == 15 or d == 20):
            raise click.BadParameter("Duration could only be list of 10, 15 or 20.")

    if url:
        pattern = r"my.headspace.com/packs/([0-9]+)"
        id = find_id(pattern, url)

    get_pack_attributes(
        pack_id=id,
        duration=duration,
        out=out,
        no_meditation=no_meditation,
        no_techniques=no_techniques,
    )


@cli.command("download")
@click.argument(
    "url",
    type=str,
    required=False,
    default="",
)
@click.option("--out", default="", help="Download directory.")
@click.option(
    "--id",
    "id_",
    type=int,
    default=0,
    help="ID of the video. Not required if URL is provided.",
)
@click.option(
    "-d",
    "--duration",
    cls=PythonLiteralOption,
    help="Duration or list of duration",
    default="[15,]",
)
def download_single(url: str, out: str, id_: int, duration: Union[list, tuple]):
    """
    Download single headspace meditation.
    """
    if url == "" and id_ <= 0:
        raise click.BadParameter("Please provide ID or URL.")
    pattern = r"my.headspace.com/play/([0-9]+)"
    if not id_ > 0:
        id = find_id(pattern, url)
    else:
        id = id_
    download_pack_session(id, duration, None, out)


session.close()