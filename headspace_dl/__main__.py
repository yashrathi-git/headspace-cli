import logging
import os
import re
from ast import literal_eval
from time import sleep
from typing import List, Optional, Union
from datetime import date, timedelta, datetime

import click
import requests
from rich.console import Console
from rich.progress import track
from rich.traceback import install

install()
# print("NEW")
BASEDIR = os.path.dirname(os.path.realpath(__file__))
LOG_FILE = os.path.join(BASEDIR, "debug.log")
BEARER = os.path.abspath(os.path.join(BASEDIR, "bearer_id.txt"))

AUDIO_URL = "https://api.prod.headspace.com/content/activities/{}"
PACK_URL = "https://api.prod.headspace.com/content/activity-groups/{}"
SIGN_URL = "https://api.prod.headspace.com/content/media-items/{}/make-signed-url"
TECHNIQUE_URL = "https://api.prod.headspace.com/content/techniques/{}"
EVERYDAY_URL = (
    "https://api.prod.headspace.com/content/view-models/everyday-headspace-banner"
)
GROUP_COLLECTION = "https://api.prod.headspace.com/content/group-collections"

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


URL_GROUP_CMD = [
    click.option("--id", type=int, default=0, help="ID of video."),
    click.argument("url", type=str, default="", required=False),
]

COMMON_CMD = [
    click.option(
        "-d",
        "--duration",
        cls=PythonLiteralOption,
        help="Duration or list of duration",
        default="[15,]",
    ),
    click.option("--out", default="", help="Download directory"),
]


def shared_cmd(cmd):
    def _shared_cmd(func):
        for option in reversed(cmd):
            func = option(func)
        return func

    return _shared_cmd


def get_group_ids():
    params = {"category": "PACK_GROUP", "limit": "-1"}
    response = request_url(GROUP_COLLECTION, params=params)
    data = response["included"]
    pack_ids = []
    for item in data:
        try:
            id = item["relationships"]["activityGroup"]["data"]["id"]
        except KeyError:
            pass
        pack_ids.append(int(id))
    return sorted(pack_ids)


def request_url(
    url: str, *, id: Union[str, int] = None, mute: bool = False, params: dict = {}
):
    url = url.format(id)
    if not mute:
        # console.print("Sending [green]GET[/green] request to {}".format(url))
        logging.info("Sending GET request to {}".format(url))

    response = session.get(url, params=params)
    try:
        response_js: dict = response.json()
    except:
        logging.critical(f"Invalid JSON data with status code {response.status_code}")
        console.print(repr(response))
        console.print("Invalid JSON data. DATA=")
        console.print(response.text)
        raise click.Abort()
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
    if time == 0:
        time = 1
    return time


def get_pack_attributes(
    *,
    pack_id: Union[str, int],
    duration: List[int],
    out: str,
    no_techniques: bool,
    no_meditation: bool,
    all_: bool = False,
):
    response = request_url(PACK_URL, id=pack_id)
    attributes: dict = response["data"]["attributes"]
    _pack_name: str = attributes["name"]

    if all_:
        exists = os.path.exists(os.path.join(out, _pack_name))
        if exists:
            console.print(
                "[red]Aborting [/red] download of "
                f"{_pack_name} because it already exists."
            )
            return
    # Logging
    logging.info(f"Downloading pack, name: {_pack_name}")

    # Printing
    console.print("Pack metadata: ")
    console.print(f'[green]Name: [/green] {attributes["name"]}')
    console.print(f'[green]Description: [/green] {attributes["description"]}')

    if all_ is True:
        console.print(f"URL: https://my.headspace.com/packs/{pack_id}")
        console.print(
            "Use [green]--exclude[/green] option to exclude downloading this pack."
        )
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


