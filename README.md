
# discord-team-manager-bot

This bot is designed to help manage team assignments and role distribution in Discord. It was initially developed and used for the Algerian Robot Cup event organized by [@celec](https://github.com/celec-club), making the process of creating about 160 rooms, 80 roles, and assigning over 200 roles to users easier and automated.

It can be used for any online hackathon or competition that utilizes Discord as the main communication platform.

Perfect for organising Discord events and hackathons just upload an Excel file, generate invite links, send them via email, and let the bot automatically assign roles.

![Banner](banner.png)
<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python Version">
  </a>
  <a href="https://discordpy.readthedocs.io/">
    <img src="https://img.shields.io/badge/discord.py-2.3%2B-green" alt="Discord.py Version">
  </a>
  <a href="https://pandas.pydata.org/">
    <img src="https://img.shields.io/badge/pandas-2.2.3-orange" alt="pandas Version">
  </a>
  <a href="https://github.com/theskumar/python-dotenv">
    <img src="https://img.shields.io/badge/python--dotenv-1.1.0-yellow" alt="python-dotenv Version">
  </a>
</p>

---

### How It Works  

1. The bot loads an Excel file using `/load file.xlsx`, extracting first names, emails, and team names.  
2. It creates text and voice channels for each team, grouping four teams per category.  
3. The bot generates single-use invite links with `/create_invites`.  
4. Using `/send_invites`, it emails each participant their unique invite.  
5. When a participant joins, the bot automatically assigns their team role, granting them access to their team's channels.  
6. Certain manager roles are granted access to all team channels.

---

### Commands  

- `/load <file_path>` – Load user data from an Excel file.  
- `/create_invites` – Generate team-specific invite links.  
- `/send_invites` – Email invites to all loaded users.  
- `/team_info` – Display loaded team data.  
- `/invite_info` – Show active invite links and their usage.  
- `/help_arc` – Display this help message.

---

### Implementation Steps  

1. Add the following files: `.env`, `main.py`, `template.xlsx`.  
2. The `.env` file should contain all necessary credentials. Obtain a bot token from the [Discord Developer Portal](https://discord.com/developers/applications) or use an existing bot token.  
   - To use email, you need to activate 2FA (two-factor authentication) to generate an app password (a code the bot will use). After enabling 2FA, a section called "App Passwords" will appear. Click on it, add a name, and generate a random 16-character password for the bot to use.
3. Populate the Excel file (`template.xlsx`) with the required team information.  
4. Install the required libraries using the following command:

   ```bash
   pip install -r requirements.txt
   ```

5. Run `main.py` to start the bot.

---

### Customize Your Bot

1. Modify the `.env` file to include your credentials.  
2. Change the server ID in `test_guild` to match your Discord server:

   ```python
   test_guild = discord.Object(id=YOUR_SERVER_ID)  # Insert your Discord server ID for faster command sync
   ```

3. Assign roles that have access to all rooms created for teams by changing the role name in this line. These roles will also be the only ones who can access the bot commands:

   ```python
   @commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president")  # Add other role names as needed
   ```

4. The provided Excel file shows the order of the data. This can be modified as needed:

   ```python
   df = pd.read_excel(file_path)
   required_columns = ['firstname', 'lastname', 'email', 'team']
   ```

5. You can customize the email message here:

   ```python
   msg = MIMEMultipart()
   msg['From'] = os.getenv('EMAIL_ADDRESS')
   msg['To'] = user['email']
   msg['Subject'] = "Insert the subject of your message"
   body = f"""<html>
   <body>
   <p><strong>{user['team']},</strong><br>
   Dear participants,<br>
   <p>The rest of your message could be here, you can modify it as you like using normal HTML.</p>

   <p>🔗 <strong>Discord link:</strong><br>
   {invite_url}</p>
   <p>Again, just write normal HTML.</p>
   <p><strong>Signature</strong></p>
   </body>
   </html>
   """
   msg.attach(MIMEText(body, 'html'))
   ```

---

### Future Improvements  
- Allow the bot to process more than one Excel file.  
- Enable the bot to access the Excel file directly from a Discord message, instead of uploading it to the server.  
- Implement logging for invites and team roles, so when the bot shuts down, it won't lose the data.

---

### Issues  
- ~~Anyone could see the used information~~: **Solved** now only certain roles can access the bot's commands.  
- ~~Having a large number of users creates long text replies for commands that display information, and they don't get sent~~: **Solved** added message splitting to handle large responses.  
- The bot isn't removing permissions to create and invite for team roles when a challenge is created.  
- The bot currently cannot handle more than one file.  
- There's no login system in place.
- the SMTP server limits sending to approximately 100 messages per day.

---

### Acknowledgments  

- Special thanks to [@issoupewd](https://github.com/issoupewd) for the original idea and the valuable feedback.

