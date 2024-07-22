import time
import logging
import os
import re
import eyed3
import random
from datetime import date, datetime, timedelta
from typing import List, Optional, Union

import jwt
from appdirs import user_data_dir
import click
import requests
from rich.console import Console
from rich.progress import track
from urllib.parse import urlparse, parse_qs
from rich.traceback import install

from pyheadspace.auth import authenticate, prompt

# Counter error
COUNTER_ERROR = 0

# For better tracebacks
install()

BASEDIR = user_data_dir("pyheadspace")
if not os.path.exists(BASEDIR):
    os.makedirs(BASEDIR)
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

if BEARER_ID:
    try:
        USER_ID = jwt.decode(
            BEARER_ID.split(" ")[-1], options={"verify_signature": False}
        )["https://api.prod.headspace.com/hsId"]
    except Exception as e:
        USER_ID = ""
else:
    USER_ID = ""

console = Console()
logger = logging.getLogger("pyHeadspace")

session = requests.Session()

URL_GROUP_CMD = [
    click.option("--id", type=int, default=0, help="ID of video."),
    click.argument("url", type=str, default="", required=False),
]

COMMON_CMD = [
    click.option(
        "-d",
        "--duration",
        help="Duration or list of duration",
        type=int,
        default=[15],
        multiple=True,
    ),
    click.option("--out", default="", help="Download directory"),
    click.option("--language", default="en-US", help="Language of audio files"),
]

def init_header(bearer: str, language: str) -> None:
    """
    Update session headers with authorization and language preference.
    """

    # Define headers with necessary information
    headers = {
        "authority": "api.prod.headspace.com",
        "accept": "application/vnd.api+json",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
            (KHTML, like Gecko) Chrome/89.0.4389.72 Safari/537.36",
        "authorization": bearer,
        "hs-languagepreference": language,
        "sec-gpc": "1",
        "origin": "https://my.headspace.com",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "referer": "https://my.headspace.com/",
        "accept-language": "en-US,en;q=0.9",
    }

    # Update session headers with the defined headers
    session.headers.update(headers)

    # Log the desired language
    logger.info("Desired language {}".format(language))


def shared_cmd(cmd):
    def _shared_cmd(func):
        for option in reversed(cmd):
            func = option(func)
        return func

    return _shared_cmd


def check_bearer_id(bearer_id):
    if "…" in bearer_id:
        return False
    return True


def get_group_ids():
    params = {"category": "PACK_GROUP", "limit": "-1"}
    response = request_url(GROUP_COLLECTION, params=params)
    if (not response) :
        return
    data = response["included"]
    pack_ids = []
    for item in data:
        try:
            id = item["relationships"]["activityGroup"]["data"]["id"]
        except KeyError:
            continue
        pack_ids.append(int(id))
    return sorted(pack_ids)


def request_url(
    url: str, *, id: Union[str, int] = None, mute: bool = False, params=None
):
    if params is None:
        params = {}
    url = url.format(id)
    if not mute:
        logger.info("Sending GET request to {}".format(url))

    response = session.get(url, params=params)
    response_js: dict = {}
    try:
        response_js = response.json()
    except Exception as e:
        global COUNTER_ERROR
        logger.critical(f"status code {response.status_code}")
        logger.critical(f"error: {e}")
        console.print(f"status code {response.status_code}")
        COUNTER_ERROR += 1
        if(COUNTER_ERROR > 20):
            raise click.Abort()
        else:
            time.sleep(COUNTER_ERROR*2)
    if not response.ok:
        if "errors" in response_js.keys():
            errors = response_js["errors"]
            logger.error(errors)
            if response.status_code == 401:
                console.print(
                    "\n[red]Not Authenticated : Unable to login to headspace account[/red]"
                )
                console.print("Run [green]headspace login[/green] first.")
            elif response.status_code == 403:
                console.print(
                    "\n[red]Unautorized : Not allow to access to resources[/red]"
                )
            else:
                console.print(errors)
        else:
            console.print(response_js)
            logger.error(response_js)
        return
        #raise click.UsageError(f"HTTP error: status-code = {response.status_code}")
    return response_js


