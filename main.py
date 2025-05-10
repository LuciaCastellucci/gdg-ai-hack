import psutil

def check_videocall_apps() -> bool:
    keywords = ['teams', 'zoom', 'meet', 'webex', 'skype']
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name'].lower()
            for keyword in keywords:
                if keyword in name:
                    return True
        except Exception as e:
            print(f"Error checking process: {e}")
    return False


if __name__ == "__main__":
    apps = check_videocall_apps()
    if apps:
        print("Video call applications are running.")
    else:
        print("No video call applications are running.")