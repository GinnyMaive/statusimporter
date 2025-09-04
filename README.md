# statusimporter

A well-named Sharkey to GoToSocial status importer hackily created.

* Before importing, you might want to import any/all custom emojis your posts use. If they are present, they will be used. If they are absent, you'll just see the old emoji short code. Adding them *after* importing will not use them in old statuses.
  * How to do this is out of scope for this tool, but you can use [Slurp](https://github.com/VyrCossont/slurp)
  * You can also just be fine with it and move on with life, which is what I did! The statuses will still import just without as much flair.
* Set `BASE_EXPORT_DIR` to the base directory of your Sharkey export - it should at least
have a `notes.json` file and a `files/` folder with any attachments to upload.
* Create a new application in the GoToSocial Settings UI (eg, https://yourinstance.social/settings)
* In that folder, create a file `application.json` with the client ID and client secret you get from there. It should look like this, but you put ur stuff in the quotes!

```
{
    "client_id": "",
    "client_secret": ""
}
```

* Run the thing and it should pop open a browser for you to authenticate. Login to your account. This will save a token into `credentials.json` for you.
  * `credentials.json` has stored credentials authorizing read and write access to your account. You should delete it after you are done importing your statuses. If you need to run the script again, you'll just need to re-authorize (it'll pop open a webpage to do that again)
  * if you're trying to run this headless try installing a text-based browser; `links` seemed to work for me :3
* By default it will run in dry mode to give you a chaotic idea of what will happen. That's
probably smart to do first.
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
* If the dry run looks reasonable enough:
  * edit the `DRY_RUN` variable to False
  * remove the `status_map.json` file in your `BASE_EXPORT_DIR` to reset the importer state
  and remove the dry run fake IDs.
* Buckle up it's gonna post some statuses! Good luck!
* When you're done you probably want to delete `credentials.json` after you're all done.
  * IDK oauth well enough to know if `application.json` is super scary but it alone won't grant account-level access. Oauth is wild so idk just delete them both if you want, you can get the `application.json` values from the GoToSocial Settings page again anyway.


## FAQ

#### What the hell this is awful

Yes!

#### You should ...

Probably. I especially should improve logging if only because it's really really bad
because it's the slapped-together output I used while writing the tool.

Ideally at least it could spit out a simple map of `old_url` to either the `new_url`
or the error/failure. You could probably do this pretty easily with the `status_map.json`
file except for capturing statuses which failed to migrate.

Oh and some rough approximation of how far it is (like notes processed out of notes total in the `notes.json` file).

#### Why not just use [Slurp](https://github.com/VyrCossont/slurp)

Slurp didn't work correctly with Sharkey exports.

#### Why not just convert Sharkey exports to be Slurp compatible?

Converting json to json and moving files around to match some spec I don't really know
seemed like a bummer. At least this way I got a bit of experience working with the GTS API
which might provoke me to do more stuff :3

#### You should have used Go! GoToSocial uses Go!

If I knew Go, yes. But if I had tried to build this in Go it would not exist.

#### You should be ashamed of this code!

Yeah I agree and I am. But it exists and seems to have worked for my statuses, so yay for me.