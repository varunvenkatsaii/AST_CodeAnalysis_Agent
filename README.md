🧠 Agentic Codebase Analysis System

AST-Based Fact Extraction | LangGraph | Local LLM

An intelligent agent that understands codebases through deterministic structural facts rather than embedding similarity.

The system combines Python's AST (Abstract Syntax Tree) analysis with LLM-powered semantic understanding to build a structured representation of a codebase. A LangGraph-based agent then dynamically retrieves only the relevant code artifacts required to answer questions, analyze dependencies, and assess the impact of potential code changes.

The core idea: Instead of guessing which code is relevant based on semantic similarity, understand how the code is actually structured and connected.

🚀 Why Fact-Based Retrieval?

Traditional embedding-based retrieval identifies code based on semantic similarity. However, understanding code dependencies and predicting the impact of a change requires more than finding similar-looking code.

Consider the question:

What could break if I modify process_order()?

An embedding-based approach might retrieve functions with similar logic. This system instead traces the actual relationships between functions.

If process_order() calls validate_cart(), and validate_cart() is used by other functions, these relationships are explicitly captured during AST analysis.

This enables:

Precise dependency tracking through actual function call relationships.

Auditable retrieval backed by deterministic code facts.

More reliable change-impact analysis.

Reduced dependence on embedding similarity and inferred relationships.

✨ Key Features

1. Deterministic AST-Based Fact Extraction

Uses Python's built-in ast module to extract structured information directly from source code.

Imports and module dependencies.

Classes, functions, and their signatures.

Function arguments and definitions.

Function call relationships (callers and callees).

Structured JSON artifacts for downstream retrieval.

2. LLM-Powered Semantic Understanding

Combines deterministic AST facts with a local LLM (Qwen3 4B via Ollama) to generate higher-level semantic understanding.

Application and file-level overviews.

Architectural roles and responsibilities.

Function and class summaries.

Execution-flow descriptions.

Prompt-ready documentation built on extracted facts.

3. Targeted Artifact Retrieval

Instead of loading entire files into the LLM context, the agent retrieves only the information necessary for the current task.

Available retrieval tools:

get_artifact – Retrieve a specific function or class.

get_full_file – Retrieve the complete source file when deeper inspection is required.

get_semantic_overview – Retrieve generated semantic documentation and architectural context.

4. Change-Impact Analysis

Uses extracted caller-callee relationships to trace dependencies and understand the potential impact of modifying a function or class.

5. Stateful Agent Architecture

A shared AgentState maintains execution context across LangGraph nodes.

Tracks previous tool calls.

Stores retrieved code artifacts.

Maintains relevant analysis results.

Prevents unnecessary repeated retrieval.

Supports iterative reasoning across multiple retrieval steps.

6. Structured and Validated Outputs

Uses Pydantic models to validate structured LLM responses, ensuring predictable outputs and consistent communication between workflow components.

7. Local and Privacy-Focused Execution

Runs using Qwen3 4B through Ollama, keeping source code and analysis local without requiring external LLM APIs.

8. Modular Architecture

Separates AST extraction, semantic analysis, retrieval, and agent orchestration.

This makes it possible to replace the local LLM with a frontier model API with minimal changes to the underlying extraction and retrieval architecture.

🏗️ Architecture

The system follows a two-layer understanding approach:

Structural understanding: Extract deterministic facts directly from source code.

Semantic understanding: Use an LLM to interpret those facts and generate higher-level documentation.


🔮 Roadmap – V2

The next iteration focuses on observability, production readiness, human oversight, and extending the system beyond source-code analysis.

Langfuse Integration – Add tracing, observability, token tracking, and evaluation of agent execution.

Containerization – Dockerize the application for reproducible deployment and environment management.

Human-in-the-Loop – Introduce human approval and feedback for critical analysis and code-change decisions.

Fine-Tuning – Fine-tune the model to improve code understanding, artifact selection, and structured extraction.

Document RAG – Extend retrieval capabilities to technical documentation, design specifications, and project-related documents.

🎯 Project Objective

Build an agent capable of understanding software systems at both the structural and semantic levels.

The long-term goal is to move beyond code search towards an intelligent codebase assistant that can reason about dependencies, explain execution flows, identify potential risks, and support developers in making informed code changes.
