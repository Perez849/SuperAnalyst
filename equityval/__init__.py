"""equityval — automated equity valuation & research-note generator."""
from .engine import ValuationConfig, value_company
from .providers import get_company

__all__ = ["value_company", "ValuationConfig", "get_company"]
__version__ = "1.0.0"
