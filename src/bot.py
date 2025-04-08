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
            await interaction.response.defer(ephemeral=False)
            
            try:
                show = await self.tvdb_client.search_show(show_name)
                if not show:
                    await interaction.followup.send(f"Could not find show: {show_name}")
                    return
                
                user_shows = self.db.get_user_subscriptions(str(interaction.user.id))
                if any(s['id'] == show.id for s in user_shows):
                    await interaction.followup.send(f"You are already following {show.name}!")
                    return
                
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
            try:
                await interaction.response.defer()
                
                shows = self.db.get_user_subscriptions(str(interaction.user.id))
                if not shows:
                    await interaction.followup.send("You're not following any shows!")
                    return
                
                # Get upcoming episodes for each show
                all_episodes = []

                for show in shows:
                    episodes = await self.tvdb_client.get_upcoming_episodes(show['id'])
                    if episodes:
                        for ep in episodes:
                            ep['show_name'] = show['name']
                        all_episodes.extend(episodes)

                if not all_episodes:
                    await interaction.followup.send("No upcoming episodes found for your shows in the next 3 months!")
                    return

                # Sort episodes by air date
                all_episodes.sort(key=lambda x: x['air_date'])
                
                # Group episodes by month
                episodes_by_month = defaultdict(lambda: defaultdict(list))
                today = datetime.now()
                next_3_months = [
                    (today + timedelta(days=30*i)).strftime("%Y-%m")
                    for i in range(3)
                ]
                
                for episode in all_episodes:
                    try:
                        air_date = datetime.fromisoformat(episode.get('air_date', '').replace('Z', '+00:00'))
                        month_key = air_date.strftime("%Y-%m")
                        week_num = air_date.isocalendar()[1]
                        
                        if month_key in next_3_months:
                            episodes_by_month[month_key][week_num].append(episode)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing episode date: {e}")
                        continue
                
                # Create calendar embeds
                embeds = []
                for month_key in next_3_months:
                    month_date = datetime.strptime(month_key, "%Y-%m")
                    
                    total_month_episodes = sum(len(episodes) for episodes in episodes_by_month[month_key].values())
                    if total_month_episodes == 0:
                        continue
                    
                    embed = discord.Embed(
                        title=f"📅 {month_date.strftime('%B %Y')}",
                        description="Upcoming episodes for your followed shows",
                        color=discord.Color.blue()
                    )
                    
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
                            
                            field_value += f"📺 **{show_name}**\n"
                            field_value += f"📅 {air_date.strftime('%A, %B %d')}\n"
                            field_value += f"S{season:02d}E{episode:02d}"
                            if name:
                                field_value += f" - {name}"
                            field_value += "\n\n"
                        
                        first_ep_date = datetime.fromisoformat(week_episodes[0].get('air_date', '').replace('Z', '+00:00'))
                        embed.add_field(
                            name=f"{first_ep_date.strftime('%B %d')}",
                            value=field_value[:1024] or "No episodes",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"Total episodes this month: {total_month_episodes}")
                    
                    embeds.append(embed)
                
                # Add summary embed
                summary_embed = discord.Embed(
                    title="📺 Calendar Summary",
                    description=f"Found {len(all_episodes)} upcoming episodes for your shows",
                    color=discord.Color.green()
                )
                
                if all_episodes:
                    next_ep = all_episodes[0]
                    air_date = datetime.fromisoformat(next_ep.get('air_date', '').replace('Z', '+00:00'))
                    show_name = next_ep.get('show_name', 'Unknown Show')
                    season = next_ep.get('season_number', 0)
                    episode = next_ep.get('episode_number', 0)
                    name = next_ep.get('name', '')
                    
                    next_ep_text = (
                        f"📺 **{show_name}**\n"
                        f"📅 {air_date.strftime('%A, %B %d, %Y')}\n"
                        f"S{season:02d}E{episode:02d}"
                    )
                    if name:
                        next_ep_text += f"\n{name}"
                    
                    summary_embed.add_field(
                        name="⏰ Next Episode",
                        value=next_ep_text,
                        inline=False
                    )
                    
                    stats_text = (
                        f"📊 **Statistics**\n"
                        f"• Total episodes: {len(all_episodes)}\n"
                        f"• Shows with episodes: {len(set(ep['show_name'] for ep in all_episodes))}\n"
                        f"• Next 3 months covered"
                    )
                    summary_embed.add_field(
                        name="📈 Overview",
                        value=stats_text,
                        inline=False
                    )
                
                embeds.insert(0, summary_embed)
                
                await interaction.followup.send(embeds=embeds)
                
            except Exception as e:
                logger.error(f"Error in calendar command: {str(e)}", exc_info=True)
                await interaction.followup.send("An error occurred while getting your calendar. Please try again later.")

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
            tvdb_id = episode_data.get('tvdb_id')
            if not tvdb_id:
                logger.error("No TVDB ID in notification payload")
                return

            show = await self.tvdb_client.search_show(episode_data.get('title', ''))
            if not show:
                logger.warning(f"Could not find show details from TVDB for ID: {tvdb_id}")

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

            episode_title = f"S{episode_data.get('season_num', '00')}E{episode_data.get('episode_num', '00')}"
            if episode_data.get('episode_name'):
                episode_title += f" - {episode_data['episode_name']}"
            
            embed.add_field(
                name="📺 Episode",
                value=episode_title,
                inline=False
            )

            if episode_data.get('summary'):
                embed.add_field(
                    name="📝 Summary",
                    value=episode_data['summary'][:1024],
                    inline=False
                )

            if episode_data.get('air_date'):
                embed.add_field(
                    name="📅 Air Date",
                    value=episode_data['air_date'],
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
            elif episode_data.get('poster_url'):
                embed.set_thumbnail(url=episode_data['poster_url'])

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