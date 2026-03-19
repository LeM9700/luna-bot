from email.mime import message
import os
from unittest import result
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from memory import search_memories, smart_save_memory
from personality import get_personality_context, update_state
from companions import COMPANIONS
from dotenv import load_dotenv


load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",        # rapide + pas cher pour tester
    api_key=os.getenv("OPENAI_API_KEY"),
    max_tokens=1000
)

def should_save_memory(message: str) -> bool:
    """Détecte si un message contient une info importante à mémoriser"""
    keywords = ["j'aime", "je déteste", "j'adore", "je travaille", "j'habite",
                "mon", "ma ", "mes ", "je suis", "j'ai", "je veux", "je rêve",
                "je m'appelle", "mon prénom", "mon âge", "ma famille", "mes plaisirs", "mon environnemnt", "mon entourage"]
    return any(k in message.lower() for k in keywords)

def chat(user_id: str, companion_id: str, message: str, history: list) -> str:
    """
    Génère une réponse avec :
    - Personnalité du companion
    - Souvenirs pertinents depuis pgvector
    - Historique de la conversation
    """
    companion = COMPANIONS.get(companion_id, COMPANIONS["luna"])

    # 1. Cherche les souvenirs pertinents
    memories = search_memories(user_id, message)
    memory_block = ""
    if memories:
        memory_block = "\n\nCe que tu sais déjà sur cet utilisateur :\n"
        memory_block += "\n".join(f"- {m}" for m in memories)

    # 2. Construit le system prompt avec mémoire injectée
    personality_ctx = get_personality_context(user_id, companion_id)
    system = companion["system"] + memory_block + personality_ctx

    # 3. Construit les messages
    messages = [SystemMessage(content=system)]
    for h in history[-10:]:  # garde les 10 derniers tours
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=message))

    # 4. Appel LLM
    response = llm.invoke(messages)
    reply = response.content

    # 5. Sauvegarde automatique si info importante

    result = smart_save_memory(user_id, message)
    if result:
        print(f"[Chain] Mémoire sauvegardée : {result['summary'][:50]}")
        
    update_state(user_id, companion_id, message, reply)
   

    return reply