## Setup Instructions


<br>

After we have installed `pyheadspace`, this is important step to set it up:

1. Go to https://my.headspace.com/ and login to your account.
2. Press `Ctrl + Shift + I` or `Command + Shift + C` to open dev tools
3. Go to the networks tab and **reload the website**
4. Now look for GET request to https://api.prod.headspace.com
5. In **request header** copy the value of authorization parameter **including the `Bearer` prefix**. **Make sure you copy it from request headers not response headers**. It would look like this:
   ```
   bearer eyJhbGciOi...
   ```

6. Run `headspace file` to get the location of the file. Paste the bearer token from the above step in this file.

**NOTE**:<br />
`authorization` token could invalidate in the future. So if you get an authentication(Unauthorized) error, please repeat the above steps.
