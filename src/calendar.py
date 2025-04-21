async def _add_episode_to_calendar(self, show: Dict[str, Any], episode: Dict[str, Any]) -> None:
    """Add an episode to the calendar."""
    try:
        # Get the show details from TVDB to get the English title
        tvdb_show = await self.tvdb_client.get_show_details(show.get('tvdb_id'))
        show_title = tvdb_show.get('english_name', show.get('title')) if tvdb_show else show.get('title')
        
        # Create the calendar event
        event = {
            'summary': f"{show_title} S{episode.get('season')}E{episode.get('episode')}",
            'description': f"Season {episode.get('season')} Episode {episode.get('episode')}: {episode.get('title')}",
            'start': {
                'dateTime': episode.get('air_date'),
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': episode.get('air_date'),
                'timeZone': 'UTC'
            }
        }
        
        # Add the event to the calendar
        await self.calendar_service.events().insert(
            calendarId=self.calendar_id,
            body=event
        ).execute()
    except Exception as e:
        print(f"Error adding episode to calendar: {e}") 