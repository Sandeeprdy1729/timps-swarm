"""Domain-specific agents package."""
from src.domain.web_scraping import web_scraping
from src.domain.data_pipeline import data_pipeline
from src.domain.realtime_agent import realtime_agent
from src.domain.mobile_agent import mobile_agent
from src.domain.browser_automation import browser_automation
from src.domain.graphql_agent import graphql_agent
from src.domain.cli_tool_agent import cli_tool_agent
from src.domain.embedded_agent import embedded_agent

DOMAIN_AGENTS = {
    "web_scraping":       web_scraping,
    "data_pipeline":      data_pipeline,
    "realtime_agent":     realtime_agent,
    "mobile_agent":       mobile_agent,
    "browser_automation": browser_automation,
    "graphql_agent":      graphql_agent,
    "cli_tool_agent":     cli_tool_agent,
    "embedded_agent":     embedded_agent,
}

__all__ = list(DOMAIN_AGENTS.keys()) + ["DOMAIN_AGENTS"]
