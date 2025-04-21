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
from src.tvdb_client import TVShow
from src.guid_parser import GUIDParser

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
        self.plex_library_section = os.getenv('PLEX_LIBRARY_SECTION', 'TV Shows')
        
        # Initialize database with proper URL
        db_url = os.getenv('DATABASE_URL', 'sqlite:////app/data/followarr.db')
        if not db_url.startswith('sqlite+aiosqlite:///'):
            db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        self.db = Database(db_url)
        
        # Initialize other components
        self.tvdb_client = TVDBClient(self.tvdb_api_key)
        self.plex_client = PlexClient(self.plex_url, self.plex_token, self.plex_library_section)
        
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
                
                # Try different variations of the show title
                title_variations = [
                    show_name,  # Original title
                    show_name.split(' (')[0].strip(),  # Remove year
                    show_name.split(':')[0].strip(),  # Remove subtitle
                    show_name.replace('&', 'and'),  # Replace & with and
                    show_name.replace('and', '&'),  # Replace and with &
                    show_name.replace(':', ''),  # Remove colons
                    show_name.replace('-', ' '),  # Replace hyphens with spaces
                    show_name.replace('  ', ' ').strip(),  # Remove double spaces
                ]
                
                # Remove duplicates while preserving order
                title_variations = list(dict.fromkeys(title_variations))
                
                # Try each variation until we find a match
                show = None
                for title in title_variations:
                    if title != show_name:
                        logger.info(f"Trying fallback title: {title}")
                    show = await self.tvdb_client.search_show(title)
                    if show:
                        logger.info(f"Found show using title: {title}")
                        break
                
                if not show:
                    logger.warning(f"Could not find show with any title variation: {title_variations}")
                    await interaction.response.send_message(
                        f"❌ Could not find show: {show_name}",
                        ephemeral=True
                    )
                    return

                logger.info(f"Found show: {show.name} (ID: {show.id})")
                
                # Add the show to the user's follows without looking up Plex ID
                await self.db.add_follower(
                    user_id=interaction.user.id,
                    show_title=show.name,
                    show_id=show.id,
                    plex_id=None,
                    tvdb_id=show.id,
                    tmdb_id=None,
                    imdb_id=None,
                    guid=None
                )
                
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
                
                for i, show in enumerate(shows, 1):
                    embed.add_field(
                        name=f"{i}. {show['show_title']}",
                        value="\u200b",  # Zero-width space for empty value
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in list command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="unfollow", description="Unfollow a TV show")
        @app_commands.describe(show_name="The name or number of the show you want to unfollow")
        async def unfollow(interaction: discord.Interaction, show_name: str):
            """Unfollow a TV show."""
            try:
                logger.info(f"User {interaction.user.name} requested to unfollow show: {show_name}")
                await interaction.response.defer()
                
                # Get user's followed shows
                user_follows = await self.db.get_user_subscriptions(str(interaction.user.id))
                if not user_follows:
                    logger.info(f"User {interaction.user.name} has no followed shows")
                    await interaction.followup.send("You're not following any shows!")
                    return
                
                logger.info(f"User {interaction.user.name} follows {len(user_follows)} shows")
                
                # Check if the input is a number
                show_to_unfollow = None
                try:
                    show_number = int(show_name)
                    if 1 <= show_number <= len(user_follows):
                        show_to_unfollow = user_follows[show_number - 1]
                        logger.info(f"User selected show by number: {show_number} - {show_to_unfollow['show_title']}")
                except ValueError:
                    # Not a number, try title matching
                    # Try different variations of the show title
                    title_variations = [
                        show_name,  # Original title
                        show_name.split(' (')[0].strip(),  # Remove year
                        show_name.split(':')[0].strip(),  # Remove subtitle
                        show_name.replace('&', 'and'),  # Replace & with and
                        show_name.replace('and', '&'),  # Replace and with &
                        show_name.replace(':', ''),  # Remove colons
                        show_name.replace('-', ' '),  # Replace hyphens with spaces
                        show_name.replace('  ', ' ').strip(),  # Remove double spaces
                    ]
                    
                    # Remove duplicates while preserving order
                    title_variations = list(dict.fromkeys(title_variations))
                    
                    # Find the show (case-insensitive)
                    for title in title_variations:
                        if title != show_name:
                            logger.info(f"Trying fallback title: {title}")
                        for show in user_follows:
                            if show['show_title'].lower() == title.lower():
                                show_to_unfollow = show
                                logger.info(f"Found show to unfollow using title: {title}")
                                break
                        if show_to_unfollow:
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
                
                # Get show details to ensure we have the English title
                show_details = await self.tvdb_client.get_show_details(show_to_unfollow['show_id'])
                if not show_details:
                    logger.warning(f"Could not get show details for {show_to_unfollow['show_title']}")
                    await interaction.followup.send(f"Successfully unfollowed {show_to_unfollow['show_title']}!")
                    return

                # Use English title if available
                show_title = show_details.get('english_name', show_to_unfollow['show_title'])

                # Create unfollow confirmation embed
                embed = discord.Embed(
                    title="Show Unfollowed",
                    description=f"You are no longer following {show_title}",
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
                            logger.info(f"Setting thumbnail for {show_title} with URL: {show_details['image']}")
                            embed.set_thumbnail(url=show_details['image'])
                            logger.info(f"Successfully set thumbnail for {show_title}")
                        else:
                            logger.warning(f"Invalid image URL for {show_title}: {show_details['image']}")
                    except Exception as e:
                        logger.error(f"Error setting thumbnail for {show_title}: {str(e)}")
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
                # Get user's followed shows
                shows = await self.db.get_user_subscriptions(str(interaction.user.id))
                if not shows:
                    await interaction.response.send_message(
                        "You're not following any shows yet! Use `/follow` to start following shows.",
                        ephemeral=True
                    )
                    return

                # Acknowledge the interaction first
                await interaction.response.defer()
                
                # Get all upcoming episodes
                all_episodes = []
                for show in shows:
                    try:
                        episodes = await self.tvdb_client.get_upcoming_episodes(show['show_id'])
                        if episodes:
                            for episode in episodes:
                                episode['show_title'] = show['show_title']
                                all_episodes.append(episode)
                    except Exception as e:
                        logger.error(f"Error getting episodes for {show['show_title']}: {str(e)}")
                        continue
                
                if not all_episodes:
                    await interaction.followup.send("No upcoming episodes found for your followed shows!")
                    return
                
                # Sort episodes by air date
                all_episodes.sort(key=lambda x: x.get('aired', ''))
                
                # Group episodes by month
                episodes_by_month = defaultdict(list)
                for episode in all_episodes:
                    try:
                        air_date = datetime.fromisoformat(episode.get('aired', '').replace('Z', '+00:00'))
                        month_key = air_date.strftime("%Y-%m")
                        episodes_by_month[month_key].append(episode)
                    except (ValueError, TypeError):
                        continue
                
                # Create embeds for each month
                embeds = []
                for month_key in sorted(episodes_by_month.keys()):
                    month_date = datetime.strptime(month_key, "%Y-%m")
                    month_episodes = episodes_by_month[month_key]
                    
                    # Group episodes by week
                    episodes_by_week = defaultdict(list)
                    for episode in month_episodes:
                        try:
                            air_date = datetime.fromisoformat(episode.get('aired', '').replace('Z', '+00:00'))
                            week_num = air_date.isocalendar()[1]
                            episodes_by_week[week_num].append(episode)
                        except (ValueError, TypeError):
                            continue
                    
                    # Create embeds for this month (might need multiple embeds)
                    current_embed = None
                    current_field_count = 0
                    current_total_length = 0
                    
                    for week_num in sorted(episodes_by_week.keys()):
                        week_episodes = episodes_by_week[week_num]
                        field_value = ""
                        
                        for episode in week_episodes:
                            try:
                                air_date = datetime.fromisoformat(episode.get('aired', '').replace('Z', '+00:00'))
                                show_title = episode.get('show_title', 'Unknown Show')
                                season = episode.get('seasonNumber', '?')
                                episode_num = episode.get('number', '?')
                                episode_title = episode.get('name', f'Episode {episode_num}')
                                
                                episode_text = f"**{air_date.strftime('%d %b')}** - {show_title}\n"
                                episode_text += f"S{season:02d}E{episode_num:02d}"
                                if episode_title:
                                    episode_text += f" - {episode_title}"
                                episode_text += "\n\n"
                                
                                # Check if adding this episode would exceed field limit
                                if len(field_value) + len(episode_text) > 1024:
                                    # Current field is full, add it to the embed
                                    if current_embed is None:
                                        current_embed = discord.Embed(
                                            title=f"📅 {month_date.strftime('%B %Y')} (Part 1)",
                                            color=discord.Color.blue()
                                        )
                                    
                                    current_embed.add_field(
                                        name=f"Week {week_num}",
                                        value=field_value,
                                        inline=False
                                    )
                                    current_field_count += 1
                                    current_total_length += len(field_value)
                                    
                                    # Check if we need a new embed
                                    if current_field_count >= 10 or current_total_length + len(episode_text) > 5000:
                                        if current_embed.fields:
                                            embeds.append(current_embed)
                                        current_embed = discord.Embed(
                                            title=f"📅 {month_date.strftime('%B %Y')} (Part {len(embeds) + 2})",
                                            color=discord.Color.blue()
                                        )
                                        current_field_count = 0
                                        current_total_length = 0
                                    
                                    # Start new field with current episode
                                    field_value = episode_text
                                else:
                                    field_value += episode_text
                                    
                            except (ValueError, TypeError):
                                continue
                        
                        # Add remaining episodes in the last field
                        if field_value:
                            if current_embed is None:
                                current_embed = discord.Embed(
                                    title=f"📅 {month_date.strftime('%B %Y')}",
                                    color=discord.Color.blue()
                                )
                            
                            current_embed.add_field(
                                name=f"Week {week_num}",
                                value=field_value,
                                inline=False
                            )
                            current_field_count += 1
                            current_total_length += len(field_value)
                    
                    # Add the last embed for this month if it has fields
                    if current_embed and current_embed.fields:
                        embeds.append(current_embed)
                
                # Add summary embed
                summary_embed = discord.Embed(
                    title="📺 Calendar Summary",
                    description=f"Found {len(all_episodes)} upcoming episodes across {len(embeds)} embeds",
                    color=discord.Color.green()
                )
                
                # Add next episode for quick reference
                if all_episodes:
                    next_ep = all_episodes[0]
                    try:
                        air_date = datetime.fromisoformat(next_ep.get('aired', '').replace('Z', '+00:00'))
                        show_title = next_ep.get('show_title', 'Unknown Show')
                        season = next_ep.get('seasonNumber', '?')
                        episode_num = next_ep.get('number', '?')
                        episode_title = next_ep.get('name', f'Episode {episode_num}')
                        
                        # Get show details for the image
                        show_id = next_ep.get('seriesId')
                        show_details = None
                        if not show_id:
                            logger.warning(f"No show ID found for next episode: {show_title}")
                        else:
                            logger.info(f"Fetching show details for ID: {show_id}")
                            show_data = await self.tvdb_client.get_show_details(show_id)
                            if not show_data:
                                logger.warning(f"Could not get show details for ID: {show_id}")
                            else:
                                logger.info(f"Successfully fetched show details for {show_title}")
                                show_details = TVShow.from_api_response(show_data)
                        
                        next_ep_text = (
                            f"**{show_title}**\n"
                            f"S{season:02d}E{episode_num:02d}"
                        )
                        if episode_title:
                            next_ep_text += f" - {episode_title}"
                        next_ep_text += f"\nAirs on {air_date.strftime('%d %B %Y')}"
                        
                        summary_embed.add_field(
                            name="Next Episode",
                            value=next_ep_text,
                            inline=False
                        )
                        
                        # Add show image if available
                        if show_details and show_details.image_url:
                            try:
                                logger.info(f"Setting thumbnail for {show_title} with URL: {show_details.image_url}")
                                summary_embed.set_thumbnail(url=show_details.image_url)
                                logger.info(f"Successfully set thumbnail for {show_title}")
                            except Exception as e:
                                logger.error(f"Error setting thumbnail for {show_title}: {str(e)}")
                                logger.error(traceback.format_exc())
                        else:
                            logger.warning(f"No image available for {show_title}")
                        
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing next episode details: {str(e)}")
                        logger.error(traceback.format_exc())
                
                # Insert summary at the beginning
                embeds.insert(0, summary_embed)
                
                # Send all embeds
                await interaction.followup.send(embeds=embeds)
                
            except Exception as e:
                logger.error(f"Error in calendar command: {str(e)}")
                logger.error(traceback.format_exc())
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "An error occurred while processing your request. Please try again later.",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            "An error occurred while processing your request. Please try again later.",
                            ephemeral=True
                        )
                except Exception as e2:
                    logger.error(f"Error sending error message: {str(e2)}")

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
            
            # Get show identifiers
            show_title = metadata.get('grandparentTitle')
            show_rating_key = metadata.get('grandparentRatingKey')
            show_guid = metadata.get('grandparentGuid')
            
            if not show_title:
                logger.error("No show title found in metadata")
                return
                
            logger.info(f"Processing new episode for show: {show_title} (RatingKey: {show_rating_key}, GUID: {show_guid})")
            
            # Try to find followers using different methods in order of reliability
            followers = []
            
            # 1. Try using GUID first (most reliable)
            if show_guid:
                followers = await self.db.get_show_followers_by_guid(show_guid)
                if followers:
                    logger.info(f"Found {len(followers)} followers using GUID: {show_guid}")
            
            # 2. Try using Plex rating key
            if not followers and show_rating_key:
                followers = await self.db.get_show_followers_by_plex_id(show_rating_key)
                if followers:
                    logger.info(f"Found {len(followers)} followers using Plex RatingKey: {show_rating_key}")
            
            # 3. Try title variations as fallback
            if not followers:
                # Try different variations of the show title to find followers
                title_variations = [
                    show_title,  # Original title
                    show_title.split(' (')[0].strip(),  # Remove year
                    show_title.split(':')[0].strip(),  # Remove subtitle
                    show_title.replace('&', 'and'),  # Replace & with and
                    show_title.replace('and', '&'),  # Replace and with &
                    show_title.replace(':', ''),  # Remove colons
                    show_title.replace('-', ' '),  # Replace hyphens with spaces
                    show_title.replace('  ', ' ').strip(),  # Remove double spaces
                ]
                
                # Remove duplicates while preserving order
                title_variations = list(dict.fromkeys(title_variations))
                
                for title in title_variations:
                    if title != show_title:
                        logger.info(f"Trying fallback title: {title}")
                    temp_followers = await self.db.get_show_followers(title)
                    if temp_followers:
                        followers = temp_followers
                        logger.info(f"Found {len(followers)} followers using title: {title}")
                        
                        # Update the show's GUID information for future matches
                        if show_guid:
                            parsed = GUIDParser.parse_guid(show_guid)
                            if parsed:
                                source, id = parsed
                                update_data = {'guid': show_guid}
                                if source == 'tvdb':
                                    update_data['tvdb_id'] = int(id)
                                elif source == 'tmdb':
                                    update_data['tmdb_id'] = int(id)
                                elif source == 'imdb':
                                    update_data['imdb_id'] = id
                                
                                if show_rating_key:
                                    update_data['plex_id'] = show_rating_key
                                
                                await self.db.update_show_guids(title, **update_data)
                        break
            
            if not followers:
                logger.info(f"No followers found for show with any identifier or title variation")
                return
                
            logger.info(f"Found {len(followers)} followers for {show_title}")
            
            # Get episode details
            season_num = metadata.get('parentIndex')
            episode_num = metadata.get('index')
            episode_title = metadata.get('title', f'Episode {episode_num}')
            
            # Get show details from TVDB
            show_details = None
            if show_guid:
                # Try to get TVDB ID from GUID
                tvdb_id = GUIDParser.get_tvdb_id(show_guid)
                if tvdb_id:
                    show_details = await self.tvdb_client.get_show(tvdb_id)
                    if show_details:
                        logger.info(f"Found show details using TVDB ID from GUID: {tvdb_id}")
            
            # If no show details found via GUID, try title search
            if not show_details:
                for title in title_variations:
                    show_details = await self.tvdb_client.search_show(title)
                    if show_details:
                        logger.info(f"Found show details for {title} on TVDB")
                        break
            
            # Get episode details from TVDB
            episode_details = None
            if show_details:
                try:
                    episodes = await self.tvdb_client.get_episodes(show_details.id)
                    if episodes:
                        # Find the matching episode
                        for ep in episodes:
                            if ep.get('seasonNumber') == season_num and ep.get('number') == episode_num:
                                episode_details = ep
                                logger.info(f"Found episode details for S{season_num}E{episode_num}")
                                break
                except Exception as e:
                    logger.error(f"Error fetching episode details from TVDB: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # Create embed for notification
            embed = discord.Embed(
                title=f"New Episode: {show_title}",
                description=f"Season {season_num} Episode {episode_num}: {episode_title}",
                color=discord.Color.blue()
            )
            
            # Add episode summary if available from TVDB
            if episode_details and episode_details.get('overview'):
                embed.add_field(
                    name="Summary",
                    value=episode_details['overview'][:1024] + '...' if len(episode_details['overview']) > 1024 else episode_details['overview'],
                    inline=False
                )
            
            # Add air date if available from TVDB
            if episode_details and episode_details.get('aired'):
                try:
                    air_date = episode_details['aired']
                    if 'T' in air_date:
                        # ISO format with time
                        air_date = air_date.replace('Z', '+00:00')
                        air_date_obj = datetime.fromisoformat(air_date)
                    else:
                        # Date-only format
                        air_date_obj = datetime.strptime(air_date, "%Y-%m-%d")
                    
                    formatted_air_date = air_date_obj.strftime('%B %d, %Y')
                    embed.add_field(
                        name="Originally Aired",
                        value=formatted_air_date,
                        inline=True
                    )
                except (ValueError, TypeError) as e:
                    logger.error(f"Error formatting air date from TVDB: {str(e)}")
            
            # Add show image if available
            if show_details and show_details.image_url:
                try:
                    embed.set_thumbnail(url=show_details.image_url)
                    logger.info(f"Successfully set thumbnail for {show_title} from TVDB")
                except Exception as e:
                    logger.error(f"Error setting thumbnail for {show_title}: {str(e)}")
                    logger.error(traceback.format_exc())
            
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