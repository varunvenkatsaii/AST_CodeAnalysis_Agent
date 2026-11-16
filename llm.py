
from langchain_ollama import ChatOllama


def get_llm():

    llm = ChatOllama (
        model="qwen3:4b",
        reasoning= False,
        temperature=0.1,
        num_ctx=8196,
        num_predict=4096,
        format = "json"
    )

    return llm
