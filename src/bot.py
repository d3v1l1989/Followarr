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
        @self.tree.command(name="follow", description="Follow a TV show")
        @app_commands.describe(show_name="The name of the show you want to follow")
        async def follow(interaction: discord.Interaction, show_name: str):
            """Follow a TV show."""
            try:
                await interaction.response.defer(ephemeral=False)
                
                # Search for the show
                show = await self.tvdb_client.search_show(show_name)
                if not show:
                    await interaction.followup.send(f"Could not find show: {show_name}")
                    return
                
                # Check if user is already following the show
                user_follows = await self.db.get_user_follows(interaction.user.id)
                if show_name in user_follows:
                    await interaction.followup.send(f"You are already following {show_name}!")
                    return
                
                # Add follower
                success = await self.db.add_follower(interaction.user.id, show_name)
                if not success:
                    await interaction.followup.send(f"Failed to follow {show_name}. Please try again.")
                    return
                
                # Create follow confirmation embed
                embed = discord.Embed(
                    title="✅ Show Followed",
                    description=f"You are now following: **{show_name}**",
                    color=discord.Color.green()
                )
                
                if hasattr(show, 'image_url') and show.image_url:
                    try:
                        embed.set_thumbnail(url=show.image_url)
                    except Exception as e:
                        logger.error(f"Error setting thumbnail: {str(e)}")
                        try:
                            embed.set_image(url=show.image_url)
                        except Exception as e:
                            logger.error(f"Error setting main image: {str(e)}")
                
                if show.overview:
                    overview = show.overview[:1024] + '...' if len(show.overview) > 1024 else show.overview
                    embed.add_field(name="Overview", value=overview, inline=False)
                
                status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                embed.add_field(name="Status", value=status, inline=True)
                
                if show.first_aired:
                    try:
                        air_date = datetime.strptime(show.first_aired, '%Y-%m-%d').strftime('%B %d, %Y')
                        embed.add_field(name="First Aired", value=air_date, inline=True)
                    except ValueError:
                        embed.add_field(name="First Aired", value=show.first_aired, inline=True)
                
                if hasattr(show, 'network') and show.network:
                    network_name = show.network if isinstance(show.network, str) else show.network.get('name', 'Unknown')
                    embed.add_field(name="Network", value=network_name, inline=True)
                
                embed.set_footer(text="Data provided by TVDB")
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error following show: {str(e)}")
                await interaction.followup.send(f"An error occurred while following the show: {str(e)}")

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
                await interaction.response.defer()
                
                # Check if user is following the show
                user_follows = await self.db.get_user_follows(interaction.user.id)
                if show_name not in user_follows:
                    await interaction.followup.send(f"You are not following {show_name}!")
                    return
                
                # Remove follower
                success = await self.db.remove_follower(interaction.user.id, show_name)
                if not success:
                    await interaction.followup.send(f"Failed to unfollow {show_name}. Please try again.")
                    return
                
                # Create unfollow confirmation embed
                embed = discord.Embed(
                    title="❌ Show Unfollowed",
                    description=f"You are no longer following: **{show_name}**",
                    color=discord.Color.red()
                )
                
                # Try to get show details for the embed
                show = await self.tvdb_client.search_show(show_name)
                if show:
                    if hasattr(show, 'image_url') and show.image_url:
                        try:
                            embed.set_thumbnail(url=show.image_url)
                        except Exception as e:
                            logger.error(f"Error setting thumbnail: {str(e)}")
                    
                    if show.overview:
                        overview = show.overview[:1024] + '...' if len(show.overview) > 1024 else show.overview
                        embed.add_field(name="Overview", value=overview, inline=False)
                    
                    if show.status:
                        status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                        embed.add_field(name="Status", value=status, inline=True)
                    
                    embed.set_footer(text="Data provided by TVDB")
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in unfollow command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="calendar", description="Shows upcoming episodes for all shows")
        async def calendar(interaction: discord.Interaction):
            """Shows upcoming episodes for all shows"""
            try:
                await interaction.response.defer()
                
                # Get user's followed shows
                shows = await self.db.get_user_follows(interaction.user.id)
                if not shows:
                    await interaction.followup.send("You're not following any shows! Use `/follow` to add some.")
                    return

                # Get upcoming episodes for all shows
                all_episodes = []
                for show_name in shows:
                    try:
                        show = await self.tvdb_client.search_show(show_name)
                        if not show:
                            logger.warning(f"Could not find show in TVDB: {show_name}")
                            continue
                            
                        episodes = await self.tvdb_client.get_upcoming_episodes(show['id'])
                        for episode in episodes:
                            episode['show_name'] = show_name
                            all_episodes.append(episode)
                    except Exception as e:
                        logger.error(f"Error getting episodes for {show_name}: {str(e)}")
                        continue

                if not all_episodes:
                    await interaction.followup.send("No upcoming episodes found for your shows.")
                    return

                # Sort episodes by air date
                all_episodes.sort(key=lambda x: x.get('aired', ''))

                # Group episodes by month
                monthly_episodes = {}
                for episode in all_episodes:
                    air_date_str = episode.get('aired')
                    if not air_date_str:
                        continue
                        
                    try:
                        if 'T' in air_date_str:
                            air_date = datetime.fromisoformat(air_date_str.replace('Z', '+00:00'))
                        else:
                            air_date = datetime.strptime(air_date_str, "%Y-%m-%d")
                            air_date = air_date.replace(tzinfo=timezone.utc)
                            
                        # Skip episodes more than 6 months in the future
                        if (air_date - datetime.now(timezone.utc)).days > 180:
                            continue
                            
                        month_key = air_date.strftime("%B %Y")
                        if month_key not in monthly_episodes:
                            monthly_episodes[month_key] = []
                        monthly_episodes[month_key].append(episode)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing episode date: {e}")
                        continue

                # Create embeds for each month
                embeds = []
                
                # Add summary embed
                summary_embed = discord.Embed(
                    title="Upcoming Episodes Summary",
                    color=discord.Color.blue()
                )
                
                if all_episodes:
                    next_episode = all_episodes[0]
                    next_air_date_str = next_episode.get('aired')
                    if next_air_date_str:
                        try:
                            if 'T' in next_air_date_str:
                                next_air_date = datetime.fromisoformat(next_air_date_str.replace('Z', '+00:00'))
                            else:
                                next_air_date = datetime.strptime(next_air_date_str, "%Y-%m-%d")
                                next_air_date = next_air_date.replace(tzinfo=timezone.utc)
                                
                            # Try different field names for season and episode
                            season = next_episode.get('seasonNumber', '?')
                            episode = next_episode.get('number', '?')
                            episode_name = next_episode.get('name', 'TBA')
                            
                            next_ep_text = f"{next_episode['show_name']} S{season}E{episode}"
                            if episode_name and episode_name.lower() != 'tba':
                                next_ep_text += f" - {episode_name}"
                            
                            # Get show details to get the poster image
                            show_details = await self.tvdb_client.get_show_details(next_episode['seriesId'])
                            if show_details and show_details.get('image'):
                                summary_embed.set_thumbnail(url=show_details['image'])
                            
                            # Build the episode description
                            episode_description = f"{next_ep_text}\n{next_air_date.strftime('%B %d, %Y at %I:%M %p %Z')}"
                            
                            # Add episode overview if available
                            episode_overview = next_episode.get('overview')
                            if episode_overview:
                                episode_description += f"\n\n{episode_overview}"
                            
                            summary_embed.add_field(
                                name="Next Episode",
                                value=episode_description,
                                inline=False
                            )
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error processing next episode date: {e}")
                
                summary_embed.add_field(
                    name="Total Episodes",
                    value=f"{len(all_episodes)} episodes across {len(monthly_episodes)} months",
                    inline=False
                )
                embeds.append(summary_embed)

                # Create embeds for each month
                for month, episodes in monthly_episodes.items():
                    # Sort episodes by date
                    episodes.sort(key=lambda x: x.get('aired', ''))
                    
                    # Split episodes into chunks of 25 (Discord's field limit)
                    episode_chunks = [episodes[i:i + 25] for i in range(0, len(episodes), 25)]
                    
                    for chunk_index, episode_chunk in enumerate(episode_chunks):
                        embed = discord.Embed(
                            title=f"{month}" + (f" (Part {chunk_index + 1})" if len(episode_chunks) > 1 else ""),
                            color=discord.Color.blue()
                        )
                        
                        current_date = None
                        current_episodes = []
                        
                        for episode in episode_chunk:
                            air_date_str = episode.get('aired')
                            if not air_date_str:
                                continue
                                
                            try:
                                if 'T' in air_date_str:
                                    air_date = datetime.fromisoformat(air_date_str.replace('Z', '+00:00'))
                                else:
                                    air_date = datetime.strptime(air_date_str, "%Y-%m-%d")
                                    air_date = air_date.replace(tzinfo=timezone.utc)
                                    
                                formatted_date = air_date.strftime("%A, %B %d")
                                
                                if current_date != formatted_date:
                                    if current_episodes:
                                        # Add previous day's episodes as a single field
                                        embed.add_field(
                                            name=current_date,
                                            value="\n".join(current_episodes),
                                            inline=False
                                        )
                                        current_episodes = []
                                    
                                    current_date = formatted_date
                                
                                season = episode.get('seasonNumber', '?')
                                episode_num = episode.get('number', '?')
                                episode_name = episode.get('name', '')
                                
                                episode_text = f"• {episode['show_name']} S{season}E{episode_num}"
                                if episode_name and episode_name.lower() != 'tba':
                                    episode_text += f" - {episode_name}"
                                
                                current_episodes.append(episode_text)
                                
                            except (ValueError, TypeError) as e:
                                logger.error(f"Error processing episode date: {e}")
                                continue
                        
                        # Add the last day's episodes
                        if current_episodes:
                            embed.add_field(
                                name=current_date,
                                value="\n".join(current_episodes),
                                inline=False
                            )
                        
                        if not embed.fields:
                            embed.add_field(
                                name="No Episodes",
                                value="No upcoming episodes this month",
                                inline=False
                            )
                        
                        embeds.append(embed)

                # Send all embeds
                await interaction.followup.send(embeds=embeds)

            except Exception as e:
                logger.error(f"Error in calendar command: {str(e)}")
                logger.error(traceback.format_exc())
                await interaction.followup.send("An error occurred while fetching the calendar. Please try again later.")

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