import discord
import pandas as pd
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
if not os.getenv('DISCORD_TOKEN'):
    raise ValueError("Missing DISCORD_TOKEN in .env file")
if not os.getenv('EMAIL_ADDRESS'):
    print("Warning: Email functionality will be disabled")

# Initialize bot with necessary intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Data storage
bot.team_data = {}  # {team_name: [user_dicts]}
bot.invite_links = {}  # {invite_url: team_name}
bot.invite_tracker = {}  # Tracks invite usage counts

# ----------------------------
# BOT SETUP AND CHANNEL MANAGEMENT
# ----------------------------
@bot.event
async def on_ready():
    """Initialize bot and setup channels"""
    print(f'Logged in as {bot.user}')
    
    # Sync commands to specific guild for faster updates
    test_guild = discord.Object(id=1354521624734784681)  # Insert your Discord server ID for faster command sync
    bot.tree.copy_global_to(guild=test_guild)
    await bot.tree.sync(guild=test_guild)
    
    # Initialize invite tracker with only bot-created invites
    bot.invite_tracker = {}
    for guild in bot.guilds:
        try:
            if not guild.me.guild_permissions.manage_guild:
                print(f"❌ Missing MANAGE_GUILD permission in {guild.name} - invite tracking disabled")
                continue
                
            guild_invites = await guild.invites()
            # Track all valid invites regardless of creation time
            # In on_ready() invite tracking:
            for invite in guild_invites:
                if invite.inviter == bot.user:
                    # Handle invites without reasons safely
                    team_name = "Unknown"
                    try:
                        if invite.reason and ":" in invite.reason:
                            team_name = invite.reason.split(":")[1].strip()
                    except AttributeError:
                        pass  # Handle legacy invites without reason field
            
                    # Fix guild context reference
                    bot.invite_links[invite.url] = {
                        'team': team_name,
                        'guild_id': guild.id  # Changed from ctx.guild.id
                    }
            
            # In create_invites command:
                    invite = await ctx.channel.create_invite(
                        max_uses=5,
                        unique=True,
                        reason=f"Team:{team_name}",
                        max_age=0  # infinite
                    )
            
            # In assign_team_role function:
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color.random(),
                        hoist=True,
                        mentionable=True,
                        reason=f"auto-created for {team_name}",
                        position=guild.me.top_role.position - 1  # Position below bot's role
                    )
            
            # Store guild ID with invite data
            bot.invite_links[invite.url] = {
                'team': team_name,
                'guild_id': ctx.guild.id
            }
            # NOT: bot.invite_links[invite.url] = team_name
            bot.invite_tracker[invite.url] = invite.uses
            print(f"🔗 Tracking invite {invite.url} (uses: {invite.uses}) in {guild.name}")
        
        except discord.Forbidden as e:
            print(f"Permission error in {guild.name}: {str(e)}")
        except Exception as e:
            print(f"Error processing invites in {guild.name}: {str(e)}")
    
    # Setup bot channels in all guilds
    for guild in bot.guilds:
        await setup_bot_channel(guild)

async def setup_bot_channel(guild):
    """Create or verify the bot's dedicated channel with proper permissions"""
    channel = discord.utils.get(guild.text_channels, name="teammanagerbot")
    if not channel:
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=False),
                guild.me: discord.PermissionOverwrite(
                    send_messages=True,
                    manage_channels=True,
                    manage_permissions=True
                )
            }
            channel = await guild.create_text_channel(
                "teammanagerbot",
                overwrites=overwrites,
                reason="Bot command channel with proper permissions"
            )
            await channel.send("Bot command center ready!")
        except discord.Forbidden:
            print(f"Missing permissions to create channels in {guild.name}")
        except Exception as e:
            print(f"Error creating channel in {guild.name}: {e}")

