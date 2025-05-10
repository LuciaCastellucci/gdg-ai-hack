import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Ottieni la chiave API di Google
google_api_key = os.getenv("GEMINI_API_KEY")
if not google_api_key:
    raise ValueError("La chiave API di Google non è stata trovata. Assicurati che il file .env contenga la variabile GEMINI_API_KEY.")

# Definisci gli strumenti che vuoi che l'agente possa usare
@tool
def search(query: str) -> str:
    """Cerca informazioni sul web."""
    return f"Risultati della ricerca per: {query}"

@tool
def calculator(expression: str) -> str:
    """Calcola espressioni matematiche."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Errore nel calcolo: {e}"

# Crea il modello LLM usando Google Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=google_api_key,
    temperature=0,
    convert_system_message_to_human=True
)

# Crea gli strumenti
tools = [search, calculator]

# Crea il prompt per l'agente
prompt = ChatPromptTemplate.from_messages([
    ("system", """Sei un assistente utile per le chiamate video. Rispondi alle domande dell'utente nel miglior modo possibile.

Hai accesso ai seguenti strumenti:
{tools}

Usa il seguente formato:

Query utente: la query dell'utente
Pensiero: devi pensare a cosa fare
Azione: lo strumento da utilizzare, deve essere uno tra [{tool_names}]
Input azione: l'input allo strumento
Osservazione: il risultato dell'azione
... (questo pattern Pensiero/Azione/Input Azione/Osservazione si può ripetere più volte)
Pensiero: ora conosco la risposta finale
Risposta finale: la risposta finale alla domanda dell'utente

Per favore, assicurati di includere una "Risposta finale" per rispondere alla domanda dell'utente.

{agent_scratchpad}
"""),
    ("human", "{input}"),
])

# Crea l'agente ReAct
react_agent = create_react_agent(llm, tools, prompt)

# Crea l'executor dell'agente
root_agent = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
)

# Funzione di esecuzione per compatibilità con il codice esistente
def run():
    print("Agente di assistenza per chiamate attivato")
    while True:
        user_input = input("Tu: ")
        if user_input.lower() in ["exit", "quit", "q", "esci"]:
            print("Chiusura dell'agente...")
            break
        response = root_agent.invoke({"input": user_input})
        print(f"Assistente: {response['output']}")
