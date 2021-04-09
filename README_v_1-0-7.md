## Setup Instructions
For version 1.x.x <br>
For latest version documentation visit [here](https://github.com/yashrathi-git/pyHeadspace/blob/main/README.md)

<br>

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