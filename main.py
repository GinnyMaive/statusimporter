import os
import json
import time
# I'd use ulid but it'd be silly to require that dependency just for dry runs :3
import uuid
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# Configuration
DELAY_BETWEEN_REQUESTS = 2 # seconds
INSTANCE_BASE_URL = 'https://transister.social/'
AUTHORIZATION_URL = INSTANCE_BASE_URL + 'oauth/authorize'
TOKEN_URL = INSTANCE_BASE_URL + 'oauth/token'
STATUS_URL = INSTANCE_BASE_URL + 'api/v1/statuses'
MEDIA_URL = INSTANCE_BASE_URL + 'api/v1/media'

CREDENTIALS_FILE = 'credentials.json'
APPLICATION_FILE = 'application.json'
STATUS_MAPPING_FILE = 'status_map.json'
# These will be read and set from APPLICATION_FILE
CLIENT_ID = ''
CLIENT_SECRET = ''
REDIRECT_URI = 'http://localhost:8080/callback'

# Screw it, use a global, computer science is my passion
SKIPPED = 0

def save_credentials(token_data):
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(token_data, f)

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    return None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/callback'):
            query = self.path.split('?', 1)[-1]
            params = dict(qc.split('=') for qc in query.split('&'))
            self.server.auth_code = params.get('code')
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'Authorization successful. You can close this window.')
        else:
            self.send_response(404)
            self.end_headers()

def get_auth_code():
    server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
    auth_url = (
        f'{AUTHORIZATION_URL}?response_type=code&client_id={CLIENT_ID}'
        f'&redirect_uri={REDIRECT_URI}&scope=read%20write'
    )
    webbrowser.open(auth_url)
    print('Please authorize in the browser...')
    server.handle_request()
    return server.auth_code

def get_token(auth_code):
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scopes': 'read write',
    }
    response = requests.post(TOKEN_URL, data=data)
    response.raise_for_status()
    return response.json()

def upload_media(creds, file_path, description):
    access_token = creds.get('access_token')
    if not access_token:
        raise ValueError('No access token found in credentials.')
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    payload = {
        'description': description
    }
    files = {'file': open(file_path, 'rb')}
    response = requests.post(
        MEDIA_URL,
        headers=headers,
        data=payload,
        files=files)
    response.raise_for_status()
    print('Uploaded media:', response.json())
    return response.json()

def post_status_dryrun(creds, payload):
    print('DRY RUN - making some stuff up')
    fake_id = uuid.uuid4()
    return {
        'uri': INSTANCE_BASE_URL + 'users/gintoxicating/statuses/' + str(fake_id),
        'url': INSTANCE_BASE_URL + '@gintoxicating/statuses/' + str(fake_id),
        'id': str(fake_id)}

def get_existing_status_mapping(sharkey_id):
    if os.path.exists(STATUS_MAPPING_FILE):
        with open(STATUS_MAPPING_FILE, 'r') as f:
            mapping = json.load(f)
            return mapping.get(sharkey_id)
    return None

def save_status_mapping(sharkey_id, opensocial_id, opensocial_url):
    print('Saving mapping:', sharkey_id, '->', opensocial_id)
    mapping = {}
    if os.path.exists(STATUS_MAPPING_FILE):
        with open(STATUS_MAPPING_FILE, 'r') as f:
            mapping = json.load(f)
    if sharkey_id in mapping:
        print('!@@@!@@*** Warning: overwriting existing mapping for', sharkey_id)
    mapping[sharkey_id] = {'opensocial_id': opensocial_id, 'opensocial_url': opensocial_url}
    with open(STATUS_MAPPING_FILE, 'w') as f:
        json.dump(mapping, f, indent=2)

