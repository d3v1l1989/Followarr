# Get upcoming episodes for each show
for show in shows:
    try:
        next_episodes = tvdb_client.get_upcoming_episodes(show['tvdb_id'])
        if next_episodes:
            logger.info(f"Found {len(next_episodes)} upcoming episodes for {show['name']}")
            all_episodes.extend([(show['name'], ep) for ep in next_episodes])
    except Exception as e:
        logger.error(f"Error getting upcoming episodes for {show['name']}: {str(e)}")
        continue

logger.info(f"Total upcoming episodes found: {len(all_episodes)}")

# Group episodes by month
episodes_by_month = {}
for show_name, next_ep in all_episodes:
    try:
        # Parse the ISO format date with timezone
        air_date = datetime.fromisoformat(next_ep.get('air_date', '').replace('Z', '+00:00'))
        month_key = air_date.strftime("%Y-%m")
        week_num = air_date.isocalendar()[1]
        
        logger.debug(f"Processing episode: {show_name} - {next_ep['air_date']} (Month: {month_key})")
        
        if month_key in target_months:
            if month_key not in episodes_by_month:
                episodes_by_month[month_key] = {}
            if week_num not in episodes_by_month[month_key]:
                episodes_by_month[month_key][week_num] = []
            episodes_by_month[month_key][week_num].append((show_name, next_ep, air_date))
            logger.debug(f"Added episode to {month_key} week {week_num}")
        else:
            logger.debug(f"Episode date {month_key} not in target months")
    except (ValueError, TypeError) as e:
        logger.error(f"Error processing episode date: {e}")
        logger.debug(f"Problematic episode data: {next_ep}")
        continue

if not episodes_by_month:
    await interaction.response.send_message("No upcoming episodes found for the specified months.")
    return

# Create calendar message
calendar_msg = "📅 **Upcoming Episodes Calendar**\n\n"

for month in sorted(episodes_by_month.keys()):
    month_date = datetime.strptime(month, "%Y-%m")
    calendar_msg += f"**{month_date.strftime('%B %Y')}**\n"
    
    for week in sorted(episodes_by_month[month].keys()):
        week_date = datetime.fromisocalendar(year=month_date.year, week=week, day=1)
        calendar_msg += f"**{week_date.strftime('%B %d')}**\n"
        
        # Sort episodes by air date
        episodes = sorted(episodes_by_month[month][week], key=lambda x: x[2])
        
        for show_name, ep, air_date in episodes:
            episode_num = f"S{ep.get('season_number', '?'):02d}E{ep.get('episode_number', '?'):02d}"
            episode_title = ep.get('episode_name', 'TBA')
            calendar_msg += f"• {show_name} - {episode_num} - {episode_title} ({air_date.strftime('%Y-%m-%d')})\n"
        
        calendar_msg += "\n"

    calendar_msg += "\n"

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
            title="�� Calendar Summary",
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