def round_off(time: Union[int, float]):
    orig_duration = time / 60000

    time = time // 60000
    unit_place = time % 10

    if 0 < unit_place < 5:
        time -= unit_place
    elif unit_place > 5:
        time -= unit_place - 5
    if time == 0:
        if (orig_duration >= 2) and (orig_duration < 3):
            time = 2
        elif (orig_duration >= 3) and (orig_duration < 4):
            time = 3
        elif (orig_duration >= 4) and (orig_duration <= 5):
            time = 5
        else:
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
    check: bool = False
):
    response = request_url(PACK_URL, id=pack_id)
    if (not response) :
        return
    attributes: dict = response["data"]["attributes"]
    _pack_name: str = attributes["name"]
    # Because it's only used for filenames, and | is mostly not allowed in filenames
    _pack_name = _pack_name.replace("|", "-")

    if all_ and not check:
        exists = os.path.exists(os.path.join(out, _pack_name))
        if exists:
            console.print(f"{_pack_name} already exists [red]skipping... [/red]")
            return
    # Logging
    logger.info(f"Downloading pack, name: {_pack_name}")

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
        response = request_url(SIGN_URL, id=sign_id)
        if (not response) :
            return
        
        direct_url = response["url"]
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
        logger.warning(msg)
    return signed_links


def download_pack_session(
    id: Union[int, str],
    duration: List[int],
    pack_name: Optional[str],
    out: str,
    filename_suffix=None,
):
    response = request_url(AUDIO_URL, id=id)
    if (not response) :
        return
    signed_url = get_signed_url(response, duration=duration)

    for name, direct_url in signed_url.items():
        if filename_suffix:
            name += filename_suffix
        filePath=download(direct_url, name, filename=name, pack_name=pack_name, out=out)
        if(filePath):
            addTags(filePath,name,pack_name,id)



def download_pack_techniques(
    technique_id: Union[int, str],
    *,
    pack_name: Optional[str] = None,
    out: str,
    filename_suffix=None,
):
    response = request_url(TECHNIQUE_URL, id=technique_id)
    if (not response) :
        return
    name = response["data"]["attributes"]["name"]
    if filename_suffix:
        name += filename_suffix
    for item in response["included"]:
        if not item["type"] == "mediaItems":
            continue
        if item["attributes"]["mimeType"] == "video/mp4":
            sign_id = item["id"]
            break
    response = request_url(SIGN_URL, id=sign_id)
    if (not response) :
        return
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
    logger.info(f"Sending GET request to {direct_url}")
    media = requests.get(direct_url, stream=True)

    if not media.ok:
        media_json = media.json()
        console.print(media_json)
        logger.error(media_json)
        raise click.UsageError(f"HTTP error: status-code = {media.status_code}")

    media_type = media.headers.get("content-type").split("/")[-1]
    filename += f".{media_type}"
    total_length = int(media.headers.get("content-length"))
    chunk_size = 1024

    if not os.path.exists(out) and os.path.isdir(out):
        raise click.BadOptionUsage("--out", f"'{out}' path not valid")

    if pack_name:
        # Clean folder name
        dir_path = os.path.join(out, re.sub( r"[^A-Za-z0-9]", "", pack_name, 0))
        pattern = r"Session \d+ of (Level \d+)"
        level = re.findall(pattern, filename)
        if level:
            dir_path = os.path.join(dir_path, level[0])

        if is_technique:
            dir_path = os.path.join(dir_path, "Techniques")

        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        filepath = os.path.join(dir_path, filename)
    else:
        if not os.path.exists(out) and out != "":
            raise click.UsageError(message=f"'{out}' path does not exists.")
        filepath = os.path.join(out, filename)

    if os.path.exists(filepath):
        console.print(f"'{filename}' already exists [red]skipping...[/red]")
        return

    failed_tries = 0
    max_tries = 5
    while failed_tries <= max_tries:
        downloaded_length = 0
        with open(filepath, "wb") as file:
            for chunk in track(
                media.iter_content(chunk_size=chunk_size),
                description=f"[red]Downloading...[/red]",
                total=total_length // chunk_size,
            ):
                downloaded_length += len(chunk)
                file.write(chunk)
                file.flush()

        if downloaded_length != total_length:
            failed_tries += 1
            console.print(
                f"[red]Download failed. Retrying {failed_tries} out of {max_tries}...[/red]",
            )
            media.close()
            media = requests.get(direct_url, stream=True)
        else:
            break

    if failed_tries > max_tries:
        console.print(f"[red]Failed to download {filename}[/red]\n")
        logger.error(f"Failed to download {filename}")
        os.remove(filepath)
        return False
    else:
        return filepath

