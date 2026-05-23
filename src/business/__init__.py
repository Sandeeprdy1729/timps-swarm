"""Business agents package."""
from src.business.analytics_agent import analytics_agent
from src.business.ab_testing_agent import ab_testing_agent
from src.business.monetization_agent import monetization_agent
from src.business.seo_agent import seo_agent
from src.business.postmortem_agent import postmortem_agent
from src.business.sprint_planning_agent import sprint_planning_agent

BUSINESS_AGENTS = {
    "analytics_agent":     analytics_agent,
    "ab_testing_agent":    ab_testing_agent,
    "monetization_agent":  monetization_agent,
    "seo_agent":           seo_agent,
    "postmortem_agent":    postmortem_agent,
    "sprint_planning_agent": sprint_planning_agent,
}

__all__ = list(BUSINESS_AGENTS.keys()) + ["BUSINESS_AGENTS"]
