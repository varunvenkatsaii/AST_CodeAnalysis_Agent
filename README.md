Agentic Codebase Analysis System with AST-Based Fact Extraction and LangGraph

An agent that understands a codebase from deterministic facts rather than embedding similarity. Python's ast module extracts imports, classes, functions, signatures and call relationships into structured JSON. A local LLM (Qwen3 4B via Ollama) then builds semantic summaries on top of those facts, and a LangGraph workflow retrieves only the artifacts needed to answer each question.

Why Fact-Based Retrieval?
Embedding search finds code that looks similar. For tasks like "what breaks if I change this function?" you need code that is actually connected. Because the facts come straight from the AST, retrieval is precise and auditable: if process_order calls validate_cart, that relationship is recorded, not inferred.

Features
AST fact extraction of imports, classes, functions, signatures and call relationships, stored as JSON artifacts
LLM-generated semantic details on top of the facts to produce application overviews and prompt-ready documentation
Targeted retrieval tools that fetch only the required function or class, or the full source file when deeper analysis is needed, keeping the context window small
Change-impact analysis by tracing callers and callees
Stateful agent: a shared AgentState records previous tool calls and retrieved artifacts so the agent does not repeat work
Structured outputs validated with Pydantic
Local and private: runs on Ollama with a 4B model, so code never leaves your machine
Loosely coupled design: the LLM layer is separate from extraction and retrieval, so switching to a frontier model API needs minimal code changes
Architecture
Codebase
   |
   v
AST analyzer  -->  facts.json (imports, classes, functions, calls)
   |                    |
   |                    v
   |           LLM semantic summaries (Qwen3 4B)
   |                    |
   v                    v
        LangGraph agent  <--  AgentState (tool calls, retrieved artifacts)
              |
              +--> tool: get_artifact (function / class)
              +--> tool: get_full_file
              +--> tool: get_semantic_overview
              |
              v
   Pydantic-validated structured answer


**Tech Stack:
Fact extraction	ast module
Agent workflow	LangGraph
LLM runtime	Ollama
Model	Qwen3 4B
Output validation	Pydantic
Artifact index	JSON
Getting Started
Prerequisites
Python 3.10+

**Roadmap for V2: 
Integrate Langfuse
Containerize the application
Add Human in the loop 
Fine tune the code extraction 
Use RAG for document analysis