def get_signed_url(response: dict, duration: List[int]) -> dict:
    data = response["included"]
    signed_links = {}
    av_duration = []
    for item in data:
        try:
            name = response["data"]["attributes"]["name"]
        except KeyError:
            name = response["data"]["attributes"]["titleText"]
        if item["type"] != "mediaItems":
            continue
        try:
            duration_in_min = round_off(int(item["attributes"]["durationInMs"]))
        except KeyError:
            continue
        av_duration.append(duration_in_min)
        if duration_in_min not in duration:
            continue

        sign_id = item["id"]
        # Getting signed URL
        direct_url = request_url(SIGN_URL, id=sign_id)["url"]
        if len(duration) > 1:
            name += f"({duration_in_min} minutes)"

        signed_links[name] = direct_url
    if len(signed_links) == 0:
        msg = (
            f"Cannot download {name}. This could be"
            " because this session might not be available in "
            f"{', '.join(str(d) for d in duration)} min duration."
        )
        console.print(f"[yellow]{msg}[yellow]")
        console.print(
            "This session is available with duration of "
            f"{'/'.join(str(d) for d in av_duration)} minutes. "
            "Use [green]--duration[/green] option to modify required duration."
            "\n[red]([bold]Ctrl+C[/bold] to terminate)[/red]"
        )
        logging.warning(msg)
    return signed_links


def download_pack_session(
    id: Union[int, str], duration: List[int], pack_name: Optional[str], out: str
):
    response = request_url(AUDIO_URL, id=id)

    signed_url = get_signed_url(response, duration=duration)
    for name, direct_url in signed_url.items():
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
    download(
        direct_url, name, filename=name, pack_name=pack_name, out=out, is_technique=True
    )


def download(
    direct_url: str,
    name: str,
    *,
    filename: str,
    pack_name: Optional[str] = None,
    out: str,
    is_technique: bool = False,
):
    console.print(f"[green]Downloading {name}[/green]")
    logging.info(f"Downloading {name}")
    logging.info(f"Sending GET request to {direct_url}")
    media = requests.get(direct_url, stream=True)

    if not media.ok:
        media_json = media.json()
        console.print(media_json)
        logging.error(media_json)
        raise click.UsageError(f"HTTP error: status-code = {media.status_code}")

    media_type = media.headers.get("content-type").split("/")[-1]
    filename += f".{media_type}"
    total_length = int(media.headers.get("content-length"))
    chunk_size = 1024

    if not os.path.exists(out) and os.path.isdir(out):
        raise click.BadOptionUsage("--out", f"'{out}' path not valid")

    if pack_name:
        dir_path = os.path.join(out, pack_name)
        pattern = r"Session \d+ of (Level \d+)"
        level = re.findall(pattern, filename)
        if level:
            dir_path = os.path.join(dir_path, level[0])

        if is_technique:
            dir_path = os.path.join(dir_path, "Techniques")
        try:
            os.makedirs(dir_path)
        except FileExistsError:
            pass
        filepath = os.path.join(dir_path, filename)
    else:
        if not os.path.exists(out) and out!="":
            raise click.UsageError(message=f"'{out}' path does not exists.")
        filepath = os.path.join(out, filename)

    if os.path.exists(filepath):
        console.print(
            f"[red]Aborting [/red]download of '{filename}' as it already exists "
            f"at '{filepath}'.\nIf you want to download session please delete [green]'{filepath}'[/green]"
        )
        return
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
            "Cannot find the ID. Please use --id option to provide the ID."
        )
    except IndexError:
        raise click.UsageError(
            "Cannot find the ID. Please use --id option to provide the ID."
        )
    return id


@click.group()
@click.version_option()
def cli():
    """
    Download headspace packs or individual meditation and techniques.
    """
    pass


