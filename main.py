from datetime import datetime
import glob
import os
import json
import time
# I'd use ulid but it'd be silly to require that dependency just for dry runs :3
import uuid
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# Configuration
INSTANCE_BASE_URL = 'https://transister.social/'
DELAY_BETWEEN_REQUESTS = 2 # seconds
# TODO: turn into a flag or something
BASE_EXPORT_DIR = 'exports/test/' # where notes.json and the files/ subdir are located
DRY_RUN = True

AUTHORIZATION_URL = f'{INSTANCE_BASE_URL}oauth/authorize'
TOKEN_URL = f'{INSTANCE_BASE_URL}oauth/token'
STATUS_URL = f'{INSTANCE_BASE_URL}api/v1/statuses'
MEDIA_URL = f'{INSTANCE_BASE_URL}api/v1/media'

CREDENTIALS_FILE = f'{BASE_EXPORT_DIR}credentials.json'
APPLICATION_FILE = f'{BASE_EXPORT_DIR}application.json'
STATUS_MAPPING_FILE = f'{BASE_EXPORT_DIR}status_map.json'
LOG_FILE = f'{BASE_EXPORT_DIR}statusimporter.log'

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

def handle_file_situation(creds, file):
    file_path = try_to_find_file(f'''{BASE_EXPORT_DIR}files/{file.get('name')}''')
    sharkey_media_id = file.get('id')
    log_to_logfile(f'Media id {sharkey_media_id} path {file_path}')
    gts_media_id = None
    if DRY_RUN:
        gts_media = upload_media_dryrun(creds, file_path, description=file.get('comment'))
    else:
        gts_media = upload_media(creds, file_path, file.get('comment'))
    save_status_mapping(file.get('id'), gts_media.get("id"), gts_media.get('url'))
    return gts_media_id

def try_to_find_file(file_path):
    if os.path.exists(file_path):
        return file_path
    glob_str = f'{file_path}.*'
    log_to_logfile(f'File not found at {file_path}, trying glob {glob_str}')
    other_files = glob.glob(glob_str)
    if len(other_files) == 1:
        return other_files[0]
    error_text = f'File not found: {file_path} or glob returned too many results: {other_files}'
    log_to_logfile(error_text)
    return None

def upload_media_dryrun(creds, file_path, description):
    log_to_logfile('DRY RUN - making some stuff up')
    fake_id = uuid.uuid4()
    return {
        'url': f'{INSTANCE_BASE_URL}fileserver/{fake_id}/attachments/{fake_id}/original/attachment.jpeg',
        'id': str(fake_id)}

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
    log_to_logfile(f'Attempting to upload {file_path} with payload: {payload}')
    files = {'file': open(file_path, 'rb')}
    response = requests.post(
        MEDIA_URL,
        headers=headers,
        data=payload,
        files=files)
    response.raise_for_status()
    log_to_logfile(f'Uploaded media: {response.json()}')
    return response.json()

def post_status_dryrun(creds, payload):
    log_to_logfile('DRY RUN - making some stuff up')
    fake_id = uuid.uuid4()
    return {
        'uri': f'{INSTANCE_BASE_URL}users/gintoxicating/statuses/{fake_id}',
        'url': f'{INSTANCE_BASE_URL}@gintoxicating/statuses/{fake_id}',
        'id': str(fake_id)}

def log_to_logfile(message):
    full_message = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {message}'
    print(full_message)
    with open(LOG_FILE, 'a+') as f:
        f.write(full_message + '\n')

def get_existing_status_mapping(sharkey_id):
    if os.path.exists(STATUS_MAPPING_FILE):
        with open(STATUS_MAPPING_FILE, 'r') as f:
            mapping = json.load(f)
            return mapping.get(sharkey_id)
    return None

def save_status_mapping(sharkey_id, opensocial_id, opensocial_url):
    log_to_logfile(f'Saving mapping: {sharkey_id} -> {opensocial_id}')
    mapping = {}
    if os.path.exists(STATUS_MAPPING_FILE):
        with open(STATUS_MAPPING_FILE, 'r') as f:
            mapping = json.load(f)
    if sharkey_id in mapping:
        log_to_logfile(f'!@@@!@@*** Warning: overwriting existing mapping for {sharkey_id}')
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
        log_to_logfile('Credentials loaded')
    else:
        auth_code = get_auth_code()
        token_data = get_token(auth_code)
        save_credentials(token_data)
        log_to_logfile('Credentials saved')
        creds = load_credentials()
    return creds

def this_note_sucks_sorry(note, reason):
    global SKIPPED
    message = f'''Note {note.get('id')} will be skipped (reason: {reason})
                {note.get('text')}'''
    log_to_logfile(message)
    SKIPPED += 1

def process_note(creds, note):
    # Simple cases to skip, at least for now.
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

    if note.get('files') or note.get('fileIds'):
        # files contains the details needed to upload the media, and fileIds is just the IDs
        for file in note.get('files', []):
          if not get_existing_status_mapping(file.get('id')):
            handle_file_situation(creds, file)
          gts_media_id = get_existing_status_mapping(file.get('id')).get('opensocial_id')
          if not gts_media_id:
            this_note_sucks_sorry(note, f'uploading file {file.get("name")} failed')
          if 'media_ids' not in payload:
            payload['media_ids'] = []
          payload['media_ids'].append(gts_media_id)
          log_to_logfile(f'  attached media {gts_media_id} for file {file.get("id")}; new payload: {payload}')

    log_to_logfile('-----')
    log_to_logfile(f'cool note: {note}')
    log_to_logfile(payload)
    response = None
    if DRY_RUN:
      response = post_status_dryrun(creds, payload)
    else:
      response = post_status(creds, payload)
    log_to_logfile(f'''   ID: {response.get('id')}''')
    log_to_logfile(f'''   URI: {response.get('uri')}''')
    log_to_logfile(f'raw response: {response}')
    save_status_mapping(note.get('id'), response.get('id'), response.get('url'))
    log_to_logfile(f'  sleeping {DELAY_BETWEEN_REQUESTS} seconds to respect rate limits')
    time.sleep(DELAY_BETWEEN_REQUESTS)
    log_to_logfile('-----')
    return


def set_app_config():
    if os.path.exists(APPLICATION_FILE):
        global CLIENT_ID, CLIENT_SECRET
        with open(APPLICATION_FILE, 'r') as f:
            app_config = json.load(f)
            CLIENT_ID = app_config.get('client_id', CLIENT_ID)
            CLIENT_SECRET = app_config.get('client_secret', CLIENT_SECRET)
    else:
        print(f'{APPLICATION_FILE} should exist with your client_id and client_secret!')

def export_filename(filename):
    return f'{BASE_EXPORT_DIR}{filename}'

def print_notes():
    notes_file = export_filename('notes.json')
    log_to_logfile(f'Starting up import run of {BASE_EXPORT_DIR}; notes file: {notes_file}')
    set_app_config()
    creds = authorize()
    if not creds:
        print('No credentials found. Please authorize first.')
        return
    if os.path.exists(notes_file):
        with open(notes_file, 'r') as f:
            notes = json.load(f)
            for note in notes.get('notes', []):
                process_note(creds, note)
    else:
        print(f'{notes_file} not found.')
    log_to_logfile(f'  **! Skipped {SKIPPED} notes!')
    log_to_logfile(f'Log file: {LOG_FILE}')

def main():
    print_notes()

if __name__ == '__main__':
    main()