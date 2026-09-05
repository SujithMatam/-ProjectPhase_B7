"""
LAM -- Language Agent Module
Phase 1 package for OrthoSync orthopedic post-operative chatbot.

Pipeline (in execution order):
  1. SafetyTriageEngine  -> RED short-circuits immediately (always wins)
  2. ScopeValidator      -> OUT_OF_SCOPE short-circuits (only if not RED)
  3. IntentClassifier    -> maps query to IntentLabel
  4. AgentRouter         -> selects TargetAgent + ActionType
  5. ChatAgent           -> generative response

Phase 2 upgrade path:
  Replace IntentClassifier internals with Sentence-BERT cosine-similarity
  without modifying this package's public interface or the orchestrator.
"""