@cli.command("pack")
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
@click.option(
    "--all", "all_", default=False, is_flag=True, help="Downloads all headspace packs."
)
@click.option(
    "--exclude",
    "-e",
    default="",
    help=(
        "Use with `--all` flag. Location of text file for"
        " links of packs to exclude downloading. Every link should be on separate line."
    ),
)
@shared_cmd(COMMON_CMD)
@shared_cmd(URL_GROUP_CMD)
def pack(
    id: int,
    duration: Union[list, tuple],
    out: str,
    no_techniques: bool,
    no_meditation: bool,
    url: str,
    all_: bool,
    exclude: str,
):
    """
    Download headspace packs with techniques videos.
    """

    if not type(duration) == list or type(duration) == tuple:
        raise click.BadParameter(duration)

    duration = list(set(duration))

    for idx, d in enumerate(duration):
        try:
            d = int(d)
            duration[idx] = d
        except:
            raise click.BadParameter(duration)

        # if not (d == 10 or d == 15 or d == 20 or d == 1 or d == 3):
        #     raise click.BadParameter("Duration could only be list of 1,3,10, 15 or 20")
    if not all_:
        if url == "" and id <= 0:
            raise click.BadParameter("Please provide ID or URL.")
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
    else:
        excluded = []
        if exclude:
            pattern = r"my.headspace.com/packs/([0-9]+)"
            try:
                with open(exclude, "r") as file:
                    links = file.readlines()
            except FileNotFoundError:
                raise click.BadOptionUsage("exclude", "Exclude file not found.")
            for link in links:
                exclude_id = re.findall(pattern, link)
                if exclude_id:
                    excluded.append(int(exclude_id[0]))
                else:
                    console.print(f"[yellow]Unable to parse: {link}[/yellow]")

        console.print("[red]Downloading all packs[/red]")
        logging.info("Downloading all packs")

        group_ids = get_group_ids()

        for pack_id in group_ids:
            if pack_id not in excluded:
                get_pack_attributes(
                    pack_id=pack_id,
                    duration=duration,
                    out=out,
                    no_meditation=no_meditation,
                    no_techniques=no_techniques,
                    all_=True,
                )
            else:
                logging.info(f"Skipping ID: {pack_id} as it is excluded")


@cli.command("download")
@shared_cmd(COMMON_CMD)
@shared_cmd(URL_GROUP_CMD)
def download_single(url: str, out: str, id: int, duration: Union[list, tuple]):
    """
    Download single headspace meditation.
    """
    if url == "" and id <= 0:
        raise click.BadParameter("Please provide ID or URL.")
    pattern = r"my.headspace.com/play/([0-9]+)"
    if not id > 0:
        final_id = find_id(pattern, url)
    else:
        final_id = id
    download_pack_session(final_id, duration, None, out)


@cli.command("file")
def display_file_location():
    """
    Display `bearer_id.txt` file location.
    """
    console.print(f'bearer_id.txt file is located at "{BEARER}"')


@cli.command("init")
def write_bearer():
    """
    Setup `bearer id`
    """
    console.print(
        "Don't know what is bearer_id? Please read "
        "[green]https://github.com/yashrathi-git/headspace-dl#setup[/green]"
    )
    console.print("Please paste bearer_id below:")
    bearer_id = input()

    with open(BEARER, "w") as file:
        file.write(bearer_id)


@cli.command("everyday")
@click.option("--userid", type=str, prompt="User ID")
@click.option(
    "--from",
    "_from",
    type=str,
    default=date.today().strftime("%Y-%m-%d"),
    help="Start download from specific date. DATE-FORMAT=>yyyy-mm-dd",
)
@click.option(
    "--to",
    type=str,
    default=date.today().strftime("%Y-%m-%d"),
    help="Download till a specific date. DATE-FORMAT=>yyyy-mm-dd",
)
@shared_cmd(COMMON_CMD)
def everyday(userid: str, _from: str, to: str, duration: Union[list, tuple], out: str):
    """
    Download everyday headspace.
    """
    date_format = "%Y-%m-%d"
    _from = datetime.strptime(_from, date_format).date()
    to = datetime.strptime(to, date_format).date()

    while _from <= to:
        params = {
            "date": _from.strftime(date_format),
            "userId": userid,
        }
        response = request_url(EVERYDAY_URL, params=params)

        signed_url = get_signed_url(response, duration=duration)

        for name, direct_url in signed_url.items():
            download(direct_url, name, filename=name, out=out)
        _from += timedelta(days=1)


session.close()