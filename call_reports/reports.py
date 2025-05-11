from typing import List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import datetime

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def find_files_with_topic(topic: str, start_path: str = '.') -> List[str]:
    """
    Find contents of all files containing 'topic' in either filename or content.

    Args:
        topic (str): The topic to search for
        start_path (str): Directory where to start the search (default: current directory)

    Returns:
        list: List of strings containing the contents of matching files
    """
    contents_list = []
    
    for root, _, files in os.walk(start_path):
        for file in files:
            file_path = os.path.join(root, file)
            
            if topic.lower() in file.lower():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        contents_list.append(f.read())
                except Exception as e:
                    print(f"Impossibile leggere il file {file_path}: {e}")
            else:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if topic.lower() in content.lower():
                            contents_list.append(content)
                except Exception as e:
                    pass
    return contents_list


def fetch_topics_from_calendar():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        now_iso = now.isoformat()
        time_max = (now + datetime.timedelta(hours=24)).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now_iso,
                timeMax=time_max,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            print("No upcoming events found.")
            return
        topics = []
        for event in events:
            topics.append(event["summary"])
        return topics
    except HttpError as error:
        print(f"An error occurred: {error}")
