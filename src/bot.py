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
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

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
                user_shows = self.db.get_user_subscriptions(str(interaction.user.id))
                if any(s['id'] == show.id for s in user_shows):
                    await interaction.followup.send(f"You are already following {show.name}!")
                    return
                
                # Add the subscription
                self.db.add_subscription(str(interaction.user.id), show.id, show.name)
                
                # Add this debug logging
                logger.info(f"Creating embed for show: {show.name}")
                logger.info(f"Show image URL: {getattr(show, 'image_url', 'No image URL')}")
                
                # Create embed
                embed = discord.Embed(
                    title="✅ Show Followed",
                    description=f"You are now following: **{show.name}**",
                    color=discord.Color.green()
                )
                
                # Try different ways to set the image
                if hasattr(show, 'image_url') and show.image_url:
                    logger.info(f"Attempting to set thumbnail with URL: {show.image_url}")
                    try:
                        embed.set_thumbnail(url=show.image_url)
                    except Exception as e:
                        logger.error(f"Error setting thumbnail: {str(e)}")
                        # Try setting as main image instead
                        try:
                            embed.set_image(url=show.image_url)
                            logger.info("Successfully set main image instead of thumbnail")
                        except Exception as e:
                            logger.error(f"Error setting main image: {str(e)}")
                
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
                
                # Use the TVShow object properties correctly
                logger.info(f"Found show to unfollow: {show.name} (ID: {show.id})")
                
                # Check if user is following the show
                if not self.db.is_user_subscribed(str(interaction.user.id), show.id):
                    await interaction.followup.send(f"You are not following {show.name}!")
                    return
                
                # Remove the subscription
                if self.db.remove_subscription(str(interaction.user.id), show.id):
                    # Create a nice embed for the response
                    embed = discord.Embed(
                        title="❌ Show Unfollowed",
                        description=f"You are no longer following: **{show.name}**",
                        color=discord.Color.red()
                    )
                    
                    # Add show poster if available
                    if hasattr(show, 'image_url') and show.image_url:
                        try:
                            embed.set_thumbnail(url=show.image_url)
                        except Exception as e:
                            logger.error(f"Error setting thumbnail: {str(e)}")
                    
                    # Add basic show info
                    if show.overview:
                        # Truncate overview if it's too long
                        overview = show.overview[:1024] + '...' if len(show.overview) > 1024 else show.overview
                        embed.add_field(name="Overview", value=overview, inline=False)
                    
                    # Add status if available
                    if show.status:
                        status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                        embed.add_field(name="Status", value=status, inline=True)
                    
                    # Set footer
                    embed.set_footer(text="Data provided by TVDB")
                    
                    await interaction.followup.send(embed=embed)
                    logger.info(f"Successfully removed subscription for {interaction.user.name} from {show.name}")
                else:
                    await interaction.followup.send(f"Failed to unfollow {show.name}. Please try again.")
                
            except Exception as e:
                logger.error(f"Error in unfollow command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="calendar", description="Show upcoming episodes for your followed shows")
        async def calendar(interaction: discord.Interaction):
            try:
                await interaction.response.defer()
                
                logger.info(f"User {interaction.user.name} requested their calendar")
                
                # Get user's subscriptions
                shows = self.db.get_user_subscriptions(str(interaction.user.id))
                if not shows:
                    await interaction.followup.send("You're not following any shows!")
                    return
                
                logger.info(f"Found {len(shows)} shows to check for episodes")
                
                # Get upcoming episodes for each show
                all_episodes = []
                total_shows = len(shows)
                shows_checked = 0

                for show in shows:
                    shows_checked += 1
                    logger.info(f"Checking episodes for show {show['name']} (ID: {show['id']}) ({shows_checked}/{total_shows})")
                    episodes = await self.tvdb_client.get_upcoming_episodes(show['id'])
                    if episodes:
                        # Add show name to each episode
                        for ep in episodes:
                            ep['show_name'] = show['name']
                        all_episodes.extend(episodes)
                        logger.info(f"Found {len(episodes)} upcoming episodes for {show['name']}")
                    else:
                        logger.info(f"No upcoming episodes found for {show['name']}")

                if not all_episodes:
                    await interaction.followup.send("No upcoming episodes found for your shows in the next 3 months!")
                    return

                # Sort all episodes by air date
                all_episodes.sort(key=lambda x: x['air_date'])
                logger.info(f"Total upcoming episodes found: {len(all_episodes)}")
                
                # Group episodes by month and week
                episodes_by_month = defaultdict(lambda: defaultdict(list))
                today = datetime.now()
                next_3_months = [
                    (today + timedelta(days=30*i)).strftime("%Y-%m")
                    for i in range(3)
                ]
                
                logger.info(f"Looking for episodes in months: {next_3_months}")
                
                for episode in all_episodes:
                    try:
                        # Parse the ISO format date with timezone
                        air_date = datetime.fromisoformat(episode.get('air_date', '').replace('Z', '+00:00'))
                        month_key = air_date.strftime("%Y-%m")
                        week_num = air_date.isocalendar()[1]
                        
                        logger.debug(f"Processing episode: {episode['show_name']} - {episode['air_date']} (Month: {month_key})")
                        
                        if month_key in next_3_months:
                            episodes_by_month[month_key][week_num].append(episode)
                            logger.debug(f"Added episode to {month_key} week {week_num}")
                        else:
                            logger.debug(f"Episode date {month_key} not in next 3 months")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing episode date: {e}")
                        logger.debug(f"Problematic episode data: {episode}")
                        continue
                
                # Create calendar embeds
                embeds = []
                for month_key in next_3_months:
                    month_date = datetime.strptime(month_key, "%Y-%m")
                    
                    embed = discord.Embed(
                        title=f"📅 Upcoming Episodes - {month_date.strftime('%B %Y')}",
                        color=discord.Color.blue()
                    )
                    
                    # Add episodes by week
                    for week_num in sorted(episodes_by_month[month_key].keys()):
                        week_episodes = episodes_by_month[month_key][week_num]
                        if not week_episodes:
                            continue
                        
                        field_value = ""
                        for ep in week_episodes:
                            air_date = datetime.fromisoformat(ep.get('air_date', '').replace('Z', '+00:00'))
                            show_name = ep.get('show_name', 'Unknown Show')
                            season = ep.get('season_number', 0)
                            episode = ep.get('episode_number', 0)
                            name = ep.get('name', '')
                            
                            field_value += f"**{air_date.strftime('%d %b')}** - {show_name}\n"
                            field_value += f"S{season:02d}E{episode:02d}"
                            if name:
                                field_value += f" - {name}"
                            field_value += "\n\n"
                        
                        embed.add_field(
                            name=f"Week {week_num}",
                            value=field_value[:1024] or "No episodes",
                            inline=False
                        )
                    
                    if not embed.fields:
                        embed.add_field(
                            name="No Episodes",
                            value="No upcoming episodes this month",
                            inline=False
                        )
                    
                    embeds.append(embed)
                
                # Add summary embed
                summary_embed = discord.Embed(
                    title="📺 Calendar Summary",
                    description=f"Found {len(all_episodes)} upcoming episodes for your shows",
                    color=discord.Color.green()
                )
                
                # Add next episode for quick reference
                if all_episodes:
                    next_ep = all_episodes[0]
                    air_date = datetime.fromisoformat(next_ep.get('air_date', '').replace('Z', '+00:00'))
                    show_name = next_ep.get('show_name', 'Unknown Show')
                    season = next_ep.get('season_number', 0)
                    episode = next_ep.get('episode_number', 0)
                    name = next_ep.get('name', '')
                    
                    next_ep_text = (
                        f"**{show_name}**\n"
                        f"S{season:02d}E{episode:02d}"
                    )
                    if name:
                        next_ep_text += f" - {name}"
                    next_ep_text += f"\nAirs on {air_date.strftime('%d %B %Y')}"
                    
                    summary_embed.add_field(
                        name="Next Episode",
                        value=next_ep_text,
                        inline=False
                    )
                
                embeds.insert(0, summary_embed)
                
                # Send all embeds
                await interaction.followup.send(embeds=embeds)
                
            except Exception as e:
                logger.error(f"Error in calendar command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while getting your calendar. Please try again later.")

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
            logger.info(f"Received notification for episode: {episode_data}")
            
            # Get the TVDB show ID from the payload
            tvdb_id = episode_data.get('tvdb_id')
            if not tvdb_id:
                logger.error("No TVDB ID in notification payload")
                return

            # Get show details from TVDB
            show = await self.tvdb_client.search_show(episode_data.get('title', ''))
            if not show:
                logger.warning(f"Could not find show details from TVDB for ID: {tvdb_id}")

            # Get subscribers for this show
            subscribers = self.db.get_show_subscribers(int(tvdb_id))
            
            if not subscribers:
                logger.info(f"No subscribers for show ID: {tvdb_id}")
                return

            # Create notification embed
            embed = discord.Embed(
                title=f"🆕 New Episode Available",
                description=f"A new episode of **{episode_data.get('title', 'Unknown Show')}** is available!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            # Add episode information
            episode_title = f"S{episode_data.get('season_num', '00')}E{episode_data.get('episode_num', '00')}"
            if episode_data.get('episode_name'):
                episode_title += f" - {episode_data['episode_name']}"
            
            embed.add_field(
                name="📺 Episode",
                value=episode_title,
                inline=False
            )

            # Add summary if available
            if episode_data.get('summary'):
                embed.add_field(
                    name="📝 Summary",
                    value=episode_data['summary'][:1024],  # Discord has a 1024 character limit
                    inline=False
                )

            # Add air date if available
            if episode_data.get('air_date'):
                embed.add_field(
                    name="📅 Air Date",
                    value=episode_data['air_date'],
                    inline=True
                )

            # Add show status if available from TVDB
            if show and show.status:
                status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                embed.add_field(
                    name="📊 Show Status",
                    value=status,
                    inline=True
                )

            # Try to add show image in this order:
            # 1. Show poster from TVDB if available
            # 2. Episode poster from notification if available
            # 3. Fall back to no image
            if show and hasattr(show, 'image_url') and show.image_url:
                logger.info(f"Using show poster from TVDB: {show.image_url}")
                embed.set_thumbnail(url=show.image_url)
            elif episode_data.get('poster_url'):
                logger.info(f"Using episode poster from notification: {episode_data['poster_url']}")
                embed.set_thumbnail(url=episode_data['poster_url'])

            # Add footer with TVDB attribution
            embed.set_footer(text="Data provided by TVDB • Followarr Notification")

            # Send notification to each subscriber
            for user_id in subscribers:
                try:
                    user = await self.fetch_user(int(user_id))
                    if user:
                        await user.send(embed=embed)
                        logger.info(f"Sent notification to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send notification to user {user_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling episode notification: {str(e)}")
            logger.error(traceback.format_exc())

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