def post_status(creds, payload):
    access_token = creds.get('access_token')
    if not access_token:
        raise ValueError('No access token found in credentials.')
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(
        STATUS_URL,
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    return response.json()

def authorize():
    creds = load_credentials()
    if creds:
        print('Credentials loaded')
    else:
        auth_code = get_auth_code()
        token_data = get_token(auth_code)
        save_credentials(token_data)
        print('Credentials saved')
        creds = load_credentials()
    return creds

def this_note_sucks_sorry(note, reason):
    global SKIPPED
    print('***** Note', note.get('id'), 'will be skipped (reason:', reason, ')\n           ', note.get('text'))
    SKIPPED += 1

def process_note(creds, note):
    # Simple cases to skip, at least for now.
    if note.get('files') or note.get('fileIds'):
        this_note_sucks_sorry(note, 'has files attached')
        return
    if note.get('renoteId'):
        this_note_sucks_sorry(note, 'is a renote')
        return
    if note.get('poll'):
        this_note_sucks_sorry(note, 'has a poll')
        return
    if note.get('visibleUserIds'):
        this_note_sucks_sorry(note, 'has visibleUserIds and idk what those are')
        return
    # TODO: filter out notes that mention non-self users somehow. is regexp the best way?
    
    payload = {
        'status': note.get('text'),
        'scheduled_at': note.get('createdAt')
    }

    payload['local_only'] = note.get('localOnly', False)
    if note.get('cw'):
        payload['spoiler_text'] = note.get('cw')
    # From https://activitypub.software/TransFem-org/Sharkey/-/blob/develop/packages/backend/src/types.ts?ref_type=heads
    # Sharkey noteVisibilities = ['public', 'home', 'followers', 'specified']
    # gotosocial visibilities = public, unlisted, private (followers-only), mutuals_only, direct
    # This will only import public, unlisted, and private (followers-only) notes
    if note.get('visibility') == 'public':
        payload['visibility'] = 'public'
    elif note.get('visibility') == 'home':
        payload['visibility'] = 'unlisted'
    elif note.get('visibility') == 'followers':
        payload['visibility'] = 'private'
    elif note.get('visibility') == 'specified':
        this_note_sucks_sorry(note, 'has specified-user visibility and i don\'t want to implement that')
        return

    if get_existing_status_mapping(note.get('id')):
        this_note_sucks_sorry(note, 'already has a mapping, so it was already posted')
        return

    if note.get('replyId'):
        note_map = get_existing_status_mapping(note.get('replyId'))
        if note_map:
            payload['in_reply_to_id'] = note_map.get('opensocial_id')
        else:
            this_note_sucks_sorry(note, 'is a reply but the parent note was not found, so skipping')
            return

    print('-----')
    print('cool note: ', note)
    print(payload)
    # response = post_status(creds, payload)
    response = post_status_dryrun(creds, payload)
    print('   ID: ', response.get('id'))
    print('   URI: ', response.get('uri'))
    print('raw response:', response)
    save_status_mapping(note.get('id'), response.get('id'), response.get('url'))
    print('  sleeping', DELAY_BETWEEN_REQUESTS, 'seconds to respect rate limits')
    time.sleep(DELAY_BETWEEN_REQUESTS)
    print('-----')
    return


def set_app_config():
    if os.path.exists(APPLICATION_FILE):
        global CLIENT_ID, CLIENT_SECRET
        with open(APPLICATION_FILE, 'r') as f:
            app_config = json.load(f)
            CLIENT_ID = app_config.get('client_id', CLIENT_ID)
            CLIENT_SECRET = app_config.get('client_secret', CLIENT_SECRET)
    else:
        print(APPLICATION_FILE, 'should exist with your client_id and client_secret!')

def print_notes():
    set_app_config()
    creds = authorize()
    if not creds:
        print('No credentials found. Please authorize first.')
        return
    notes_file = 'notes-test.json'
    if os.path.exists(notes_file):
        with open(notes_file, 'r') as f:
            notes = json.load(f)
            for note in notes.get('notes', []):
                process_note(creds, note)
    else:
        print(f'{notes_file} not found.')
    print('  **! Skipped', SKIPPED, 'notes!')

def main():
    print_notes()

if __name__ == '__main__':
    main()