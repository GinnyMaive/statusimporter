# statusimporter

A well-named Sharkey to Gotosocial status importer hackily created.

* Change the instance URL at the top of main.py unless you are me
* Create a new application in the GotoSocial Settings UI (eg, https://yourinstance.social/settings)
* Create a file "application.json" with the client ID and client secret you get from there. It should look like this, but you put ur stuff in the quotes!

```
{
    "client_id": "",
    "client_secret": ""
}
```

* Run the thing and it should pop open a browser for you to authenticate. Login to your account. This will save a token into `credentials.json` for you.
  * `credentials.json` has stored credentials authorizing read and write access to your account. You should delete it after you are done importing your statuses. If you need to run the script again, you'll just need to re-authorize (it'll pop open a webpage to do that again)
  * if you're trying to run this headless try installing a text-based browser; `links` seemed to work for me :3
* Set BASE_EXPORT_DIR to the base directory of your Sharkey export - it should at least
have a `notes.json` file and a `files/` folder with any attachments to upload.
* It should start working. By default each request will be followed by a 2 second delay to avoid failed requests due to rate limiting. Hope you weren't too chatty.
* Some statuses are unsupported and will expectedly fail/get skipped:
  * If you mention another user
  * If the status had a poll
  * If the status is direct message
  * If it's a renote
  * If it's a reply to someone else
  * Self-replies should import correctly, unless it's a self-reply *to a note that isn't being imported*
  * Other failures are probably unexpected but not totally surprising.
* While/after running the script will create and update a file `status_map.json`. This keeps track of what it has posted already.
  * If you kill the script or it crashes, it should skip anything already posted.
  * This file also lets the script properly chain together threads of self-replies.
* When you're done you probably want to delete `credentials.json` after you're all done.
  * IDK oauth well enough to know if `application.json` is super scary but it alone won't grant account-level access. Oauth is wild so idk just delete them both if you want, you can get the `application.json` values from the Gotosocial Settings page again anyway.
