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
    print(f"Searching for files matching: {file_description}")
    # Extract potential filename or keywords from the description
    keywords = file_description.lower().split()

    # Define search paths (add or modify based on your needs)
    search_paths = [
        os.path.expanduser("~\\Desktop\\Demo_Files")
        # Add more paths as needed
    ]

    print(f"Search paths: {search_paths}")
    
    potential_files = []

    # Search for files that match the keywords
    for path in search_paths:
        if os.path.exists(path):
            print(f"Searching in: {path}")
            for root, _, files in os.walk(path):
                for file in files:
                    file_lower = file.lower()
                    score = sum(1 for keyword in keywords if keyword in file_lower)
                    if score > 0:
                        full_path = os.path.join(root, file)
                        potential_files.append((full_path, score))

    # Sort by score (highest first)
    potential_files.sort(key=lambda x: x[1], reverse=True)
    
    print(f"Potential files found: {potential_files}")

    if potential_files:
        top_files = potential_files[:3]  # Get top 3 matches
        result = "Found these files:\n"
        for i, (file_path, _) in enumerate(top_files, 1):
            result += f"{i}. {file_path}\n"
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            elif platform.system() == 'Windows':
                os.startfile(file_path)
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
            return f"Successfully opened {file_path}"
        except Exception as e:
            return f"Error opening file: {e}"
    else:
        return "No files found matching that description."


@tool
def open_file(file_path: str) -> str:
    """Open a file with the default application."""
    print(f"Opening file: {file_path}")
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
    print(f"Listing audio files in directory: {directory}")
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
    print(f"Analyzing audio file: {file_path}")
    try:
        # Verify the file exists
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        # Instead of just returning a placeholder, actually process the audio
        # using the process_audio_file function
        result = process_audio_file(file_path)
        return f"Audio analysis result: {result}"
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
    temperature=0,  # Use a very low temperature for more deterministic responses
)

# Create the tools list
tools = [find_file, open_file, list_audio_files, analyze_audio_file]

# Create the agent prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant used for work. You can process audio and understand what is 
     said to help users in their work.
     
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

IMPORTANT INSTRUCTIONS:
If the user mentions any file or document name, or speaks about finding documents or files, use the find_file tool with those keywords.
Scenario example: user says "Let's talk about file budget.xlsx" -> Use find_file with "budget.xlsx"

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
    """Process an audio file with Gemini for transcription, then use the agent to act on the content"""
    try:
        print(f"Processing audio file: {file_path}")
        # Convert the audio file to base64
        base64_audio = audio_to_base64(file_path)
        
        # Use the Gemini model directly for audio processing/transcription
        direct_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro", google_api_key=gemini_api_key, temperature=0
        )
        
        response = direct_llm.invoke([
            SystemMessage(content="Transcribe what people in this audio says. If the speaker mentions any filenames or documents, make sure to transcribe them accurately, but if you don't say any file name, just transcribe the audio."),
            HumanMessage(content=[
                {
                    "type": "media",
                    "mime_type": "audio/wav",
                    "data": base64_audio
                }
            ])
        ])
        
        # Get the transcription result
        transcription = response.content
        print(f"Transcription result: {transcription}")
        
        # Now pass the transcription to the agent to take action based on the content
        print(f"Passing transcription to agent for processing...")
        try:
            # Run the agent with the transcription as input
            agent_result = agent.invoke({"input": f"Audio Transcription: {transcription}"})
            final_answer = agent_result.get("output", "The agent couldn't process the transcription.")
            #print(f"Agent result: {final_answer}")
            return f"Transcription: {transcription}\n\nAgent Action: {final_answer}"
        except Exception as agent_error:
            print(f"Error when running agent: {agent_error}")
            # Fallback: just return the transcription if the agent fails
            return f"Transcription: {transcription}\n\nNote: Couldn't process with agent due to error: {agent_error}"
        
    except Exception as e:
        print(f"Error in process_audio_file: {e}")
        return f"Error processing audio file: {e}"