def addTags(filepath: str,title:str,album:str,track_number:int=0,total_tracks:int=0):
    """
    Adds tags to an audio file specified by `filepath`. The tags added include 
    `title`, `album`, `artist`, and `track_num` (if `total_tracks` and 
    `track_number` are provided). 

    Args:
        filepath (str): The path to the audio file.
        title (str): The title of the audio file.
        album (str): The name of the album the audio file belongs to.
        track_number (int, optional): The track number of the audio file. 
            Defaults to 0.
        total_tracks (int, optional): The total number of tracks in the album. 
            Defaults to 0.

    Returns:
        None
    """
    audiofile = eyed3.load(filepath)
    if not audiofile.tag:
        audiofile.initTag()
    audiofile.tag.title = title
    audiofile.tag.album = album
    audiofile.tag.artist = "headspace"
    if(total_tracks!=0 and track_number!=0):
        audiofile.tag.track_num = (track_number, total_tracks)
    elif(total_tracks==0 and track_number!=0):
        audiofile.tag.track_num = track_number
    audiofile.tag.save()

def find_id(pattern: str, url: str):
    try:
        id = int(re.findall(pattern, url)[-1])
    except ValueError:
        raise click.UsageError("Cannot find the ID. Use --id option to provide the ID.")
    except IndexError:
        raise click.UsageError("Cannot find the ID. Use --id option to provide the ID.")
    return id


