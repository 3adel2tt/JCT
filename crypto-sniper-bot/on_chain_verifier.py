"""
On-Chain Verifier Module

Fetches and parses token security data from the GoPlus Security API.
Provides real-time on-chain metrics for the Decision Engine.
"""

import aiohttp
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OnChainVerifier:
    """
    Asynchronous verifier that queries the GoPlus Security API for token safety metrics.
    
    The GoPlus API provides comprehensive security data including:
    - Honeypot detection
    - Mintability status
    - Ownership information
    - Tax rates (buy/sell)
    - LP lock status
    - Holder distribution
    
    Attributes:
        base_url: GoPlus API endpoint
        chain_id: Blockchain network ID (1=ETH, 56=BSC, etc.)
        headers: Request headers for API authentication
    """
    
    def __init__(self, api_key: str, chain_id: str):
        """
        Initialize the OnChainVerifier.
        
        Args:
            api_key: GoPlus API key (optional for basic tier)
            chain_id: Blockchain network identifier
        """
        self.base_url = "https://api.gopluslabs.io/api/v1/token_security"
        self.chain_id = chain_id
        self.headers = {}
        # Note: GoPlus often doesn't require a header key for basic endpoints,
        # but if you have a premium key, add it here:
        # if api_key:
        #     self.headers = {'Authorization': f'Bearer {api_key}'}
        logger.info(f"OnChainVerifier initialized for chain_id={chain_id}")

    async def get_security_data(self, contract_address: str) -> Dict[str, Any]:
        """
        Fetches security data from GoPlus API for a given token contract.
        
        Args:
            contract_address: The token's smart contract address
            
        Returns:
            Dictionary containing normalized security metrics:
                - is_honeypot: Boolean
                - is_mintable: Boolean
                - owner_address: String (0x0 if renounced)
                - buy_tax: Float percentage
                - sell_tax: Float percentage
                - lp_locked_pct: Float percentage
                - top_10_holder_pct: Float percentage
                
        Error Handling:
            - Rate limiting (429): Returns fallback data with warning
            - API errors: Returns fallback data with error logging
            - Connection failures: Returns safe fallback defaults
        """
        url = f"{self.base_url}/{self.chain_id}?contract_addresses={contract_address}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_response(data, contract_address)
                    elif response.status == 429:
                        logger.warning(f"GoPlus Rate Limited for {contract_address}")
                        return self._get_fallback_data("Rate Limited")
                    else:
                        logger.error(f"GoPlus API Error: Status {response.status} for {contract_address}")
                        return self._get_fallback_data(f"API Error: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching data for {contract_address}")
            return self._get_fallback_data("Connection Timeout")
        except aiohttp.ClientError as e:
            logger.exception(f"Client error fetching data for {contract_address}: {e}")
            return self._get_fallback_data("Connection Failed")
        except Exception as e:
            logger.exception(f"Unexpected error fetching data for {contract_address}: {e}")
            return self._get_fallback_data("Unexpected Error")

    def _parse_response(self, data: dict, address: str) -> Dict[str, Any]:
        """
        Normalizes GoPlus JSON response into our standard metric format.
        
        Args:
            data: Raw JSON response from GoPlus API
            address: Contract address being queried
            
        Returns:
            Normalized dictionary of security metrics
        """
        result = data.get('result', {}).get(address, {})
        
        # Helper functions for safe type conversion
        def safe_int(val, default=0):
            """Safely convert value to integer."""
            if val is None or val == '':
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def safe_bool(val):
            """Convert GoPlus string/integer boolean to Python bool."""
            return str(val) == "1"

        # Calculate LP Locked Percentage
        # GoPlus returns locked value and total LP value separately
        lp_locked = safe_int(result.get('lp_locked'))
        lp_total = safe_int(result.get('liquidity'))
        lp_pct = (lp_locked / lp_total * 100) if lp_total > 0 else 0

        # Extract holder concentration (top 10 holders percentage)
        # GoPlus provides this as 'holder_10' field
        top_10_pct = safe_int(result.get('holder_10'), 0)

        return {
            'is_honeypot': safe_bool(result.get('is_honeypot')),
            'is_mintable': safe_bool(result.get('is_mintable')),
            'owner_address': result.get('creator_address', '0x0'),  # Using creator as proxy for owner
            'buy_tax': safe_int(result.get('buy_tax'), 0),
            'sell_tax': safe_int(result.get('sell_tax'), 0),
            'lp_locked_pct': lp_pct,
            'top_10_holder_pct': top_10_pct,
        }

    def _get_fallback_data(self, reason: str) -> Dict[str, Any]:
        """
        Returns safe default values when API calls fail.
        
        This is a critical security feature - when we can't verify a token,
        we assume conservative defaults to prevent false positives that could
        lead to risky trades.
        
        Args:
            reason: String explaining why fallback data is being used
            
        Returns:
            Dictionary with conservative default values
        """
        logger.warning(f"Using fallback data due to: {reason}")
        return {
            'is_honeypot': False,      # Assume not honeypot (let CSV decide)
            'is_mintable': True,       # Assume risky if unknown
            'owner_address': '0x1',    # Assume not renounced
            'buy_tax': 0,              # Unknown tax
            'sell_tax': 0,             # Unknown tax
            'lp_locked_pct': 0,        # Assume unlocked
            'top_10_holder_pct': 100,  # Assume concentrated
        }
