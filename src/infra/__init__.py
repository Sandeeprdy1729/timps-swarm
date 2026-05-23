"""Infrastructure agents package."""
from src.infra.load_testing import load_testing
from src.infra.feature_flag import feature_flag
from src.infra.disaster_recovery import disaster_recovery
from src.infra.finops_agent import finops_agent
from src.infra.secrets_management import secrets_management
from src.infra.edge_agent import edge_agent

INFRA_AGENTS = {
    "load_testing":        load_testing,
    "feature_flag":        feature_flag,
    "disaster_recovery":   disaster_recovery,
    "finops_agent":        finops_agent,
    "secrets_management":  secrets_management,
    "edge_agent":          edge_agent,
}

__all__ = list(INFRA_AGENTS.keys()) + ["INFRA_AGENTS"]
