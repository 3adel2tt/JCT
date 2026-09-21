"""
Crypto Sniper Bot - Main Entry Point

This is the main entry point for the Crypto Sniper Bot.
It initializes all modules, validates environment variables,
and starts the Discord bot with the background scanner loop.

SECURITY WARNING:
================================================================================
NEVER use a main cold wallet private key in this bot.
Only use a dedicated hot wallet with limited funds you can afford to lose.
Store your .env file securely and never commit it to version control.
================================================================================
"""

import os
import logging
from dotenv import load_dotenv

# Import bot and module classes
from discord_bot import SniperBot
from on_chain_verifier import OnChainVerifier
from smart_money_tracker import SmartMoneyTracker

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to console
        # Add file handler if needed:
        # logging.FileHandler('sniper_bot.log')
    ]
)

logger = logging.getLogger(__name__)


def validate_environment() -> bool:
    """
    Validates that all required environment variables are set.
    
    Returns:
        True if all required variables are present, False otherwise
    """
    required_vars = [
        'DISCORD_BOT_TOKEN',      # Discord bot authentication
        'DISCORD_CHANNEL_ID',     # Channel for sending alerts
        'ADMIN_USER_ID',          # Admin user for privileged commands
        'RPC_URL',                # Blockchain RPC endpoint
        'SMART_WALLETS',          # Comma-separated list of smart wallets
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.critical("Missing required environment variables:")
        for var in missing:
            logger.critical(f"  - {var}")
        logger.critical("\nPlease copy .env.example to .env and fill in all values.")
        return False
    
    return True


def main():
    """
    Main entry point for the Crypto Sniper Bot.
    
    Initializes all components:
    1. Validates environment configuration
    2. Creates OnChainVerifier for security checks
    3. Creates SmartMoneyTracker for smart money detection
    4. Initializes and runs the Discord bot
    """
    
    logger.info("=" * 60)
    logger.info("🚀 Crypto Sniper Bot Starting...")
    logger.info("=" * 60)
    
    # Step 1: Validate environment variables
    if not validate_environment():
        logger.error("Startup aborted due to missing configuration.")
        return
    
    # Step 2: Parse configuration
    try:
        channel_id = int(os.getenv('DISCORD_CHANNEL_ID'))
        admin_id = int(os.getenv('ADMIN_USER_ID'))
        chain_id = os.getenv('CHAIN_ID', '1')  # Default to Ethereum mainnet
        goplus_key = os.getenv('GOPLUS_API_KEY', '')  # Optional for basic tier
        
        logger.info(f"Configuration loaded:")
        logger.info(f"  - Channel ID: {channel_id}")
        logger.info(f"  - Admin ID: {admin_id}")
        logger.info(f"  - Chain ID: {chain_id}")
        
    except ValueError as e:
        logger.error(f"Invalid configuration format: {e}")
        logger.error("Ensure DISCORD_CHANNEL_ID and ADMIN_USER_ID are valid integers.")
        return
    
    # Step 3: Initialize On-Chain Verifier
    verifier = OnChainVerifier(api_key=goplus_key, chain_id=chain_id)
    logger.info("OnChainVerifier initialized ✓")
    
    # Step 4: Initialize Smart Money Tracker
    smart_wallets_str = os.getenv('SMART_WALLETS', '')
    smart_wallets = [w.strip() for w in smart_wallets_str.split(',') if w.strip()]
    tracker = SmartMoneyTracker(smart_wallets=smart_wallets)
    logger.info(f"SmartMoneyTracker initialized with {len(smart_wallets)} wallets ✓")
    
    # Step 5: Initialize Discord Bot
    bot = SniperBot(
        channel_id=channel_id,
        admin_id=admin_id,
        verifier=verifier,
        tracker=tracker
    )
    logger.info("Discord Bot initialized ✓")
    
    # Step 6: Run the bot
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    logger.info("=" * 60)
    logger.info("✅ All systems ready. Connecting to Discord...")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Bot Commands:")
    logger.info("  /check <address> - Analyze a token contract")
    logger.info("  /status          - View bot statistics")
    logger.info("  /pause           - Pause scanning (Admin only)")
    logger.info("  /resume          - Resume scanning (Admin only)")
    logger.info("  /add_wallet      - Add smart money wallet (Admin only)")
    logger.info("")
    logger.info("SECURITY REMINDER:")
    logger.info("  - Never share your private keys")
    logger.info("  - Only use hot wallets with limited funds")
    logger.info("  - Monitor bot activity regularly")
    logger.info("=" * 60)
    
    try:
        # Start the bot (this blocks until shutdown)
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Shutdown signal received.")
    except Exception as e:
        logger.exception(f"Fatal error running bot: {e}")
    finally:
        logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
