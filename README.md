# discord-team-manager-bot
perfect for organising discord events and hackathons, enter an excel file, generate invite links, send them via mail and let the bot assign roles automatically


This is a bot designed to help manage team assignments and role distribution in Discord. It can also be used in any online hackathon or competition that utilises Discord.  

### How It Works  
1. The bot loads an Excel file using `/load file.xlsx`, extracting first names, emails, and team names.  
2. It creates a text and voice channel for each team, grouping four teams per category.  
3. The bot generates single-use invite links with `/create_invites`.  
4. Using `/send_invites`, it emails each participant their unique invite.  
5. When a participant joins, the bot automatically assigns their team role, granting them access to their team's channels.  
6. Certain manager roles are granted access to all team channels.  

### Commands  
- `/load <file_path>` – Load user data from an Excel file.  
- `/create_invites` – Generate team-specific invite links.  
- `/send_invites` – Email invites to all loaded users.  
- `/team_info` – Display loaded team data.  
- `/invite_info` – Show active invite links and their usage.  
- `/help_arc` – Display this help message.  

### Implementation Steps  
1. Add the following files: `.env`, `main.py`, `template.xlsx`.  
2. The `.env` file should contain all necessary credentials. Obtain a bot token from [Discord Developer Portal](https://discord.com/developers/applications) or use an existing bot token.  
3. Populate the Excel file (`template.xlsx`) with the required team information.  
4. Run `main.py` to start the bot.  

## Acknowledgments
- A special thanks to [@issoupewd](https://github.com/issoupewd) for the original idea and the feedback.
