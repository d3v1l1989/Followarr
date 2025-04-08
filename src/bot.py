import os
import discord
import logging
import asyncio
import uvicorn
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from database import Database
from tvdb_client import TVDBClient
from tautulli_client import TautulliClient
from webhook_server import WebhookServer
import traceback
from discord.app_commands import CommandTree
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class CustomCommandTree(CommandTree):
    """Custom command tree with detailed logging"""
    async def sync(self, *, guild=None):
        logger.info(f"Starting command sync {'globally' if guild is None else f'for guild {guild.id}'}")
        try:
            commands = await super().sync(guild=guild)
            logger.info(f"Successfully synced {len(commands)} commands")
            for cmd in commands:
                logger.info(f"Synced command: {cmd.name}")
            return commands
        except Exception as e:
            logger.error(f"Error syncing commands: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Command error in {interaction.command.name if interaction.command else 'unknown command'}")
        logger.error(f"Error details: {str(error)}")
        logger.error(traceback.format_exc())
        await super().on_error(interaction, error)

class FollowarrBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        # Use our custom command tree
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=CustomCommandTree
        )
        
        logger.info("Initializing bot components...")
        
        # Add debug logging for token and application ID
        logger.debug(f"Bot token present: {'Yes' if os.getenv('DISCORD_BOT_TOKEN') else 'No'}")
        
        # Initialize clients
        self.tvdb_client = TVDBClient(os.getenv('TVDB_API_KEY'))
        logger.info(f"TVDB client initialized with API key: {os.getenv('TVDB_API_KEY')[:5]}...")
        
        self.tautulli_client = TautulliClient(
            os.getenv('TAUTULLI_URL'),
            os.getenv('TAUTULLI_API_KEY')
        )
        logger.info("Tautulli client initialized")
        
        self.db = Database()
        logger.info("Database initialized")
        
        # Set up webhook handler
        self.webhook_server = WebhookServer(self.handle_episode_notification)
        logger.info("Webhook server initialized")

        # Set up commands
        self.setup_commands()

    def setup_commands(self):
        @self.tree.command(name="follow", description="Follow a TV show")
        @app_commands.describe(show_name="The name of the show you want to follow")
        async def follow(interaction: discord.Interaction, show_name: str):
            """Follow a TV show"""
            logger.info(f"User {interaction.user} ({interaction.user.id}) trying to follow show: {show_name}")
            
            # Defer the response since TVDB API calls might take some time
            await interaction.response.defer(ephemeral=False)
            
            try:
                show = await self.tvdb_client.search_show(show_name)
                if not show:
                    await interaction.followup.send(f"Could not find show: {show_name}")
                    return
                
                # Get user's current subscriptions
                user_shows = self.db.get_user_shows(str(interaction.user.id))
                if any(s.tvdb_id == show.id for s in user_shows):
                    await interaction.followup.send(f"You are already following {show.name}!")
                    return
                
                # Add the subscription
                self.db.add_subscription(str(interaction.user.id), interaction.user.name, show.id, show.name)
                
                # Create a rich embed for the response
                embed = discord.Embed(
                    title="✅ Show Followed",
                    description=f"You are now following: **{show.name}**",
                    color=discord.Color.green()
                )
                
                # Add show poster if available
                if hasattr(show, 'image_url') and show.image_url:
                    embed.set_thumbnail(url=show.image_url)
                
                # Add show information fields
                if show.overview:
                    # Truncate overview if it's too long
                    overview = show.overview[:1024] + '...' if len(show.overview) > 1024 else show.overview
                    embed.add_field(name="Overview", value=overview, inline=False)
                
                # Format status properly
                status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                embed.add_field(name="Status", value=status, inline=True)
                
                # Add first aired date if available
                if show.first_aired:
                    # Format the date nicely
                    try:
                        air_date = datetime.strptime(show.first_aired, '%Y-%m-%d').strftime('%B %d, %Y')
                        embed.add_field(name="First Aired", value=air_date, inline=True)
                    except ValueError:
                        embed.add_field(name="First Aired", value=show.first_aired, inline=True)
                
                # Add network if available
                if hasattr(show, 'network') and show.network:
                    network_name = show.network if isinstance(show.network, str) else show.network.get('name', 'Unknown')
                    embed.add_field(name="Network", value=network_name, inline=True)
                
                # Set footer with TVDB attribution
                embed.set_footer(text="Data provided by TVDB")
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Successfully added subscription for {interaction.user} to {show.name}")
                
            except Exception as e:
                logger.error(f"Error following show: {str(e)}")
                await interaction.followup.send(f"An error occurred while following the show: {str(e)}")

        @self.tree.command(name="list", description="List all shows you're following")
        async def list_shows(interaction: discord.Interaction):
            try:
                await interaction.response.defer()
                
                logger.info(f"User {interaction.user.name} requested their show list")
                
                # Get user's subscriptions (synchronous call)
                shows = self.db.get_user_subscriptions(str(interaction.user.id))
                logger.info(f"Found {len(shows) if shows else 0} shows for user {interaction.user.name}")
                
                if not shows:
                    await interaction.followup.send("You're not following any shows!")
                    return
                
                embed = discord.Embed(
                    title="Your Followed Shows",
                    color=discord.Color.blue()
                )
                
                for show in shows:
                    embed.add_field(
                        name=show['name'],
                        value=f"ID: {show['id']}",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in list command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="unfollow", description="Unfollow a TV show")
        @app_commands.describe(show_name="The name of the show you want to unfollow")
        async def unfollow(interaction: discord.Interaction, show_name: str):
            try:
                await interaction.response.defer()
                
                logger.info(f"User {interaction.user.name} ({interaction.user.id}) trying to unfollow show: {show_name}")
                
                # Search for show first
                show = await self.tvdb_client.search_show(show_name)
                
                if not show:
                    logger.warning(f"No show found for query: {show_name}")
                    await interaction.followup.send(f"Could not find show: {show_name}")
                    return

                logger.info(f"Found show to unfollow: {show['seriesName']} (ID: {show['id']})")

                # Remove from database
                success = self.db.remove_subscription(
                    str(interaction.user.id),
                    show['id']
                )
                
                if success:
                    logger.info(f"Successfully removed subscription for {interaction.user.name} from {show['seriesName']}")
                    embed = discord.Embed(
                        title="Show Unfollowed",
                        description=f"You are no longer following: {show['seriesName']}",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    logger.info(f"User {interaction.user.name} wasn't following {show['seriesName']}")
                    await interaction.followup.send(f"You weren't following: {show['seriesName']}")
                    
            except Exception as e:
                logger.error(f"Error in unfollow command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

    async def setup_hook(self):
        try:
            logger.info("Initializing database...")
            self.db.init_db()
            
            logger.info("Starting command sync process...")
            # Log the commands that are about to be synced
            commands = self.tree.get_commands()
            logger.info(f"Preparing to sync {len(commands)} commands:")
            for cmd in commands:
                logger.info(f"- Command '{cmd.name}': {cmd.description}")
            
            # Sync commands
            try:
                await self.tree.sync()
                logger.info("Command tree sync completed successfully")
            except discord.errors.Forbidden as e:
                logger.error(f"Forbidden error during sync: {str(e)}")
                logger.error("Bot might lack required permissions")
            except discord.errors.HTTPException as e:
                logger.error(f"HTTP error during sync: {str(e)}")
                logger.error(f"Status: {e.status}, Code: {e.code}")
                logger.error(f"Response: {e.text if hasattr(e, 'text') else 'No response text'}")
            except Exception as e:
                logger.error(f"Unexpected error during sync: {str(e)}")
                logger.error(traceback.format_exc())
            
            # Start webhook server
            logger.info("Starting webhook server...")
            port = int(os.getenv('WEBHOOK_SERVER_PORT', 3000))
            config = uvicorn.Config(
                self.webhook_server.app,
                host="0.0.0.0",
                port=port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            self.webhook_task = asyncio.create_task(server.serve())
            
        except Exception as e:
            logger.error(f"Error during setup: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def on_ready(self):
        logger.info(f"Bot is ready! Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"Bot is in {len(self.guilds)} guilds:")
        for guild in self.guilds:
            logger.info(f"- {guild.name} (ID: {guild.id})")
            
        try:
            # Try to sync commands again and log the results
            commands = await self.tree.sync()
            logger.info(f"Synced {len(commands)} commands on ready")
            for cmd in commands:
                logger.info(f"Command available: {cmd.name}")
        except Exception as e:
            logger.error(f"Error syncing commands on ready: {str(e)}")
            logger.error(traceback.format_exc())

    async def on_command_error(self, ctx, error):
        logger.error(f"Command error: {str(error)}")
        logger.error(traceback.format_exc())

    # Remove or comment out this method since it's not needed
    # async def on_interaction(self, interaction: discord.Interaction):
    #     logger.info(f"Received interaction: {interaction.type}")
    #     logger.info(f"Command name: {interaction.command.name if interaction.command else 'No command'}")
    #     await self.process_interaction(interaction)

    async def handle_episode_notification(self, episode_data: dict):
        try:
            # Get show details from Tautulli
            show_info = await self.tautulli_client.get_show_info(episode_data['grandparent_rating_key'])
            if not show_info:
                logger.error("Could not get show info from Tautulli")
                return

            # Get TVDB show ID
            tvdb_show = await self.tvdb_client.search_show(show_info['title'])
            if not tvdb_show:
                logger.error(f"Could not find show on TVDB: {show_info['title']}")
                return

            # Get subscribers for this show
            subscribers = await self.db.get_show_subscribers(tvdb_show['id'])
            
            if not subscribers:
                logger.info(f"No subscribers for show: {show_info['title']}")
                return

            # Create notification embed
            embed = discord.Embed(
                title=f"🆕 New Episode Added: {show_info['title']}",
                description="A new episode has been added to your media server!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()  # Add timestamp
            )

            # Add episode information
            embed.add_field(
                name="📺 Episode",
                value=f"S{episode_data['season_num']:02d}E{episode_data['episode_num']:02d} - {episode_data['title']}",
                inline=False
            )

            # Add summary if available
            if episode_data.get('summary'):
                embed.add_field(
                    name="📝 Summary",
                    value=episode_data['summary'][:1024],  # Discord has a 1024 character limit for field values
                    inline=False
                )

            # Add air date if available
            if episode_data.get('air_date'):
                embed.add_field(
                    name="📅 Air Date",
                    value=episode_data['air_date'],
                    inline=True
                )

            # Add quality/resolution if available
            if episode_data.get('video_resolution'):
                embed.add_field(
                    name="🎥 Quality",
                    value=episode_data['video_resolution'],
                    inline=True
                )

            # Add duration if available
            if episode_data.get('duration'):
                duration_min = int(episode_data['duration'] / 60)
                embed.add_field(
                    name="⏱️ Duration",
                    value=f"{duration_min} minutes",
                    inline=True
                )

            # Add footer
            embed.set_footer(text="Followarr Notification")

            # Add show image if available
            if episode_data.get('thumb'):
                embed.set_thumbnail(url=episode_data['thumb'])

            # Send DM to each subscriber
            for user_id in subscribers:
                try:
                    user = await self.fetch_user(int(user_id))
                    if user:
                        await user.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send notification to user {user_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling episode notification: {str(e)}")

def main():
    try:
        logger.info("Starting bot...")
        bot = FollowarrBot()
        bot.run(os.getenv('DISCORD_BOT_TOKEN'))
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

if __name__ == "__main__":
    main() 