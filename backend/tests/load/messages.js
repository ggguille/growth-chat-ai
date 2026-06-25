// RAG-triggering messages — require knowledge base retrieval (~60% of turns)
export const ragMessages = [
  "What kind of AI projects has your team delivered?",
  "Do you have experience with RAG pipelines in production?",
  "Can you tell me about your engagement models?",
  "What industries do you typically work with?",
  "Do you have case studies in the fintech space?",
  "How does your team handle model evaluation?",
  "What's your experience with LangGraph or LangChain?",
  "Do you work with European companies specifically?",
];

// Non-RAG messages — general qualification conversation (~40% of turns)
export const nonRagMessages = [
  "We're a 200-person SaaS company looking to add AI to our product.",
  "Our main challenge is automating document review.",
  "We've tried OpenAI APIs internally but need more structure.",
  "The project would need to start in Q3.",
  "I'm the CTO — I'd need to involve our VP of Engineering.",
  "What would next steps look like if we wanted to explore working together?",
];
