import os
import discord
import logging
import asyncio
import uvicorn
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from src.database import Database
from src.tvdb_client import TVDBClient
from src.plex_client import PlexClient
from src.webhook_server import WebhookServer
import traceback
from discord.app_commands import CommandTree
from datetime import datetime, timedelta, timezone
import calendar
from collections import defaultdict
from typing import Dict, Any

# Load env vars and setup logging
load_dotenv()
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CustomCommandTree(CommandTree):
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
        """Initialize the bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=CustomCommandTree
        )
        
        # Get environment variables
        self.discord_token = os.getenv('DISCORD_BOT_TOKEN')
        self.channel_id = int(os.getenv('DISCORD_CHANNEL_ID'))
        self.tvdb_api_key = os.getenv('TVDB_API_KEY')
        self.plex_url = os.getenv('PLEX_URL')
        self.plex_token = os.getenv('PLEX_TOKEN')
        
        # Initialize database with proper URL
        db_url = os.getenv('DATABASE_URL', 'sqlite:////app/data/followarr.db')
        if not db_url.startswith('sqlite+aiosqlite:///'):
            db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        self.db = Database(db_url)
        
        # Initialize other components
        self.tvdb_client = TVDBClient(self.tvdb_api_key)
        self.plex_client = PlexClient(self.plex_url, self.plex_token)
        
        # Initialize webhook server
        self.webhook_server = WebhookServer(self.handle_plex_notification)
        
        logger.info("Initializing bot components...")
        
        # Setup slash commands
        self.setup_commands()

        # Start the webhook server
        self.webhook_server_task = None

    def setup_commands(self):
        @self.tree.command(name="follow", description="Follow a TV show to receive notifications")
        async def follow(interaction: discord.Interaction, show_name: str):
            """Follow a TV show to receive notifications."""
            try:
                logger.info(f"User {interaction.user.name} requested to follow show: {show_name}")
                # Search for the show using TVDB
                show = await self.tvdb_client.search_show(show_name)
                if not show:
                    logger.warning(f"Could not find show: {show_name}")
                    await interaction.response.send_message(
                        f"❌ Could not find show: {show_name}",
                        ephemeral=True
                    )
                    return

                logger.info(f"Found show: {show.name} (ID: {show.id})")
                # Add the show to the user's follows
                await self.db.add_follower(interaction.user.id, show.id, show.name)
                
                # Create follow confirmation embed
                embed = discord.Embed(
                    title="✅ Show Followed",
                    description=f"You are now following: **{show.name}**",
                    color=discord.Color.green()
                )
                
                # Add show details to embed
                if show.overview:
                    overview = show.overview[:1024] + '...' if len(show.overview) > 1024 else show.overview
                    embed.add_field(name="Overview", value=overview, inline=False)
                
                if show.status:
                    status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                    embed.add_field(name="Status", value=status, inline=True)
                
                if show.image_url:
                    try:
                        logger.info(f"Attempting to set thumbnail for {show.name} with URL: {show.image_url}")
                        embed.set_thumbnail(url=show.image_url)
                        logger.info(f"Successfully set thumbnail for {show.name}")
                    except Exception as e:
                        logger.error(f"Error setting thumbnail for {show.name}: {str(e)}")
                        logger.error(traceback.format_exc())
                
                embed.set_footer(text="Data provided by TVDB")
                
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in follow command: {str(e)}")
                logger.error(traceback.format_exc())
                await interaction.response.send_message(
                    "❌ An error occurred while processing your request.",
                    ephemeral=True
                )

        @self.tree.command(name="list", description="List all shows you're following")
        async def list_shows(interaction: discord.Interaction):
            """List all shows you're following."""
            try:
                await interaction.response.defer()
                
                shows = await self.db.get_user_subscriptions(str(interaction.user.id))
                
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
                        value="\u200b",  # Zero-width space for empty value
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in list command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="unfollow", description="Unfollow a TV show")
        @app_commands.describe(show_name="The name of the show you want to unfollow")
        async def unfollow(interaction: discord.Interaction, show_name: str):
            """Unfollow a TV show."""
            try:
                logger.info(f"User {interaction.user.name} requested to unfollow show: {show_name}")
                await interaction.response.defer()
                
                # Get user's followed shows
                user_follows = await self.db.get_user_follows(str(interaction.user.id))
                if not user_follows:
                    logger.info(f"User {interaction.user.name} has no followed shows")
                    await interaction.followup.send("You're not following any shows!")
                    return
                
                logger.info(f"User {interaction.user.name} follows {len(user_follows)} shows")
                # Find the show (case-insensitive)
                show_to_unfollow = None
                for show in user_follows:
                    if show['show_title'].lower() == show_name.lower():
                        show_to_unfollow = show
                        break
                
                if not show_to_unfollow:
                    logger.warning(f"User {interaction.user.name} tried to unfollow {show_name} but wasn't following it")
                    await interaction.followup.send(f"You're not following {show_name}!")
                    return
                
                logger.info(f"Found show to unfollow: {show_to_unfollow['show_title']} (ID: {show_to_unfollow['show_id']})")
                # Remove follower
                success = await self.db.remove_follower(interaction.user.id, show_to_unfollow['show_title'])
                if not success:
                    logger.error(f"Failed to remove follower for show: {show_to_unfollow['show_title']}")
                    await interaction.followup.send("Failed to unfollow the show. Please try again later.")
                    return
                
                # Check if this is a movie ID (starts with 'movie-')
                if isinstance(show_to_unfollow['show_id'], str) and show_to_unfollow['show_id'].startswith('movie-'):
                    # For movies, just send a simple confirmation
                    await interaction.followup.send(f"Successfully unfollowed {show_to_unfollow['show_title']}!")
                    return
                
                # Get show details for the embed
                show_details = await self.tvdb_client.get_show_details(show_to_unfollow['show_id'])
                if not show_details:
                    logger.warning(f"Could not get show details for {show_to_unfollow['show_title']}")
                    await interaction.followup.send(f"Successfully unfollowed {show_to_unfollow['show_title']}!")
                    return
                
                # Create unfollow confirmation embed
                embed = discord.Embed(
                    title="Show Unfollowed",
                    description=f"You are no longer following {show_to_unfollow['show_title']}",
                    color=discord.Color.red()
                )
                
                if show_details.get('overview'):
                    overview = show_details['overview'][:100] + '...' if len(show_details['overview']) > 100 else show_details['overview']
                    embed.add_field(name="Overview", value=overview, inline=False)
                
                if show_details.get('status'):
                    embed.add_field(name="Status", value=show_details['status'], inline=True)
                
                if show_details.get('image'):
                    try:
                        # Ensure the URL is valid
                        if show_details['image'].startswith('http'):
                            logger.info(f"Setting thumbnail for {show_to_unfollow['show_title']} with URL: {show_details['image']}")
                            embed.set_thumbnail(url=show_details['image'])
                            logger.info(f"Successfully set thumbnail for {show_to_unfollow['show_title']}")
                        else:
                            logger.warning(f"Invalid image URL for {show_to_unfollow['show_title']}: {show_details['image']}")
                    except Exception as e:
                        logger.error(f"Error setting thumbnail for {show_to_unfollow['show_title']}: {str(e)}")
                        logger.error(traceback.format_exc())
                
                embed.set_footer(text="Data provided by TVDB")
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in unfollow command: {str(e)}")
                logger.error(traceback.format_exc())
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="calendar", description="View upcoming episodes for your followed shows")
        async def calendar(interaction: discord.Interaction):
            """View upcoming episodes for your followed shows."""
            try:
                await interaction.response.defer()
                
                # Get user's followed shows
                shows = await self.db.get_user_follows(str(interaction.user.id))
                if not shows:
                    await interaction.followup.send("You're not following any shows!")
                    return
                
                # Create calendar embed
                embed = discord.Embed(
                    title="📅 Upcoming Episodes",
                    description="Here are the upcoming episodes for your followed shows:",
                    color=discord.Color.blue()
                )
                
                # Get upcoming episodes for each show
                for show in shows:
                    try:
                        show_details = await self.tvdb_client.get_show_details(show['show_id'])
                        if not show_details:
                            logger.warning(f"Could not get show details for {show['show_title']}")
                            continue
                            
                        # Get next episode
                        next_episode = show_details.get('nextAiredEpisode')
                        if not next_episode:
                            logger.info(f"No upcoming episodes found for {show['show_title']}")
                            continue
                            
                        # Format episode info
                        episode_info = f"**S{next_episode['seasonNumber']}E{next_episode['episodeNumber']}** - {next_episode['episodeName']}\n"
                        episode_info += f"📅 {next_episode['firstAired']}\n"
                        
                        if next_episode.get('overview'):
                            overview = next_episode['overview'][:100] + '...' if len(next_episode['overview']) > 100 else next_episode['overview']
                            episode_info += f"📝 {overview}\n"
                        
                        # Add to embed
                        embed.add_field(
                            name=show['show_title'],
                            value=episode_info,
                            inline=False
                        )
                        
                    except Exception as e:
                        logger.error(f"Error getting episodes for {show['show_title']}: {str(e)}")
                        logger.error(traceback.format_exc())
                        continue
                
                if not embed.fields:
                    await interaction.followup.send("No upcoming episodes found for your followed shows.")
                    return
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in calendar command: {str(e)}")
                logger.error(traceback.format_exc())
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

    async def setup_hook(self):
        """Setup hook that runs after the bot is ready."""
        # Start the webhook server
        config = uvicorn.Config(
            self.webhook_server.app,
            host="0.0.0.0",
            port=int(os.getenv('WEBHOOK_SERVER_PORT', 3000)),
            log_level="info"
        )
        server = uvicorn.Server(config)
        self.webhook_server_task = asyncio.create_task(server.serve())

    async def close(self):
        """Cleanup when the bot is shutting down."""
        if self.webhook_server_task:
            self.webhook_server_task.cancel()
            try:
                await self.webhook_server_task
            except asyncio.CancelledError:
                pass
        await super().close()

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        logger.info('Bot is ready and online!')
        
        # Initialize DB here
        try:
            logger.info("Initializing database...")
            await self.db.init_db()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing database in on_ready: {e}", exc_info=True)
            # Depending on severity, you might want to close the bot
            # await self.close()
            # return

        # Sync commands
        try:
            logger.info("Syncing commands...")
            synced_commands = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced_commands)} commands")
            for cmd in synced_commands:
                logger.info(f"Command available: {cmd.name}")
        except discord.errors.Forbidden as e:
            logger.error(
                "Bot lacks 'applications.commands' scope. "
                "Please re-invite the bot with the correct scope."
            )
            logger.error("You need to re-invite the bot with the 'applications.commands' scope.")
            logger.error("Visit the Discord Developer Portal, go to your application's OAuth2 page,")
            logger.error("and make sure 'applications.commands' is selected in the scopes.")
        except Exception as e:
            logger.error(f"Error syncing commands: {str(e)}")
            logger.error(traceback.format_exc())

    async def on_command_error(self, ctx, error):
        logger.error(f"Command error: {str(error)}")
        logger.error(traceback.format_exc())

    async def handle_plex_notification(self, payload: dict):
        """Handle incoming Plex notifications."""
        try:
            logger.info(f"Processing Plex notification: {payload}")
            
            # Check if this is a new episode
            if payload.get('event') != 'library.new':
                logger.info(f"Ignoring non-library.new event: {payload.get('event')}")
                return
            
            metadata = payload.get('Metadata', {})
            if metadata.get('type') != 'episode':
                logger.info("Ignoring non-episode content")
                return
            
            # Get show title and episode info
            show_title = metadata.get('grandparentTitle')
            if not show_title:
                logger.error("No show title found in metadata")
                return
                
            logger.info(f"Processing new episode for show: {show_title}")
            
            # Get followers for this show
            followers = await self.db.get_show_followers(show_title)
            if not followers:
                logger.info(f"No followers found for show: {show_title}")
                return
                
            logger.info(f"Found {len(followers)} followers for {show_title}")
            
            # Get episode details
            season_num = metadata.get('parentIndex')
            episode_num = metadata.get('index')
            episode_title = metadata.get('title', f'Episode {episode_num}')
            
            # Get show poster URL
            thumb = metadata.get('grandparentThumb', '')
            if thumb:
                # Convert relative URL to absolute
                thumb = f"{self.plex_url}{thumb}?X-Plex-Token={self.plex_token}"
            
            # Create embed for notification
            embed = discord.Embed(
                title=f"New Episode: {show_title}",
                description=f"Season {season_num} Episode {episode_num}: {episode_title}",
                color=discord.Color.blue()
            )
            
            if thumb:
                embed.set_thumbnail(url=thumb)
            
            # Send notification to each follower
            for user_id in followers:
                try:
                    user = await self.fetch_user(user_id)
                    if user:
                        await user.send(embed=embed)
                        logger.info(f"Sent notification to user {user_id} for {show_title}")
                    else:
                        logger.warning(f"Could not find user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending notification to user {user_id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error processing Plex notification: {str(e)}")
            logger.error(traceback.format_exc())

def main():
    try:
        bot = FollowarrBot()
        bot.run(os.getenv('DISCORD_BOT_TOKEN'))
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        raise

if __name__ == "__main__":
    main() 