import os
import subprocess
import platform
import base64
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool

# Load environment variables from .env file
load_dotenv()

# Get Google API key
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError(
        "Google API key not found. Make sure the .env file contains the GEMINI_API_KEY variable."
    )


# Define tools for the agent
@tool
def find_file(file_description: str) -> str:
    """
    Find a file in the file system based on the description.
    Example description: "text file in documents folder", "spreadsheet with budget data"
    """
    # Extract potential filename or keywords from the description
    keywords = file_description.lower().split()

    # Define search paths (add or modify based on your needs)
    search_paths = [
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~"),
        # Add more paths as needed
    ]

    potential_files = []

    # Search for files that match the keywords
    for path in search_paths:
        if os.path.exists(path):
            for root, _, files in os.walk(path):
                for file in files:
                    file_lower = file.lower()
                    score = sum(1 for keyword in keywords if keyword in file_lower)
                    if score > 0:
                        full_path = os.path.join(root, file)
                        potential_files.append((full_path, score))

    # Sort by score (highest first)
    potential_files.sort(key=lambda x: x[1], reverse=True)

    if potential_files:
        top_files = potential_files[:3]  # Get top 3 matches
        result = "Found these files:\n"
        for i, (file_path, _) in enumerate(top_files, 1):
            result += f"{i}. {file_path}\n"
        return result
    else:
        return "No files found matching that description."


@tool
def open_file(file_path: str) -> str:
    """Open a file with the default application."""
    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"

    try:
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", file_path])
        elif platform.system() == "Windows":
            os.startfile(file_path)
        else:  # Linux
            subprocess.run(["xdg-open", file_path])
        return f"Successfully opened {file_path}"
    except Exception as e:
        return f"Error opening file: {e}"


@tool
def list_audio_files(directory: str = "./") -> str:
    """
    List all WAV audio files in the specified directory.
    """
    try:
        directory_path = Path(directory)
        if not directory_path.exists() or not directory_path.is_dir():
            return f"Error: Directory {directory} does not exist"

        audio_files = list(directory_path.glob("*.wav"))

        if not audio_files:
            return f"No WAV files found in {directory}"

        result = f"Found {len(audio_files)} WAV files in {directory}:\n"
        for i, file_path in enumerate(audio_files, 1):
            result += f"{i}. {file_path.name}\n"
        return result
    except Exception as e:
        return f"Error listing audio files: {e}"


@tool
def analyze_audio_file(file_path: str) -> str:
    """
    Analyze the content of an audio file and return a description.
    This uses the model's understanding of the audio content.
    """
    try:
        # Verify the file exists
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        # This is a placeholder - the actual processing is done in process_audio_file
        return f"Audio file {os.path.basename(file_path)} will be analyzed."
    except Exception as e:
        return f"Error analyzing audio file: {e}"


# Function to convert audio to base64
def audio_to_base64(file_path):
    with open(file_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("utf-8")


# Create the LLM model using Google Gemini with multimodal capabilities
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",  # Using the pro model for multimodal capabilities
    google_api_key=gemini_api_key,
    temperature=0,
    convert_system_message_to_human=True,
)

# Create the tools list
tools = [find_file, open_file, list_audio_files, analyze_audio_file]

# Create the agent prompt
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a helpful assistant that can process both text and audio inputs. You can help users find and open files from their computer, and understand the content of audio files.

You have access to the following tools:
{tools}

Use the following format:

User Query: the user query
Thought: you should think about what to do
Action: the tool to use, should be one of [{tool_names}]
Action Input: the input to the tool
Observation: the result of the action
... (this Thought/Action/Action Input/Observation pattern can repeat multiple times)
Thought: now I know the final answer
Final Answer: the final answer to the user's question

When asked about an audio file, first use list_audio_files if needed, then use analyze_audio_file to understand its content.

{agent_scratchpad}
""",
        ),
        ("human", "{input}"),
    ]
)

# Create the ReAct agent
react_agent = create_react_agent(llm, tools, prompt)

# Create the agent executor
agent = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
)


def process_audio_file(file_path):
    """Process an audio file directly with the Gemini model to understand its content"""
    try:
        # Convert the audio file to base64
        base64_audio = audio_to_base64(file_path)

        # Use the Gemini model directly for audio processing
        direct_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro", google_api_key=gemini_api_key, temperature=0
        )

        response = direct_llm.invoke(
            [
                SystemMessage(
                    content="Describe this audio content in detail. What can you hear? If there's speech, what is being said?"
                ),
                HumanMessage(
                    content=[
                        {
                            "type": "media",
                            "mime_type": "audio/wav",
                            "data": base64_audio,
                        }
                    ]
                ),
            ]
        )

        # Return the model's description of the audio
        return response.content
    except Exception as e:
        return f"Error processing audio file: {e}"


def main():
    print("File and Audio Assistant")
    print("------------------------")
    print("Options:")
    print("1. Process a query")
    print("2. List audio files")
    print("3. Analyze a specific audio file")
    print("4. Exit")

    while True:
        choice = input("\nSelect an option (1-4): ")

        if choice == "1":
            user_query = input("Enter your query: ")
            result = agent.invoke({"input": user_query})
            print("\nResponse:", result["output"])

        elif choice == "2":
            directory = (
                input("Enter directory path (or press Enter for current directory): ")
                or "./"
            )
            print(list_audio_files(directory))

        elif choice == "3":
            file_path = input("Enter the path to the audio file: ")
            if os.path.exists(file_path) and file_path.lower().endswith(".wav"):
                print("Analyzing audio file...")
                analysis = process_audio_file(file_path)
                print("\nAudio Analysis:")
                print(analysis)
            else:
                print(f"Error: File does not exist or is not a WAV file: {file_path}")

        elif choice == "4":
            print("Goodbye!")
            break

        else:
            print("Invalid option. Please select 1-4.")


if __name__ == "__main__":
    main()
