"""India-specific agents package."""
from src.india.gst_compliance import gst_compliance
from src.india.abdm_agent import abdm_agent
from src.india.upi_agent import upi_agent
from src.india.digilocker_agent import digilocker_agent
from src.india.indiehacker_agent import indiehacker_agent

INDIA_AGENTS = {
    "gst_compliance":    gst_compliance,
    "abdm_agent":        abdm_agent,
    "upi_agent":         upi_agent,
    "digilocker_agent":  digilocker_agent,
    "indiehacker_agent": indiehacker_agent,
}

__all__ = list(INDIA_AGENTS.keys()) + ["INDIA_AGENTS"]
