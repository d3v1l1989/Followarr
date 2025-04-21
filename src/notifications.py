from typing import Dict, Any

class Notifications:
    async def _send_notification(self, show: Dict[str, Any], episode: Dict[str, Any], guild_id: int) -> None:
        """Send a notification for a new episode."""
        try:
            # Get the show details from TVDB to get the English title
            tvdb_show = await self.tvdb_client.get_show_details(show.get('tvdb_id'))
            show_title = tvdb_show.get('english_name', show.get('title')) if tvdb_show else show.get('title')
            
            # Create the notification message
            message = f"🎬 New episode of **{show_title}** is available!\n"
            message += f"Season {episode.get('season')} Episode {episode.get('episode')}: {episode.get('title')}"
            
            # Send the notification to the configured channel
            channel_id = self.notification_channels.get(guild_id)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(message)
        except Exception as e:
            print(f"Error sending notification: {e}") 