# ----------------------------
# DATA LOADING SYSTEM
# ----------------------------
@bot.hybrid_command(name="load", description="Load user data from Excel")
@commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president") # Add other role names to your liking
async def load_users(ctx, file_path: str):
    try:
        df = pd.read_excel(file_path)
        required_columns = ['firstname', 'lastname', 'email', 'team']
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            return await ctx.send(f"❌ Missing required columns: {', '.join(missing)}")
        
        bot.team_data = {}
        for team, group in df.groupby('team'):
            bot.team_data[team] = group.to_dict('records')
            
        # Create channels for all teams immediately
        created_channels = []
        for team_name in bot.team_data.keys():
            success = await create_team_channels(ctx.guild, team_name)
            if success:
                created_channels.append(team_name)
        
        await ctx.send(
            f"✅ Successfully loaded {len(df)} users "
            f"across {len(bot.team_data)} teams!\n"
            f"Created channels for: {', '.join(created_channels) if created_channels else 'No new teams found'}"
        )
    except FileNotFoundError:
        await ctx.send("❌ File not found. Please check the path and try again.")
    except Exception as e:
        await ctx.send(f"❌ Error loading file: {str(e)}")

# ----------------------------
# INVITE MANAGEMENT SYSTEM
# ----------------------------
@bot.hybrid_command(name="create_invites", description="Create team-specific invites")
@commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president")
async def create_invites(ctx):
    # Immediately acknowledge the interaction
    await ctx.defer()
    
    if not bot.team_data:
        print("❌ No team data loaded! Use `/load` first.")
        return await ctx.send("❌ No team data loaded! Use `/load` first.")
    
    bot.invite_links = {}
    results = []
    
    try:
        for team_name, members in bot.team_data.items():
            # Create one invite per team member.
            for member in members:
                try:
                    invite = await ctx.channel.create_invite(
                        max_uses=1, # You can choose how many times an invite link can be used by modifying max_uses.
                        unique=True,
                        reason=f"Team:{team_name} Member:{member['email']}",
                        max_age=0 # here you can choose for how long the invite link is valid, Discord allows ]0, a week (in secs)] U (infinity which takes the value of "0")
                    )
                    
                    bot.invite_links[invite.url] = {
                        'team': team_name,
                        'member_email': member['email'],
                        'guild_id': ctx.guild.id
                    }
                    bot.invite_tracker[invite.url] = invite.uses
                    results.append(f"• {team_name} ({member['email']}): {invite.url}")
                    print(f"✅ Created invite for {team_name} member {member['email']}: {invite.url}")
                    
                except discord.HTTPException as e:
                    results.append(f"• {team_name}: ❌ Failed ({str(e)})")
                    print(f"❌ Failed to create invites for team {team_name}: {str(e)}")
                    continue
        
        message = "**Generated Member Invites:**\n" + "\n".join(results)
        if len(message) > 2000:
            chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(message)
            
    except Exception as e:
        await ctx.send(f"❌ Error creating invites: {str(e)}")
        print(f"❌ Global error in create_invites: {str(e)}")

# ----------------------------
# IMPROVED EMAIL SYSTEM
# ----------------------------
async def send_team_invite(user: dict, invite_url: str):
    try:
        if not all(k in user for k in ['email', 'firstname', 'team']):
            print(f"❌ Missing user data for {user.get('email', 'unknown')}")
            raise ValueError("Missing user data")
            
        # Validate email format properly.
        if '@' not in user['email'] or '.' not in user['email'].split('@')[-1]:
            print(f"❌ Invalid email format: {user['email']}")
            raise ValueError(f"Invalid email: {user['email']}")
            
        msg = MIMEMultipart()
        msg['From'] = os.getenv('EMAIL_ADDRESS')
        msg['To'] = user['email']
        msg['Subject'] = "insert the subject of your message"
        body = f"""<html>
<body>
<p><strong>{user['team']},</strong><br>
Dear participants,<br>
<p> the rest of your message could be here, you could modify it as you like, just write normal html</p>

<p>🔗 <strong>Discord link :</strong><br>
{invite_url}</p>
<p>again, just write normal html</p>
<p><strong>signature</strong></p>
</body>
</html>
"""
        
        msg.attach(MIMEText(body, 'html'))
        
        # Handle different SMTP connection types
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD'))
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD'))
                server.send_message(msg)
                
        print(f"✅ Email successfully sent to {user['email']}")
        return True
        
    except smtplib.SMTPException as e:
        print(f"❌ SMTP Error for {user['email']}: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ general error for {user['email']}: {str(e)}")
        return False

