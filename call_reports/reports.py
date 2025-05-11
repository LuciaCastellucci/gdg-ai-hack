from typing import List, Optional, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import requests
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add the parent directory to sys.path to import synthesizer
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
    
from synthesizer import synthesize_report_content

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
        now = datetime.now(tz=timezone.utc)
        now_iso = now.isoformat()
        time_max = (now + timedelta(hours=24)).isoformat()
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
            start = event["start"].get("dateTime", event["start"].get("date"))
            topics.append((start, event["summary"]))
        return topics
    except HttpError as error:
        print(f"An error occurred: {error}")


def get_call_logs_by_topic(topic: str) -> List[str]:
    """
    Retrieve call logs from the API by topic.
    
    Args:
        topic (str): The topic to search for
        
    Returns:
        List[str]: List of call log reports
    """
    try:
        response = requests.get(f"http://localhost:8000/call-logs/topic/{topic}")
        if response.status_code == 200:
            call_logs = response.json()
            return [log.get("report", "") for log in call_logs]
        else:
            print(f"Failed to retrieve call logs: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"Error retrieving call logs: {e}")
        return []


def get_reports_by_topic(topic: str) -> List[str]:
    """
    Retrieve reports from the API by topic.
    
    Args:
        topic (str): The topic to search for
        
    Returns:
        List[str]: List of reports
    """
    try:
        response = requests.get(f"http://localhost:8000/reports/topic/{topic}")
        if response.status_code == 200:
            reports = response.json()
            return [report.get("content", "") for report in reports]
        else:
            print(f"Failed to retrieve reports: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"Error retrieving reports: {e}")
        return []


def parse_datetime(dt_string: str) -> Optional[datetime]:
    """
    Parse the datetime string from Google Calendar API.
    
    Args:
        dt_string (str): The datetime string (e.g., "2025-06-01T07:30:00+02:00")
        
    Returns:
        Optional[datetime]: Parsed datetime object or None if parsing failed
    """
    try:
        return datetime.fromisoformat(dt_string)
    except ValueError:
        print(f"Failed to parse datetime: {dt_string}")
        return None


def create_report(notification_callback=None):
    """
    Create reports for upcoming calendar events based on their start time.
    
    For events starting in more than 60 minutes:
    - Gather relevant files and call logs
    - Synthesize content for preparation
    
    For events starting in more than 30 minutes (but less than 60):
    - Retrieve existing reports for quick review
    
    Args:
        notification_callback (callable, optional): Function to call with the synthesis content
        
    Returns:
        str: A summary of the reports created or found
    """
    topics = fetch_topics_from_calendar()
    if not topics:
        print("No topics found in calendar.")
        return "Nessun evento trovato nel calendario."
    
    current_time = datetime.now().astimezone()  # Current time with timezone info
    print(f"Current time: {current_time}")
    print(f"Found {len(topics)} upcoming events")
    
    # Teniamo traccia dello stato di generazione dei report
    report_summary = []
    
    # Per la notifica, useremo il contenuto del primo report significativo
    first_synthesis = None
    
    for start_str, topic in topics:
        start_time = parse_datetime(start_str)
        if not start_time:
            continue
        
        time_diff = start_time - current_time
        print(f"Event: {topic} starting at {start_time} (in {time_diff})")
        
        # For events more than 60 minutes in the future
        if time_diff >= timedelta(minutes=60):
            print(f"Preparing comprehensive report for: {topic}")
            files = find_files_with_topic(topic)
            call_logs = get_call_logs_by_topic(topic)
            
            if files or call_logs:
                synthesis = synthesize_report_content(files, call_logs)
                print(f"Synthesis generated for {topic}: {len(synthesis)} characters")
                
                # Salva il primo report significativo per la notifica
                if first_synthesis is None:
                    first_synthesis = synthesis
                
                # Create a Report object and save it to the database
                current_date = datetime.now().strftime("%Y-%m-%d")
                expected_time = start_time.strftime("%H:%M")
                actual_time = datetime.now().strftime("%H:%M")
                
                report_data = {
                    "date": current_date,
                    "topic": topic,
                    "content": synthesis,
                    "timestamp_expected": None,
                    "timestamp_actual": None
                }
                
                try:
                    response = requests.post(
                        "http://localhost:8000/reports",
                        json=report_data,
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code == 201:
                        print(f"Report saved to database with ID: {response.json().get('_id')}")
                        report_summary.append(f"☑️ Creato report per '{topic}' (tra {time_diff})")
                    else:
                        print(f"Failed to save report: HTTP {response.status_code}")
                        report_summary.append(f"❌ Errore nel salvare il report per '{topic}'")
                except Exception as e:
                    print(f"Error saving report to database: {e}")
                    report_summary.append(f"❌ Errore nel salvare il report per '{topic}': {str(e)}")
            else:
                print(f"No files or call logs found for topic: {topic}")
                report_summary.append(f"ℹ️ Nessun file o registro chiamate trovato per '{topic}'")
        
        # For events between 30-60 minutes in the future
        elif time_diff >= timedelta(minutes=30):
            print(f"Retrieving quick reference reports for: {topic}")
            reports = get_reports_by_topic(topic)
            if reports:
                print(f"Found {len(reports)} existing reports for {topic}")
                report_summary.append(f"📑 Trovati {len(reports)} report esistenti per '{topic}' (tra {time_diff})")
                
                # Se non abbiamo ancora un report significativo, usa il primo report esistente
                if first_synthesis is None and reports:
                    first_synthesis = reports[0]
            else:
                print(f"No existing reports found for topic: {topic}")
                report_summary.append(f"ℹ️ Nessun report esistente per '{topic}' (tra {time_diff})")
    
    # Crea un riassunto completo per il log
    summary = "\n".join(report_summary)
    final_summary = f"Riepilogo report ({len(topics)} eventi):\n\n{summary}"
    print(final_summary)
    
    # Invia una notifica con il contenuto del report
    if notification_callback and first_synthesis:
        # Prepariamo un titolo per il report
        if len(topics) > 0:
            # Usa il titolo del primo evento con report
            event_topic = topics[0][1]
            notification_message = f"📋 Report per: {event_topic}\n\n{first_synthesis}"
            notification_callback(notification_message)
    
    return final_summary