@click.group()
@click.version_option()
@click.option(
    "--verbose", "-v", is_flag=True, help="Enable verbose mode.", default=False
)
def cli(verbose):
    """
    Download headspace packs or individual meditation and techniques.
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.CRITICAL)
    # We don't want log messages from requests and urllib3 unless they are atleast warning
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    if verbose:
        console.print("[bold]Verbose mode enabled[/bold]")


@cli.command("help")
@click.argument("command", required=False)
@click.pass_context
def help_(ctx, command):
    """
    Display help information
    """
    if not command:
        click.echo(ctx.parent.get_help())
        return

    cmd = cli.get_command(ctx, command)

    if not cmd:
        raise click.ClickException("No such command: {}".format(command))

    click.echo(cmd.get_help(ctx))


def get_legacy_id(new_id):
    logger.info("Getting entity ID")
    url = "https://api.prod.headspace.com/content-aggregation/v2/content/view-models/content-info/skeleton"
    response = request_url(url, params={"contentId": new_id, "userId": USER_ID})
    if (not response) :
        return
    return response["entityId"]


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
    "--check", "check", default=False, is_flag=True, help="Check all headspace packs."
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
    check: bool,
    language: str,
):
    """
    Download headspace packs with techniques videos.
    """
    init_header(BEARER_ID, language)

    duration = list(set(duration))
    pattern = r"my.headspace.com/modes/(?:meditate|focus)/content/([0-9]+)"

    if not all_:
        if url == "" and id <= 0:
            raise click.BadParameter("Please provide ID or URL.")
        if url:
            id = find_id(pattern, url)
            id = get_legacy_id(id)
        else:
            id = get_legacy_id(id)
        get_pack_attributes(
            pack_id=id,
            duration=duration,
            out=out,
            no_meditation=no_meditation,
            no_techniques=no_techniques,
            check=check,
        )
    else:
        excluded = []
        if exclude:
            try:
                with open(exclude, "r") as file:
                    links = file.readlines()
            except FileNotFoundError:
                raise click.BadOptionUsage("exclude", "Exclude file not found.")
            for link in links:
                exclude_id = re.findall(pattern, link)
                if exclude_id:
                    excluded.append(int(get_legacy_id(int(exclude_id[0]))))
                else:
                    console.print(f"[yellow]Unable to parse: {link}[/yellow]")

        console.print("[red]Downloading all packs[/red]")
        logger.info("Downloading all packs")

        group_ids = get_group_ids()
        random.shuffle(group_ids) # more resilient

        for pack_id in group_ids:
            if pack_id not in excluded:
                get_pack_attributes(
                    pack_id=pack_id,
                    duration=duration,
                    out=out,
                    no_meditation=no_meditation,
                    no_techniques=no_techniques,
                    all_=True,
                    check=check,
                )
            else:
                logger.info(f"Skipping ID: {pack_id} as it is excluded")


@cli.command("download")
@shared_cmd(COMMON_CMD)
@click.argument("url", type=str)
def download_single(url: str, out: str, duration: Union[list, tuple], language:str):
    """
    Download single headspace session.
    """
    init_header(BEARER_ID,language)
    pattern = r"my.headspace.com/player/([0-9]+)"
    try:
        pack_id = find_id(pattern, url)
    except click.UsageError:
        raise click.UsageError("Unable to parse URL.")

    try:
        index = int(parse_qs(urlparse(url).query)["startIndex"][0])
    except KeyError:
        index = 0
    except ValueError:
        raise click.Abort("Unable to parse startIndex.")

    response = request_url(PACK_URL, id=pack_id)
    if (not response) :
        return
    attributes: dict = response["data"]["attributes"]
    pack_name: str = attributes["name"]

    data = response["included"]
    data = data[index]
    if data["type"] == "orderedActivities":
        id = data["relationships"]["activity"]["data"]["id"]
        download_pack_session(
            id, duration, None, out=out, filename_suffix=" - {}".format(pack_name)
        )
    elif data["type"] == "orderedTechniques":
        id = data["relationships"]["technique"]["data"]["id"]
        download_pack_techniques(
            id, pack_name=None, out=out, filename_suffix=" - {}".format(pack_name)
        )


@cli.command("file")
def display_file_location():
    """
    Display `bearer_id.txt` file location.
    """
    console.print(f'bearer_id.txt file is located at "{BEARER}"')


def write_bearer(bearer_id):
    """
    Setup `bearer id`
    """

    if not check_bearer_id(bearer_id):
        console.print(
            "\n[red]The bearer ID is invalid. It "
            "is incomplete as it contains '…' in it[/red]. \n[green]Please copy the"
            " ID by right click on the attribute 'authorization' and "
            "then 'copy value' to copy full value.[/green]"
        )
        raise click.UsageError("Bearer ID not complete")

    with open(BEARER, "w") as file:
        file.write(bearer_id)


@cli.command("everyday")
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
def everyday(_from: str, to: str, duration: Union[list, tuple], out: str, language:str):
    """
    Download everyday headspace.
    """
    init_header(BEARER_ID,language)
    userid = USER_ID
    date_format = "%Y-%m-%d"
    _from = datetime.strptime(_from, date_format).date()
    to = datetime.strptime(to, date_format).date()

    while _from <= to:
        params = {
            "date": _from.strftime(date_format),
            "userId": userid,
        }
        response = request_url(EVERYDAY_URL, params=params)
        if (not response) :
            return
        signed_url = get_signed_url(response, duration=duration)

        for name, direct_url in signed_url.items():
            filePath=download(direct_url, name, filename=name, out=out)
            if(filePath):
                addTags(filePath,name,"everyday")
        _from += timedelta(days=1)


@cli.command("login")
@click.option(
    "--email",
    "_email",
    type=str,
    help="Email for login"
)
@click.option(
    "--password",
    "_password",
    type=str,
    help="Credentials for login"
)
def login(_email: str, _password: str):
    if _email is not None and _password is not None:
        email, password = _email, _password
    else:    
        email, password = prompt()
    bearer_token = authenticate(email, password)
    if not bearer_token:
        raise click.Abort()
    write_bearer(bearer_token)
    console.print("[green]:heavy_check_mark:[/green] Logged in successfully!")

# For launch program directly, useful for debugging
cli()
session.close()