@bot.hybrid_command(name="send_invites", description="Email invites to all users")
@commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president")
async def send_invites(ctx):
    if not bot.invite_links:
        print("❌ No invites created! Use `/create_invites` first.")
        return await ctx.send("❌ No invites created! Use `/create_invites` first.")
    if not bot.team_data:
        print("❌ No team data loaded! Use `/load` first.")
        return await ctx.send("❌ No team data loaded! Use `/load` first.")
    
    # Verify email configuration.
    if not os.getenv('EMAIL_ADDRESS') or not os.getenv('EMAIL_PASSWORD'):
        print("❌ Email credentials not configured in .env file")
        return await ctx.send("❌ email functionality is disabled - check server logs")

    total_emails = sum(len(users) for users in bot.team_data.values())
    if total_emails == 0:
        print("❌ No users found in team data.")
        return await ctx.send("❌ No users found.")
    
    print(f"📧 starting to send {total_emails} emails...")
    progress_msg = await ctx.send("🔄 starting email sends... (0%)")
    success = failures = 0
    failed_emails = []
    
    for team_name, users in bot.team_data.items():
        for user in users:
            # Find the specific invite for this user.
            invite_url = next(
                (url for url, data in bot.invite_links.items() 
                 if data['team'] == team_name 
                 and data['member_email'] == user['email']
                 and data['guild_id'] == ctx.guild.id),
                None
            )
            if not invite_url:
                print(f"⚠️ No invite found for {user['email']} in team {team_name}")
                continue
                
            processed = success + failures + 1
            progress = int((processed / total_emails) * 100)
            
            if await send_team_invite(user, invite_url):
                success += 1
                print(f"✅ Email sent to {user['email']} ({team_name})")
            else:
                failures += 1
                failed_emails.append(user['email'])
                print(f"❌ failed to send email to {user['email']} ({team_name})")
                
            if progress % 10 == 0 or processed == total_emails:
                await progress_msg.edit(content=f"🔄 Sending... ({progress}%)")
                print(f"📊 Email progress: {progress}%")
    
    report = [
        f"📬 Email sending complete!",
        f"✅ Success: {success}",
        f"❌ Failed: {failures}"
    ]
    
    if failures > 0:
        report.append("\nFailed recipients (first 5):")
        report.extend(failed_emails[:5])
        if len(failed_emails) > 5:
            report.append(f"(+{len(failed_emails)-5} more)")
    
    await progress_msg.delete()
    full_report = "\n".join(report)
    print(f"📝 final email report:\n{full_report}")
    
    if len(full_report) > 2000:
        chunks = [full_report[i:i+2000] for i in range(0, len(full_report), 2000)]
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(full_report)

