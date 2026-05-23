"""Intelligence agents package."""
from src.intelligence.code_archaeology import code_archaeology
from src.intelligence.pattern_detector import pattern_detector
from src.intelligence.technical_debt import technical_debt
from src.intelligence.memory_agent import memory_agent
from src.intelligence.learning_agent import learning_agent
from src.intelligence.agent_composer import agent_composer

INTELLIGENCE_AGENTS = {
    "code_archaeology": code_archaeology,
    "pattern_detector": pattern_detector,
    "technical_debt":   technical_debt,
    "memory_agent":     memory_agent,
    "learning_agent":   learning_agent,
    "agent_composer":   agent_composer,
}

__all__ = list(INTELLIGENCE_AGENTS.keys()) + ["INTELLIGENCE_AGENTS"]
