"""
Decision Engine Module

Implements the Two-Tier Decision Engine that combines scanner metrics
with on-chain data and smart money tracking to make trading decisions.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


async def make_decision(csv_metrics: dict, on_chain_metrics: dict, smart_money_detected: bool) -> Tuple[str, str]:
    """
    Core Decision Engine implementing the Two-Tier Logic.
    
    This function evaluates token safety and opportunity using a phased approach:
    - Phase 0: Smart Money Override (bypasses strict filters if smart money detected)
    - Phase 1: Hard Veto (instant kills for dangerous tokens)
    - Phase 2: Blue Chip Bypass (ignores Rug_Prob for safe high-liquidity tokens)
    - Phase 3: Degen Sniper (strict CSV-based filtering for risky tokens)
    
    Args:
        csv_metrics: Dictionary containing scanner metrics from CSV/Websocket
            - Rug_Prob: Risk probability percentage (0-100)
            - Strength_Score: Heuristic strength score (0-5)
            - Liquidity: Token liquidity in USD
        on_chain_metrics: Dictionary containing on-chain security data
            - is_honeypot: Boolean indicating honeypot risk
            - is_mintable: Boolean indicating if tokens can be minted
            - owner_address: Contract owner address (0x0 if renounced)
            - buy_tax: Buy tax percentage
            - sell_tax: Sell tax percentage
            - lp_locked_pct: Percentage of LP tokens locked
            - top_10_holder_pct: Percentage held by top 10 wallets
        smart_money_detected: Boolean indicating if known profitable wallets bought
    
    Returns:
        Tuple[str, str]: (Verdict, Reason)
        Verdict options:
            - STRONG_BUY: Smart money detected with safe conditions
            - BUY: Blue chip characteristics confirmed
            - SPECULATIVE_BUY: Passed strict degen filters
            - WATCH_ONLY: Safe structure but insufficient metrics
            - SKIP: Failed safety checks
    """
    
    # Extract On-Chain Metrics with safe defaults
    is_honeypot = on_chain_metrics.get('is_honeypot', False)
    is_mintable = on_chain_metrics.get('is_mintable', False)
    owner_address = on_chain_metrics.get('owner_address', '0x0')
    buy_tax = float(on_chain_metrics.get('buy_tax', 0))
    sell_tax = float(on_chain_metrics.get('sell_tax', 0))
    lp_locked_pct = float(on_chain_metrics.get('lp_locked_pct', 0))
    top_10_holder_pct = float(on_chain_metrics.get('top_10_holder_pct', 100))
    
    # Extract CSV Metrics
    rug_prob = float(csv_metrics.get('Rug_Prob', 100))
    strength_score = float(csv_metrics.get('Strength_Score', 0))
    liquidity = float(csv_metrics.get('Liquidity', 0))

    # =========================================================================
    # Phase 0: Smart Money Override
    # =========================================================================
    # Condition: Smart Money detected AND Not Honeypot AND Buy Tax < 15%
    # Action: Return STRONG_BUY, bypass all strict CSV filters
    # =========================================================================
    if smart_money_detected and not is_honeypot and buy_tax < 15.0:
        logger.info("Phase 0 Triggered: Smart Money Detected.")
        return "STRONG_BUY", "Smart Money Inflow Detected"

    # =========================================================================
    # Phase 1: Hard Veto (Instant Kills)
    # =========================================================================
    # Condition: Honeypot OR (Mintable + Non-Renounced Owner) OR (Tax > 15%)
    # Action: Return SKIP immediately
    # =========================================================================
    owner_renounced = (
        owner_address == '0x0' or 
        owner_address == '0x0000000000000000000000000000000000000000'
    )
    
    if is_honeypot:
        logger.warning(f"Hard Veto: Honeypot detected for token")
        return "SKIP", "Hard Veto: Honeypot Detected"
    
    if is_mintable and not owner_renounced:
        logger.warning(f"Hard Veto: Mintable token with non-renounced owner")
        return "SKIP", "Hard Veto: Mintable + Owner Not Renounced"
    
    if buy_tax > 15.0 or sell_tax > 15.0:
        logger.warning(f"Hard Veto: High tax detected (Buy: {buy_tax}%, Sell: {sell_tax}%)")
        return "SKIP", f"Hard Veto: High Tax (Buy: {buy_tax}%, Sell: {sell_tax}%)"

    # =========================================================================
    # Phase 2: Blue Chip Bypass (The "PONS" Fix)
    # =========================================================================
    # Condition: LP Locked > 90% AND Top 10 Holders < 15%
    # Action: Ignore Rug_Prob entirely. If Strength >= 2.5 AND Liq >= 50000, BUY
    # =========================================================================
    if lp_locked_pct > 90.0 and top_10_holder_pct < 15.0:
        logger.info(f"Phase 2 Triggered: Blue Chip Characteristics (LP: {lp_locked_pct}%, Top10: {top_10_holder_pct}%)")
        
        # Ignore Rug_Prob entirely here - safe structure overrides heuristic risk
        if strength_score >= 2.5 and liquidity >= 50000:
            return "BUY", "Blue Chip Confirmed (High Liquidity/Safe)"
        else:
            return "WATCH_ONLY", "Blue Chip Structure but Low Strength/Liq"

    # =========================================================================
    # Phase 3: Degen Sniper (Strict CSV Rules)
    # =========================================================================
    # Condition: Fallback for all other tokens (unlocked LP, high dev concentration)
    # Action: Strict CSV filtering - Rug_Prob < 25%, Strength >= 3.0, Liq >= 5000
    # =========================================================================
    if rug_prob < 25.0 and strength_score >= 3.0 and liquidity >= 5000:
        logger.info(f"Phase 3 Triggered: Degen Play passed strict filters")
        return "SPECULATIVE_BUY", "Degen Play: Passed Strict CSV Filters"
    
    logger.info(f"Token skipped: RugProb={rug_prob}, Strength={strength_score}, Liq={liquidity}")
    return "SKIP", "Degen Filter Failed (High Risk/Low Strength)"
