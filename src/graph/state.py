# short-term state variables of the current conversation and holds data retrieved from your database

from typing import Annotated, Sequence, Dict, Any, Optional
from typing_extensions import TypedDict
from langchain_core import BaseMessage, BaseMemory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core import add_messages

class HealthTwinState(TypedDict):
    # Appends incoming  messages
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Stores the chronological anchor timestamp discovered via pgvector search
    discovered_timestamp: Optional[str]

    # Stores the raw physical analytics (glucose, heart rate calculations)
    extracted_biometrics: Optional[Dict[str, Any]]

