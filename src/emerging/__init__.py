"""Emerging technology agents package."""
from src.emerging.robotics_agent import robotics_agent
from src.emerging.web3_agent import web3_agent
from src.emerging.federated_learning import federated_learning
from src.emerging.quantum_ready import quantum_ready

EMERGING_AGENTS = {
    "robotics_agent":     robotics_agent,
    "web3_agent":         web3_agent,
    "federated_learning": federated_learning,
    "quantum_ready":      quantum_ready,
}

__all__ = list(EMERGING_AGENTS.keys()) + ["EMERGING_AGENTS"]