# ----------------------------
# ROLE ASSIGNMENT SYSTEM
# ----------------------------
@bot.event
async def on_member_join(member):
    try:
        await asyncio.sleep(5)
        guild = member.guild
        
        if not guild.me.guild_permissions.manage_guild:
            print(f"❌ Missing MANAGE_GUILD permission in {guild.name}")
            return

        # Get current invites.
        current_invites = await guild.invites()
        used_invite = None
        
        # Check which invite is missing (was used)
        for invite_url, uses in bot.invite_tracker.items():
            # Find if this tracked invite still exists
            invite_still_exists = any(invite.url == invite_url for invite in current_invites)
            
            # If invite no longer exists and was created by bot, it was used
            if not invite_still_exists and invite_url in bot.invite_links:
                print(f"🔍 Detected used invite: {invite_url} (no longer exists)")
                used_invite_url = invite_url
                # Remove from tracker since it's been used.
                bot.invite_tracker.pop(invite_url, None)
                
                # Get team from our stored data
                invite_data = bot.invite_links.get(invite_url)
                if invite_data and invite_data['guild_id'] == guild.id:
                    team_name = invite_data['team']
                    print(f"🎉 {member.name} joined using invite for {team_name}")
                    
                    # Assign role with retry logic
                    success = await assign_team_role(member, team_name)
                    if success:
                        # Create channels if they don't exist
                        await create_team_channels(guild, team_name)
                        
                        # Send welcome message
                        welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
                        if welcome_channel:
                            role = discord.utils.get(guild.roles, name=team_name.title())
                            if role:
                                await welcome_channel.send(
                                    f"Welcome {member.mention} to team {team_name}! "
                                    f"You've been assigned the {role.mention} role and "
                                    f"can now access your team channels."
                                )
                    else:
                        print(f"❌ Failed to assign role for {member.name} in {guild.name}")
                    return
        
        # If we get here, we need to check for increased usage counts.
        for invite in current_invites:
            if invite.inviter == bot.user and invite.url in bot.invite_links:
                invite_data = bot.invite_links[invite.url]
                if invite_data['guild_id'] != guild.id:
                    continue
                    
                tracked_uses = bot.invite_tracker.get(invite.url, 0)
                print(f"🔍 Checking invite {invite.url}: tracked={tracked_uses} vs current={invite.uses}")
                
                if invite.uses > tracked_uses:
                    used_invite = invite
                    bot.invite_tracker[invite.url] = invite.uses
                    print(f"🔑 Valid invite used: {invite.url}")
                    break

        if used_invite:
            invite_data = bot.invite_links[used_invite.url]
            team_name = invite_data['team']
            print(f"🎉 {member.name} joined using invite for {team_name}")
            
            # Assign role with retry logic
            success = await assign_team_role(member, team_name)
            if success:
                # Create channels if they don't exist
                await create_team_channels(guild, team_name)
                
                # Send welcome message
                welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
                if welcome_channel:
                    role = discord.utils.get(guild.roles, name=team_name.title())
                    if role:
                        await welcome_channel.send(
                            f"Welcome {member.mention} to team {team_name}! "
                            f"You've been assigned the {role.mention} role and "
                            f"can now access your team channels."
                        )
            else:
                print(f"❌ Failed to assign role for {member.name} in {guild.name}")

    except Exception as e:
        print(f"❌ Error in on_member_join: {str(e)}")

