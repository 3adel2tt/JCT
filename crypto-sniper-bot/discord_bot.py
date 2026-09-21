"""
Discord Bot Module

Main Discord integration for the Crypto Sniper Bot.
Handles background scanning, alert embeds, slash commands, and user interactions.
"""

import discord
from discord import app_commands
from discord.ext import tasks, commands
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

# Import local modules
from decision_engine import make_decision
from on_chain_verifier import OnChainVerifier
from smart_money_tracker import SmartMoneyTracker

logger = logging.getLogger(__name__)


class SniperBot(commands.Bot):
    """
    Main Discord bot class for the Crypto Sniper Bot.
    
    Features:
    - Background task for continuous token scanning
    - Rich embed alerts with color-coded verdicts
    - Interactive buttons for DexScreener, Etherscan, Quick Buy
    - Slash commands for manual checks, status, and admin controls
    
    Attributes:
        channel_id: Discord channel ID for sending alerts
        admin_id: Discord user ID for admin-only commands
        verifier: OnChainVerifier instance for security checks
        tracker: SmartMoneyTracker instance for smart money detection
        is_scanning: Boolean flag controlling the background scanner
        scan_count: Counter for total tokens processed
        start_time: Bot startup timestamp for uptime calculation
    """
    
    def __init__(
        self, 
        channel_id: int, 
        admin_id: int, 
        verifier: OnChainVerifier, 
        tracker: SmartMoneyTracker
    ):
        """
        Initialize the SniperBot.
        
        Args:
            channel_id: Discord channel ID where alerts are sent
            admin_id: Discord user ID with admin privileges
            verifier: Initialized OnChainVerifier instance
            tracker: Initialized SmartMoneyTracker instance
        """
        intents = discord.Intents.default()
        intents.message_content = True  # Required for reading message content
        intents.members = True          # Required for member-related events
        intents.guilds = True           # Required for guild (server) events
        
        super().__init__(command_prefix="!", intents=intents)
        
        self.channel_id = channel_id
        self.admin_id = admin_id
        self.verifier = verifier
        self.tracker = tracker
        
        # State management
        self.is_scanning = False  # Starts paused, use /resume to start
        self.scan_count = 0
        self.start_time: Optional[datetime] = None
        self.scanner_task: Optional[tasks.Loop] = None

    async def on_ready(self):
        """Called when the bot has successfully connected to Discord."""
        logger.info(f'{self.user} has connected to Discord!')
        
        try:
            # CRITICAL FIX: Sync the command tree with Discord
            # This makes slash commands visible and functional immediately
            logger.info("Attempting to sync command tree...")
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} commands.")
            
            # Send startup notification to the configured channel
            channel = self.get_channel(self.channel_id)
            if channel:
                await channel.send(
                    "🟢 **Sniper Bot Online.**\n"
                    "✅ Command tree synced successfully.\n"
                    "Use `/resume` to start scanning.\n"
                    "Use `/status` to check bot stats."
                )
            else:
                logger.warning(f"Could not find channel ID {self.channel_id} to send startup message.")
                
        except discord.errors.HTTPException as e:
            logger.error(f"Failed to sync command tree: {e.code} - {e.text}")
            logger.error("Please check your Bot Token permissions and ensure the bot is invited to the server with 'applications.commands' scope.")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during on_ready: {e}")
        
        # Record startup time for uptime tracking
        self.start_time = datetime.utcnow()
        
        # Start the background scanner loop
        # The loop will wait until the bot is fully ready before starting
        self.scanner_task = self.loop_scanner.start()
        logger.info("Background scanner task initialized (paused by default)")

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """
        Checks if the interaction user has admin privileges.
        
        Args:
            interaction: The Discord interaction to check
            
        Returns:
            True if user is admin, False otherwise (with error message sent)
        """
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message(
                "🔒 **Access Denied:** Admin only command.",
                ephemeral=True  # Only visible to the user
            )
            return False
        return True

    # =========================================================================
    # Background Scanner Loop
    # =========================================================================
    
    @tasks.loop(seconds=10)  # Run every 10 seconds (adjust for production)
    async def loop_scanner(self):
        """
        Background task that continuously scans for new token opportunities.
        
        This loop:
        1. Checks if scanning is enabled (via /pause or /resume)
        2. Simulates receiving a token signal (replace with real data source)
        3. Runs the full decision engine pipeline
        4. Sends alerts for non-SKIP verdicts
        
        Note: In production, replace the simulated signal with:
        - CSV file monitoring
        - WebSocket connection to scanner service
        - Database polling
        """
        if not self.is_scanning:
            return  # Skip iteration if paused
        
        # Process incoming token signals
        await self.process_simulated_signal()

    @loop_scanner.before_loop
    async def before_loop_scanner(self):
        """Ensures the bot is fully ready before starting the scanner loop."""
        await self.wait_until_ready()

    async def process_simulated_signal(self):
        """
        Simulates receiving a token signal and runs the decision engine.
        
        PRODUCTION NOTE: Replace this method with actual data ingestion:
        
        Example for CSV monitoring:
            async def process_csv_signal(self):
                # Read latest row from CSV
                df = pd.read_csv('scanner_output.csv')
                latest = df.iloc[-1]
                csv_metrics = latest.to_dict()
                token_address = latest['contract_address']
                ...
        
        Example for WebSocket:
            async def process_ws_signal(self, message):
                csv_metrics = message['metrics']
                token_address = message['address']
                ...
        """
        # ================================================================
        # SIMULATED DATA - Replace with real data source in production
        # ================================================================
        
        # Mock CSV metrics representing a scanner signal
        mock_csv_metrics = {
            'Rug_Prob': 15.0,          # 15% rug probability
            'Strength_Score': 3.5,     # 3.5/5.0 strength
            'Liquidity': 60000         # $60,000 liquidity
        }
        
        # Mock token address (Ethereum mainnet format)
        mock_token_address = "0x1234567890abcdef1234567890abcdef12345678"
        # ================================================================
        
        self.scan_count += 1
        logger.debug(f"Processing token #{self.scan_count}: {mock_token_address[:10]}...")
        
        # Step 1: Fetch on-chain security data
        on_chain_data = await self.verifier.get_security_data(mock_token_address)
        
        # Step 2: Check for smart money activity
        smart_money = await self.tracker.check_smart_money_activity(mock_token_address)
        
        # Step 3: Run decision engine
        verdict, reason = await make_decision(
            csv_metrics=mock_csv_metrics,
            on_chain_metrics=on_chain_data,
            smart_money_detected=smart_money
        )
        
        logger.info(f"Verdict for {mock_token_address[:10]}...: {verdict} - {reason}")
        
        # Step 4: Send alert if not SKIP
        if verdict != "SKIP":
            await self.send_alert_embed(
                verdict=verdict,
                reason=reason,
                address=mock_token_address,
                csv_met=mock_csv_metrics,
                onchain_met=on_chain_data,
                smart_money=smart_money
            )

    async def send_alert_embed(
        self, 
        verdict: str, 
        reason: str, 
        address: str, 
        csv_met: dict, 
        onchain_met: dict, 
        smart_money: bool
    ):
        """
        Sends a rich embed alert to the configured Discord channel.
        
        Args:
            verdict: Decision engine verdict (STRONG_BUY, BUY, etc.)
            reason: Explanation for the verdict
            address: Token contract address
            csv_met: CSV metrics dictionary
            onchain_met: On-chain metrics dictionary
            smart_money: Boolean indicating smart money detection
        """
        channel = self.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Channel {self.channel_id} not found")
            return

        # Determine embed color and title based on verdict
        color = discord.Color.red()
        title = "🛑 SKIP"
        emoji = "❌"
        
        if "STRONG_BUY" in verdict:
            color = discord.Color.green()
            title = "🚀 STRONG BUY"
            emoji = "💎"
        elif "BUY" in verdict:
            color = discord.Color.green()
            title = "✅ BUY"
            emoji = "🔵"
        elif "SPECULATIVE_BUY" in verdict:
            color = discord.Color.gold()
            title = "⚡ SPECULATIVE BUY"
            emoji = "🔥"
        elif "WATCH_ONLY" in verdict:
            color = discord.Color.orange()
            title = "👀 WATCH ONLY"
            emoji = "⏳"

        # Build the embed
        embed = discord.Embed(
            title=f"{emoji} {title}",
            description=f"**Reason:** {reason}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Add fields with token information
        embed.add_field(
            name="📍 Token Address",
            value=f"`{address[:10]}...{address[-8:]}`",
            inline=False
        )
        embed.add_field(
            name="💧 Liquidity",
            value=f"${csv_met.get('Liquidity', 0):,.0f}",
            inline=True
        )
        embed.add_field(
            name="💪 Strength",
            value=f"{csv_met.get('Strength_Score', 0)}/5.0",
            inline=True
        )
        embed.add_field(
            name="🧠 Smart Money",
            value="✅ Yes" if smart_money else "❌ No",
            inline=True
        )
        embed.add_field(
            name="🍯 Honeypot Risk",
            value="⚠️ Yes" if onchain_met.get('is_honeypot') else "✅ No",
            inline=True
        )
        embed.add_field(
            name="💰 Buy Tax",
            value=f"{onchain_met.get('buy_tax', 0)}%",
            inline=True
        )
        embed.add_field(
            name="📉 Sell Tax",
            value=f"{onchain_met.get('sell_tax', 0)}%",
            inline=True
        )
        embed.add_field(
            name="🔒 LP Locked",
            value=f"{onchain_met.get('lp_locked_pct', 0):.1f}%",
            inline=True
        )
        embed.add_field(
            name="🏆 Top 10 Holders",
            value=f"{onchain_met.get('top_10_holder_pct', 0)}%",
            inline=True
        )
        
        # Footer with timestamp
        embed.set_footer(text="Crypto Sniper Bot | Real-time Analysis")

        # Create interactive buttons
        view = discord.ui.View()
        
        # DexScreener button
        view.add_item(
            discord.ui.Button(
                label="DexScreener",
                url=f"https://dexscreener.com/ethereum/{address}",
                emoji="📊"
            )
        )
        
        # Etherscan button
        view.add_item(
            discord.ui.Button(
                label="Etherscan",
                url=f"https://etherscan.io/address/{address}",
                emoji="🔍"
            )
        )
        
        # Quick Buy button (requires callback for actual trading)
        buy_button = discord.ui.Button(
            label="⚡ Quick Buy",
            style=discord.ButtonStyle.blurple,
            custom_id="buy_btn"
        )
        view.add_item(buy_button)

        # Send the embed with buttons
        try:
            await channel.send(embed=embed, view=view)
            logger.info(f"Alert sent for {address[:10]}... with verdict {verdict}")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    # =========================================================================
    # Slash Commands
    # =========================================================================

    @app_commands.command(name="check", description="Manually verify a token contract address")
    async def check_command(self, interaction: discord.Interaction, address: str):
        """
        Manually triggers the On-Chain Verifier for a specific token.
        
        Args:
            interaction: Discord interaction
            address: Token contract address to analyze
        """
        await interaction.response.defer()  # Acknowledge the command
        
        try:
            on_chain_data = await self.verifier.get_security_data(address)
            
            # Build security report embed
            embed = discord.Embed(
                title=f"🔍 Security Report: `{address[:10]}...{address[-8:]}`",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Add security metrics
            embed.add_field(
                name="🍯 Honeypot",
                value="⚠️ Yes" if on_chain_data.get('is_honeypot') else "✅ No",
                inline=True
            )
            embed.add_field(
                name="🏭 Mintable",
                value="⚠️ Yes" if on_chain_data.get('is_mintable') else "✅ No",
                inline=True
            )
            embed.add_field(
                name="💸 Buy Tax",
                value=f"{on_chain_data.get('buy_tax', 0)}%",
                inline=True
            )
            embed.add_field(
                name="💸 Sell Tax",
                value=f"{on_chain_data.get('sell_tax', 0)}%",
                inline=True
            )
            embed.add_field(
                name="🔒 LP Locked",
                value=f"{on_chain_data.get('lp_locked_pct', 0):.2f}%",
                inline=True
            )
            embed.add_field(
                name="🏆 Top 10 Holders",
                value=f"{on_chain_data.get('top_10_holder_pct', 0)}%",
                inline=True
            )
            
            # Overall risk assessment
            risk_level = "LOW"
            risk_color = discord.Color.green()
            
            if on_chain_data.get('is_honeypot'):
                risk_level = "CRITICAL - HONEYPOT"
                risk_color = discord.Color.red()
            elif on_chain_data.get('is_mintable'):
                risk_level = "HIGH - Mintable"
                risk_color = discord.Color.orange()
            elif on_chain_data.get('buy_tax', 0) > 10 or on_chain_data.get('sell_tax', 0) > 10:
                risk_level = "MEDIUM - High Tax"
                risk_color = discord.Color.gold()
            
            embed.add_field(
                name="⚠️ Risk Level",
                value=risk_level,
                inline=False
            )
            embed.color = risk_color
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.exception(f"Error in /check command: {e}")
            await interaction.followup.send(
                f"❌ Error analyzing token: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="status", description="Show bot uptime and statistics")
    async def status_command(self, interaction: discord.Interaction):
        """Returns bot uptime, scan count, and current state."""
        uptime = datetime.utcnow() - self.start_time if self.start_time else timedelta(0)
        
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.greyple(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="⏱️ Uptime",
            value=str(uptime).split('.')[0],  # Remove microseconds
            inline=True
        )
        embed.add_field(
            name="📊 Tokens Scanned",
            value=str(self.scan_count),
            inline=True
        )
        embed.add_field(
            name="🔄 Scanner State",
            value="🟢 Running" if self.is_scanning else "🔴 Paused",
            inline=True
        )
        embed.add_field(
            name="🧠 Smart Wallets Tracked",
            value=str(self.tracker.get_tracked_count()),
            inline=True
        )
        
        embed.set_footer(text=f"Bot Version 1.0 | {self.user.name}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pause", description="Pause the scanner (Admin Only)")
    async def pause_command(self, interaction: discord.Interaction):
        """Pauses the background scanner loop. Admin only."""
        if not await self.is_admin(interaction):
            return
        
        self.is_scanning = False
        await interaction.response.send_message(
            "⏸️ **Scanner Paused.**\nNo new tokens will be analyzed until resumed.",
            ephemeral=True
        )
        logger.info("Scanner paused by admin")

    @app_commands.command(name="resume", description="Resume the scanner (Admin Only)")
    async def resume_command(self, interaction: discord.Interaction):
        """Resumes the background scanner loop. Admin only."""
        if not await self.is_admin(interaction):
            return
        
        self.is_scanning = True
        await interaction.response.send_message(
            "▶️ **Scanner Resumed.**\nMonitoring for new token opportunities...",
            ephemeral=True
        )
        logger.info("Scanner resumed by admin")

    @app_commands.command(name="add_wallet", description="Add a wallet to smart money tracking (Admin Only)")
    async def add_wallet_command(self, interaction: discord.Interaction, address: str):
        """
        Dynamically adds a wallet to the smart money tracking list.
        
        Args:
            interaction: Discord interaction
            address: Wallet address to track
        """
        if not await self.is_admin(interaction):
            return
        
        success = self.tracker.add_smart_wallet(address)
        
        if success:
            await interaction.response.send_message(
                f"✅ Added `{address[:10]}...{address[-8:]}` to smart money tracking.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ Wallet already being tracked or invalid address.",
                ephemeral=True
            )

    async def on_interaction(self, interaction: discord.Interaction):
        """
        Handles button interactions from alert embeds.
        
        Currently handles the "Quick Buy" button click.
        """
        if interaction.type == discord.InteractionType.component:
            if interaction.data.get('custom_id') == 'buy_btn':
                # IMPORTANT: Trading execution is disabled in this demo
                # To enable live trading, you would:
                # 1. Verify the user's identity/permissions
                # 2. Use web3.py to construct and sign a transaction
                # 3. Broadcast to the network via RPC
                
                await interaction.response.send_message(
                    "⚠️ **Trading Execution Disabled in Demo Mode**\n\n"
                    "To enable live swaps:\n"
                    "1. Configure `SNIPER_WALLET_PRIVATE_KEY` in .env\n"
                    "2. Implement swap logic using web3.py\n"
                    "3. Add proper risk management and position sizing\n\n"
                    "**SECURITY WARNING:** Never use a main cold wallet!",
                    ephemeral=True
                )
