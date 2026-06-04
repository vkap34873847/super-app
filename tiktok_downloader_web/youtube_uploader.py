#!/usr/bin/env python3
"""
YouTube Upload Utility for Super-App
Uploads dubbed videos to YouTube using OAuth 2.0 flow.
"""
import argparse
import httplib
import httplib2
import os
import sys
import random
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error,
    IOError,
    httplib.NotConnected,
    httplib.IncompleteRead,
    httplib.ImproperConnectionState,
    httplib.CannotSendRequest,
    httplib.CannotSendHeader,
    httplib.ResponseNotReady,
    httplib.BadStatusLine,
)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the Google API Console at https://console.cloud.google.com/.
# For more information about the client_secrets.json file format, see:
# https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
TOKEN_FILE = "youtube_upload_token.json"

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")


def get_authenticated_service():
    """Authorize the request and store authorization credentials."""
    creds = None
    # The file youtube_upload_token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(
                    f"Error: {CLIENT_SECRETS_FILE} not found. "
                    "Please download it from Google Cloud Console and place it in the current directory."
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)


def initialize_upload(youtube, options):
    """Initialize and execute the video upload."""
    tags = None
    if options.keywords:
        tags = [k.strip() for k in options.keywords.split(",")]

    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category,
        ),
        status=dict(privacyStatus=options.privacyStatus),
    )

    # Call the API's videos.insert method to create and upload the video.
    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True),
    )

    resumable_upload(insert_request)


# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(insert_request):
    """Upload the video with retry logic."""
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()
            if response is not None:
                if "id" in response:
                    print(f'Video id "{response["id"]}" was successfully uploaded.')
                    return response["id"]
                else:
                    exit(f"The upload failed with an unexpected response: {response}")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")

            max_sleep = 2**retry
            sleep_seconds = random.random() * max_sleep
            print(f"Sleeping {sleep_seconds:f} seconds and then retrying...")
            time.sleep(sleep_seconds)


def upload_video(
    file_path: str,
    title: str = "Test Title",
    description: str = "Test Description",
    category: str = "22",
    keywords: str = "",
    privacy_status: str = "private",
) -> str:
    """High-level function to upload a video.

    Args:
        file_path: Path to the video file.
        title: Video title.
        description: Video description.
        category: Numeric video category (default "22" for People & Blogs).
        keywords: Comma-separated keywords.
        privacy_status: Privacy status ('public', 'private', 'unlisted').

    Returns:
        The uploaded video ID.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    youtube = get_authenticated_service()

    class Options:
        def __init__(self):
            self.file = file_path
            self.title = title
            self.description = description
            self.category = category
            self.keywords = keywords
            self.privacyStatus = privacy_status

    options = Options()
    return initialize_upload(youtube, options)


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Upload a video to YouTube.")
    parser.add_argument("--file", required=True, help="Video file to upload")
    parser.add_argument("--title", help="Video title", default="Test Title")
    parser.add_argument(
        "--description", help="Video description", default="Test Description"
    )
    parser.add_argument(
        "--category",
        default="22",
        help="Numeric video category. See https://developers.google.com/youtube/v3/docs/videoCategories/list",
    )
    parser.add_argument(
        "--keywords", help="Video keywords, comma separated", default=""
    )
    parser.add_argument(
        "--privacyStatus",
        choices=VALID_PRIVACY_STATUSES,
        default="private",
        help="Video privacy status.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        exit(f"Please specify a valid file using the --file= parameter. File not found: {args.file}")

    youtube = get_authenticated_service()
    try:
        initialize_upload(youtube, args)
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")


if __name__ == "__main__":
    main()