async def create_team_channels(guild, team_name):
    """Create team-specific channels with proper permissions"""
    try:
        # Generate consistent base name for both channels
        base_name = "".join(c for c in team_name if c.isalnum() or c in " -_").strip().lower()
        text_channel_name = f"{base_name}-chat"
        voice_channel_name = f"{base_name}-voice"
        
        # Check ALL channels in the server (not just current category)
        existing_text = discord.utils.find(
            lambda c: c.name.lower() == text_channel_name.lower(),
            guild.text_channels
        )
        existing_voice = discord.utils.find(
            lambda c: c.name.lower() == voice_channel_name.lower(), 
            guild.voice_channels
        )

        # If channels exist anywhere, skip creation
        if existing_text or existing_voice:
            print(f"⚠️ Channels already exist for team {team_name}")
            return True

        # Create team role first (if it doesn't exist)
        role_name = team_name.title()
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(
                name=role_name,
                color=discord.Color.random(),
                hoist=True,
                mentionable=True,
                reason=f"Auto-created for {team_name}"
            )
            print(f"✅ Created role: {role_name} in {guild.name}")
            
            # Position role below bot's role
            try:
                if guild.me.top_role.position > 1:
                    await role.edit(position=guild.me.top_role.position - 1)
            except:
                print("⚠️ Couldn't reposition role - ensure bot role is high enough")

        # Configure permissions
        ADMIN_ROLES = ["Admin", "Moderator", "Organiser", "Formateur", "Supervisor", "Responsable", "President"]
        overwrites = {
            guild.default_role: discord.PermissionOverwrite( # Default-role permissions
                read_messages=False,
                view_channel=False,
                connect=False
            ),
            role: discord.PermissionOverwrite( # The assigned team roles permissions
                read_messages=True,
                view_channel=True,
                send_messages=True,
                connect=True,
                speak=True
            )
        }

        # Add admin permissions
        for admin_role_name in ADMIN_ROLES:
            admin_role = discord.utils.get(guild.roles, name=admin_role_name)
            if admin_role:
                # Admins as well as other roles present in ADMIN_ROLES can access the team channels
                overwrites[admin_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    connect=True,
                    speak=True,
                    manage_channels=True
                )

        # Find or create category, we re grouping each four teams in a bigger team Discord category
        teams_category = next((
            cat for cat in guild.categories 
            if cat.name.startswith("TEAM ") 
            and len(cat.channels) < 8  # (4 text + 4 voice)
        ), None)
        
        if not teams_category:
            # Count existing team channels to determine new category number
            team_channels = [
                c for c in guild.channels 
                if any(c.name.lower().endswith(suffix) for suffix in ["-chat", "-voice"])
            ]
            category_number = (len(team_channels) // 8) + 1  # 4 teams per category, two channels for each.
            category_name = f"TEAM {category_number}"
            teams_category = await guild.create_category(category_name)
            print(f"✅ Created category {category_name} in {guild.name}")

        # Create text channel if it doesn't exist
        if not existing_text:
            await guild.create_text_channel(
                text_channel_name,
                overwrites=overwrites,
                category=teams_category,
                reason=f"Team {team_name} text channel"
            )
            print(f"✅ Created text channel: {text_channel_name}")

        # Create voice channel if it doesn't exist
        if not existing_voice:
            await guild.create_voice_channel(
                voice_channel_name,
                overwrites=overwrites,
                category=teams_category,
                reason=f"Team {team_name} voice channel"
            )
            print(f"✅ Created voice channel: {voice_channel_name}")

        return True

    except discord.Forbidden as e:
        print(f"❌ Permission error in {guild.name}: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error in {guild.name}: {str(e)}")
        return False

async def assign_team_role(member, team_name):
    try:
        guild = member.guild
        role_name = "".join(c for c in team_name if c.isalnum() or c in " -_").strip().title()
        
        if not guild.me.guild_permissions.manage_roles:
            print(f"❌ Missing MANAGE_ROLES in {guild.name}")
            return False

        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(
                name=role_name,
                color=discord.Color.random(),
                hoist=True,
                mentionable=True,
                reason=f"auto-created for {team_name}"
            )
            print(f"✅ Created role: {role_name} in {guild.name}")
            
            # Move the role position AFTER creation
            try:
                await role.edit(position=guild.me.top_role.position - 1)
                print(f"🔀 Moved {role_name} to position {role.position}")
            except Exception as e:
                print(f"⚠️ Couldn't position role: {str(e)}")

        if role not in member.roles:
            print(f"⚙️ {guild.name} Hierarchy Check | Bot: {guild.me.top_role.position} vs {role_name}: {role.position}")
            if guild.me.top_role.position > role.position:
                await member.add_roles(role)
                return True
            else:
                print(f"❌ Fix required: Drag @{guild.me.top_role.name} above @{role.name} in {guild.name}")
                return False
        return True

    except discord.Forbidden:
        print(f"❌ Missing permissions in {guild.name}")
        return False
    except Exception as e:
        print(f"❌ Error in {guild.name}: {str(e)}")
        return False

# ----------------------------
# UTILITY COMMANDS
# ----------------------------
@bot.hybrid_command(name="team_info", description="Show loaded team data")
@commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president")
async def team_info(ctx):
    if not bot.team_data:
        return await ctx.send("No team data loaded! Use `/load` first.")
    
    embed = discord.Embed(
        title="📊 Team Information",
        color=discord.Color.blue(),
        description=f"Total {sum(len(u) for u in bot.team_data.values())} users"
    )
    
    for team, users in bot.team_data.items():
        members = "\n".join(
            f"{u['firstname']} {u['lastname']} ({u['email']})"
            for u in users[:3]
        )
        if len(users) > 3:
            members += f"\n...and {len(users)-3} more"
        embed.add_field(name=f"Team {team}", value=members, inline=False)
    
    # Check if embed is too large (Discord limit is around 6000 characters for embeds)
    if len(embed) > 6000:
        # Fall back to text-based output with chunking
        message = "**📊 Team Information**\n"
        message += f"Total {sum(len(u) for u in bot.team_data.values())} users\n\n"
        
        for team, users in bot.team_data.items():
            message += f"**Team {team}**\n"
            for i, user in enumerate(users[:3]):
                message += f"{user['firstname']} {user['lastname']} ({user['email']})\n"
            if len(users) > 3:
                message += f"...and {len(users)-3} more\n"
            message += "\n"
        
        # Split message if too long
        if len(message) > 2000:
            chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(message)
    else:
        await ctx.send(embed=embed)

@bot.hybrid_command(name="invite_info", description="Show active invite links")
@commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president")
async def invite_info(ctx):
    if not bot.invite_links:
        return await ctx.send("No invites created! Use `/create_invites` first.")
    
    embed = discord.Embed(title="🔗 Active Invite Links", color=discord.Color.green())
    
    for url, team in bot.invite_links.items():
        uses = bot.invite_tracker.get(url, 0)
        embed.add_field(
            name=f"Team {team}",
            value=f"Uses: {uses}\n{url}",
            inline=False
        )
    
    # Check if embed is too large
    if len(embed) > 6000:
        # Fall back to text-based output with chunking
        message = "**🔗 Active Invite Links**\n\n"
        
        for url, data in bot.invite_links.items():
            uses = bot.invite_tracker.get(url, 0)
            team_name = data['team'] if isinstance(data, dict) else data
            message += f"**Team {team_name}**\n"
            message += f"Uses: {uses}\n{url}\n\n"
        
        # Split message if too long
        if len(message) > 2000:
            chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(message)
    else:
        await ctx.send(embed=embed)


# ----------------------------
# HELP COMMAND
# ----------------------------
@bot.hybrid_command(name="help_arc", description="List all available ARC Bot commands")
@commands.has_any_role("Admin", "Moderator", "Leaders", "admin", "leader", "president")
async def help_command(ctx):
    """Display all available commands and their descriptions"""
    embed = discord.Embed(
        title="🤖 ARC Bot Commands Help",
        color=discord.Color.blue(),
        description="Here are all the available commands:"
    )
    
    commands_list = [
        ("/load <file_path>", "Load user data from Excel file"),
        ("/create_invites", "Generate team-specific invite links"),
        ("/send_invites", "Email invites to all loaded users"),
        ("/team_info", "Show loaded team data"),
        ("/invite_info", "Show active invite links and usage"),
        ("/help_arc", "Show this help message")
    ]
    
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    embed.set_footer(text="Note: Most commands require admin/moderator roles")
    await ctx.send(embed=embed)

# ----------------------------
# BOT EXECUTION
# ----------------------------
try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except discord.LoginFailure:
    print("Invalid Discord token. Check your .env file")
except Exception as e:
    print(f"Unexpected error: {str(e)}")
