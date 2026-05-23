"""AI/ML agents package."""
from src.aiml.prompt_engineer import prompt_engineer
from src.aiml.dataset_agent import dataset_agent
from src.aiml.model_evaluator import model_evaluator
from src.aiml.rag_designer import rag_designer
from src.aiml.finetuning_agent import finetuning_agent
from src.aiml.ai_safety_agent import ai_safety_agent
from src.aiml.vector_db_agent import vector_db_agent

AIML_AGENTS = {
    "prompt_engineer":  prompt_engineer,
    "dataset_agent":    dataset_agent,
    "model_evaluator":  model_evaluator,
    "rag_designer":     rag_designer,
    "finetuning_agent": finetuning_agent,
    "ai_safety_agent":  ai_safety_agent,
    "vector_db_agent":  vector_db_agent,
}

__all__ = list(AIML_AGENTS.keys()) + ["AIML_AGENTS"]
