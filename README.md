# HealthTwin_langgraph_memory
Health Twin: Multi-Layered Long-Term Agentic Memory with LangGraph

An advanced, production-grade Health Twin Agent that shifts away from stateless chatbots to manage continuous, longitudinal patient biometrics. Inspired by the architectural concepts taught in the DeepLearning.AI: Long-Term Agentic Memory with LangGraph course, this project implements a hybrid database layout to manage Semantic, Episodic, and Procedural memory streams.Using the real-world clinical BIG IDEAs Lab Glycemic Variability Dataset (Duke University), the agent correlates high-frequency biometric data streams with qualitative lifestyle journal text logs to diagnose, track, and explain biological trends over time.

🧠 Memory Architecture (The LangGraph Engine)Rather than overwhelming the LLM's context window with months of raw csv lines, this system maps memory tiers into specific physical database architectures:Semantic Memory (The Conceptual Facts): Lifestyle events, meal entries, and environmental changes are stored in a PostgreSQL pgvector database. The agent uses vector similarity search (text-embedding-3-small) to isolate relevant conceptual facts on demand.

Episodic Memory (The Time-Stitched Narratives): When a semantic anchor is uncovered, custom LangGraph tools dynamically calculate and slice corresponding windows inside a relational PostgreSQL time-series table (Continuous Glucose Monitor records + continuous Heart Rate biometrics). This allows the agent to reconstruct the full narrative arc of a biological episode.

Procedural Memory (The Execution Rules): Baked directly into the compiled LangGraph topology (state_modifier), establishing strict reasoning routes (Identify Context ➔ Execute Time Slice ➔ Analytical Synthesis) without risk of workflow hallucination.


🛠️ The Tech StackOrchestration Engine: LangGraph & LangChain (V1 Production Spec)Reasoning & Embedding LLMs: OpenAI gpt-4o & text-embedding-3-smallDatabase Infrastructure: PostgreSQL + pgvector (Hosted on Neon serverless postgres)Data Pipeline Engine: Pandas (Timestamp synchronization and token aggregation metrics)Interactive Interface: Streamlit (Dashboard visualization tracking multi-modal state)

📈 The Graph Workflow PipelinetextUser
Question: "Why did my blood sugar spike last Tuesday morning?"
       │
       ▼
[LangGraph Agent Loop] ───(Queries pgvector)───► [Semantic Memory Tool]
                                                         │
                                               Extracts: "Ate white bagel @ 08:15 AM"
                                                         │
       ┌─────────────────────────────────────────────────┘
       ▼
[Episodic Memory Tool] ───(Queries SQL Tables)─► Grabs raw CGM/HR metrics from 08:15 to 11:15 AM
       │
       ▼
[Analytical Synthesizer Node] ─────────────────► Output: "Your bagel caused a 185 mg/dL spike."
