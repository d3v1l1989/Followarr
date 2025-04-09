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
from src.tautulli_client import TautulliClient
from src.webhook_server import WebhookServer
import traceback
from discord.app_commands import CommandTree
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

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
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            tree_cls=CustomCommandTree
        )
        
        logger.info("Initializing bot components...")
        
        # Initialize API clients and database
        self.tvdb_client = TVDBClient(os.getenv('TVDB_API_KEY'))
        self.tautulli_client = TautulliClient(
            os.getenv('TAUTULLI_URL'),
            os.getenv('TAUTULLI_API_KEY')
        )
        self.db = Database()
        self.webhook_server = WebhookServer(self.handle_episode_notification)

        # Setup slash commands
        self.setup_commands()

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
                if self.db.is_user_subscribed(str(interaction.user.id), show.id):
                    await interaction.followup.send(f"You are already following {show.name}!")
                    return
                
                # Add subscription
                self.db.add_subscription(str(interaction.user.id), show.id, show.name)
                
                # Create follow confirmation embed
                embed = discord.Embed(
                    title="✅ Show Followed",
                    description=f"You are now following: **{show.name}**",
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
                
                shows = self.db.get_user_subscriptions(str(interaction.user.id))
                
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
            """Unfollow a TV show."""
            try:
                await interaction.response.defer()
                
                show = await self.tvdb_client.search_show(show_name)
                
                if not show:
                    await interaction.followup.send(f"Could not find show: {show_name}")
                    return
                
                if not self.db.is_user_subscribed(str(interaction.user.id), show.id):
                    await interaction.followup.send(f"You are not following {show.name}!")
                    return
                
                if self.db.remove_subscription(str(interaction.user.id), show.id):
                    embed = discord.Embed(
                        title="❌ Show Unfollowed",
                        description=f"You are no longer following: **{show.name}**",
                        color=discord.Color.red()
                    )
                    
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
                else:
                    await interaction.followup.send(f"Failed to unfollow {show.name}. Please try again.")
                
            except Exception as e:
                logger.error(f"Error in unfollow command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while processing your request. Please try again later.")

        @self.tree.command(name="calendar", description="Show upcoming episodes for your followed shows")
        async def calendar(interaction: discord.Interaction):
            """Show upcoming episodes for followed shows."""
            try:
                await interaction.response.defer()
                
                # Get user's followed shows
                shows = self.db.get_user_subscriptions(str(interaction.user.id))
                if not shows:
                    await interaction.followup.send("You're not following any shows yet! Use `/follow` to add some.")
                    return

                # Get upcoming episodes for each show
                all_episodes = []
                for show in shows:
                    episodes = await self.tvdb_client.get_upcoming_episodes(show['id'])
                    for episode in episodes:
                        episode['show_name'] = show['name']
                        all_episodes.append(episode)

                if not all_episodes:
                    await interaction.followup.send("No upcoming episodes found for your shows in the next 3 months!")
                    return

                # Sort episodes by air date
                all_episodes.sort(key=lambda x: x['aired'])

                # Group episodes by month
                episodes_by_month = defaultdict(list)
                for episode in all_episodes:
                    air_date = datetime.fromisoformat(episode['aired'].replace('Z', '+00:00'))
                    month_key = air_date.strftime("%Y-%m")
                    episodes_by_month[month_key].append(episode)

                # Create embeds for each month
                embeds = []
                for month_key in sorted(episodes_by_month.keys()):
                    month_date = datetime.strptime(month_key, "%Y-%m")
                    month_episodes = episodes_by_month[month_key]
                    
                    # Create month embed
                    embed = discord.Embed(
                        title=f"📅 {month_date.strftime('%B %Y')}",
                        description="Here are the upcoming episodes for this month:",
                        color=discord.Color.blue()
                    )

                    # Add episodes to month embed
                    for episode in month_episodes:
                        air_date = datetime.fromisoformat(episode['aired'].replace('Z', '+00:00'))
                        formatted_date = air_date.strftime("%A, %B %d")
                        
                        # Add emojis based on show type/genre
                        show_emoji = "🎬"  # Default emoji
                        if "comedy" in episode.get('show_name', '').lower():
                            show_emoji = "😂"
                        elif "drama" in episode.get('show_name', '').lower():
                            show_emoji = "🎭"
                        elif "action" in episode.get('show_name', '').lower():
                            show_emoji = "💥"
                        elif "sci-fi" in episode.get('show_name', '').lower() or "science fiction" in episode.get('show_name', '').lower():
                            show_emoji = "🚀"
                        elif "horror" in episode.get('show_name', '').lower():
                            show_emoji = "👻"
                        
                        embed.add_field(
                            name=f"{show_emoji} {episode['show_name']} S{episode['seasonNumber']}E{episode['number']}",
                            value=f"📺 **{episode.get('name', 'TBA')}**\n📅 {formatted_date}",
                            inline=False
                        )

                    embeds.append(embed)

                # Add summary embed
                summary_embed = discord.Embed(
                    title="📊 Calendar Summary",
                    description=f"Found {len(all_episodes)} upcoming episodes across {len(episodes_by_month)} months",
                    color=discord.Color.green()
                )

                # Add next episode info
                if all_episodes:
                    next_ep = all_episodes[0]
                    air_date = datetime.fromisoformat(next_ep['aired'].replace('Z', '+00:00'))
                    formatted_date = air_date.strftime("%A, %B %d, %Y")
                    
                    summary_embed.add_field(
                        name="⏰ Next Episode",
                        value=f"📺 **{next_ep['show_name']}**\nS{next_ep['seasonNumber']}E{next_ep['number']} - {next_ep.get('name', 'TBA')}\n📅 {formatted_date}",
                        inline=False
                    )

                # Send all embeds
                await interaction.followup.send(embed=summary_embed)
                for embed in embeds:
                    await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"Error in calendar command: {str(e)}")
                logger.error(traceback.format_exc())
                await interaction.followup.send("An error occurred while fetching the calendar. Please try again later.")

    async def setup_hook(self):
        logger.info("Setting up bot...")
        
        # Initialize DB (moved to on_ready)
        # try:
        #     self.db.init_db()
        #     logger.info("Database initialized successfully.")
        # except Exception as e:
        #     logger.error(f"Error during setup: {e}", exc_info=True)
        #     raise  # Re-raise the exception to potentially stop the bot if DB fails

        # Sync commands
        try:
            synced_global = await self.tree.sync()
            logger.info(f"Synced {len(synced_global)} global commands")
            # Optionally sync guild-specific commands if needed
            # test_guild = discord.Object(id=YOUR_TEST_GUILD_ID)  # Replace with your guild ID
            # synced_guild = await self.tree.sync(guild=test_guild)
            # logger.info(f"Synced {len(synced_guild)} commands to guild {test_guild.id}")
        except discord.errors.Forbidden as e:
            logger.error(
                "Bot lacks 'applications.commands' scope. "
                "Please re-invite with the correct scope."
            )
            # Decide if you want to exit or continue without commands
            # await self.close()
            # return
        except Exception as e:
            logger.error(f"Command syncing failed: {e}", exc_info=True)

        # Start webhook server
        logger.info("Starting webhook server...")
        webhook_port = int(os.getenv('WEBHOOK_SERVER_PORT', 3000))
        config = uvicorn.Config(self.webhook_server.app, host="0.0.0.0", port=webhook_port, log_level="info")
        server = uvicorn.Server(config)
        # Run the server in the background
        asyncio.create_task(server.serve())
        logger.info(f"Webhook server started on port {webhook_port}")
        
        logger.info("Bot setup complete.")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        logger.info('Bot is ready and online!')
        
        # Initialize DB here
        try:
            logger.info("Initializing database...")
            self.db.init_db()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing database in on_ready: {e}", exc_info=True)
            # Depending on severity, you might want to close the bot
            # await self.close()
            # return

        # Optional: Set bot presence
        try:
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

    async def handle_episode_notification(self, episode_data: dict):
        try:
            # Extract show information from Tautulli payload
            show_name = episode_data.get('grandparent_title', '')  # Tautulli uses grandparent_title for show name
            season_num = episode_data.get('parent_index', 0)  # Tautulli uses parent_index for season number
            episode_num = episode_data.get('index', 0)  # Tautulli uses index for episode number
            episode_name = episode_data.get('title', '')  # Tautulli uses title for episode name
            summary = episode_data.get('summary', '')
            air_date = episode_data.get('originally_available_at', '')
            poster_url = episode_data.get('thumb', '')  # Tautulli uses thumb for episode thumbnail

            # Search for the show in TVDB
            show = await self.tvdb_client.search_show(show_name)
            if not show:
                logger.warning(f"Could not find show details from TVDB for show: {show_name}")
                return

            # Get subscribers for this show
            subscribers = self.db.get_show_subscribers(show.id)
            
            if not subscribers:
                logger.info(f"No subscribers for show: {show_name}")
                return

            # Create notification embed
            embed = discord.Embed(
                title=f"🆕 New Episode Available",
                description=f"A new episode of **{show_name}** is available!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            episode_title = f"S{season_num:02d}E{episode_num:02d}"
            if episode_name:
                episode_title += f" - {episode_name}"
            
            embed.add_field(
                name="📺 Episode",
                value=episode_title,
                inline=False
            )

            if summary:
                embed.add_field(
                    name="📝 Summary",
                    value=summary[:1024],
                    inline=False
                )

            if air_date:
                try:
                    air_date_obj = datetime.fromisoformat(air_date.replace('Z', '+00:00'))
                    embed.add_field(
                        name="📅 Air Date",
                        value=air_date_obj.strftime('%B %d, %Y'),
                        inline=True
                    )
                except (ValueError, TypeError):
                    embed.add_field(
                        name="📅 Air Date",
                        value=air_date,
                        inline=True
                    )

            if show and show.status:
                status = show.status.get('name', 'Unknown') if isinstance(show.status, dict) else str(show.status)
                embed.add_field(
                    name="📊 Show Status",
                    value=status,
                    inline=True
                )

            if show and hasattr(show, 'image_url') and show.image_url:
                embed.set_thumbnail(url=show.image_url)
            elif poster_url:
                embed.set_thumbnail(url=poster_url)

            embed.set_footer(text="Data provided by TVDB • Followarr Notification")

            for user_id in subscribers:
                try:
                    user = await self.fetch_user(int(user_id))
                    if user:
                        await user.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send notification to user {user_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling episode notification: {str(e)}")
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