# pyHeadspace
Python command line script to download heaspace packs, singles or everyday headspace OR download all packs at once.
<p align="center">
<img src = "https://raw.githubusercontent.com/yashrathi-git/headspace-dl/main/images/demo-f.gif" alt = "demo">
</p>


## Installation
### Install with pip
```sh
pip install pyheadspace
```
### Install latest version
1. Clone this repo:
   ```sh
   git clone https://github.com/yashrathi-git/headspace-dl 
   ```
2. Navigate to the cloned folder.
3. To install run:
   ```sh
   pip install --editable .
   ```

## Setup
After we have installed `headspace-dl`, this is important step to set it up:

1. Go to https://my.headspace.com/ and login to your account.
2. Press `Ctrl + Shift + I` or `Command + Shift + C` to open dev tools
3. Go to the networks tab and **reload the website**
4. Now look for GET request to https://api.prod.headspace.com
5. In **request header** copy the value of authorization parameter. **Make sure you copy it from request headers not response headers**. It would look like this:
   ```
   bearer eyJhbGciOi...
   ```

6. Run:
   ```sh
   headspace init
   ```
7. Paste `authorization` value(bearer id) here. Setup is done!


**NOTE**:<br />
`authorization` token could invalidate in the future. So if you get an authentication(Unauthorized) error, please repeat the above steps. 

## Usage
First, make sure to follow <a href="#setup">setup instructions</a><br>
### Download all packs at once
```sh
# Download all packs of duration 15 minutes
headspace pack --all --duration 15

# Download all packs of duration 10,20 minutes
headspace pack --all --duration "[10,20]"
```
**Exclude specific packs from downloading**
<br />

To exclude specific packs from downloading use `--exclude` option.
<br />
It expects location of text file for links of packs to exclude downloading. Every link should be on separate line.<br><br>
**links.txt**:
```
https://my.headspace.com/packs/5
https://my.headspace.com/packs/6
```
**command**
```sh
headspace packs --all --exclude links.txt
```
This would download all packs except the ones in `links.txt` file

### Downloading Headspace pack
```sh
headspace pack <URL> [Options]
```
It expects URL in format `https://my.headspace.com/packs/<int>`

<br />

**BASIC USAGE**
```sh
# Download with all session of duration 15 minutes
headspace pack https://my.headspace.com/packs/33 --duration 15 

# Download sessions of multiple duration
headspace pack https://my.headspace.com/packs/33 --duration "[20, 15, 10]"    

```
**Options:**
```sh
--id INTEGER         ID of video.
-d, --duration TEXT  Duration or list of duration
--no_meditation      Only download meditation session without techniques
                    videos.
--no_techniques      Only download techniques and not meditation sessions.
--out TEXT           Download directory
--all                Downloads all headspace packs.
-e, --exclude TEXT   Use with `--all` flag. Location of text file with links
                    of packs to exclude downloading. Every link should be
                    on separate line.
--help               Show this message and exit.

```
**NOTE**:<br />
`authorization` token(bearer id) could invalidate after some time. So if you get an authentication(Unauthorized) error, please repeat <a href="#setup">setup</a> instructions.

### Download single session
```sh
headspace download <URL> [options]
```

It expects URL in format `https://my.headspace.com/play/<int>`

<br />

**BASIC USAGE**
```sh
headspace download https://my.headspace.com/play/520 --duration 15
# Download sessions of multiple durations
headspace download https://my.headspace.com/play/520 --duration "[15,20]"
```
**Options:**
```sh
--out TEXT           Download directory.
--id INTEGER         ID of the video. Not required if URL is provided.
-d, --duration       Duration or list of duration
--help               Show this message and exit.
```
**NOTE**:<br />
`authorization` token(bearer id) could invalidate after some time. So if you get an authentication(Unauthorized) error, please repeat <a href="#setup">setup</a> instructions.

### Download everyday meditations
```sh
headspace everyday [OPTIONS]
```
**How to get your user id?** <br>
1. Go to https://my.headspace.com/everyday-headspace/info
2. Open developer tools using `Ctrl + Shift + I` or `Command + Shift + C`
3. Go to network tab and reload the webpage
4. Find a request made to URL: https://api.prod.headspace.com/content/view-models/everyday-headspace-banner
5. You would find your userId as query parameter in the URL.
<br>

**BASIC USAGE**
```sh
# Downloads today's meditation
headspace everyday --userid <YOUR USER ID>

# Download everyday meditation of specific time period.
# DATE FORMAT: yyyy-mm-dd
headspace everyday --from 2021-03-01 --to 2021-03-20 --userid <YOUR USER ID>
```
**Options**
```
--userid TEXT
--from TEXT          Start download from specific date. DATE-FORMAT=>yyyy-
                    mm-dd
--to TEXT            Download till a specific date. DATE-FORMAT=>yyyy-mm-dd
-d, --duration TEXT  Duration or list of duration
--out TEXT           Download directory
--help               Show this message and exit.
```

### Display location for `bearer_id.txt` file
```sh
headspace file
```

### Add `bearer id` for authentication
```sh
headspace init
```
