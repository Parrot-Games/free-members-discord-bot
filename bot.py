import discord
import requests
import json
import os
import asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import time
from urllib.parse import urlencode

print("🚀 STARTING BOT...")

# Load config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    BOT_TOKEN = config['token']
    CLIENT_ID = config['id']
    CLIENT_SECRET = config['secret']
    MAIN_SERVER = 1437381878310109185  # Your main server ID
    
    print(f"<a:BlueVerifed:1464994925581176862> Config loaded")
    print(f"<:MekoApplication:1463528148422496343> Token: {BOT_TOKEN[:20]}...")
    print(f"<:id:1463528151744254085> Client ID: {CLIENT_ID}")
    print(f"<a:shop:1463528173097582720> Secret: {CLIENT_SECRET[:8]}...")
    print(f"🏠 Main Server: {MAIN_SERVER}")
    
except Exception as e:
    print(f"❌ Config error: {e}")
    exit(1)

# Create bot
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=['!', '?'], intents=intents)
bot.remove_command("help")

# Store server join times
server_join_times = {}

@bot.event
async def on_ready():
    print(f'🎯 Bot is ready: {bot.user}')
    print(f'📋 Loaded commands: {[command.name for command in bot.commands]}')
    
    # Initialize server join times
    for guild in bot.guilds:
        if guild.id != MAIN_SERVER:
            server_join_times[guild.id] = datetime.now()
            print(f"📝 Tracking server: {guild.name} ({guild.id})")
    
    # Start the cleanup task
    check_server_ages.start()

@tasks.loop(hours=24)  # Run once per day
async def check_server_ages():
    """Check servers and leave if they're older than 14 days (except main server)"""
    print("🔍 Checking server ages...")
    
    for guild in bot.guilds:
        if guild.id == MAIN_SERVER:
            continue  # Never leave main server
        
        guild_id = guild.id
        guild_name = guild.name
        guild_age = None
        
        # Calculate age
        if guild_id in server_join_times:
            join_time = server_join_times[guild_id]
            guild_age = datetime.now() - join_time
        else:
            # If we don't have a join time, assume we joined now
            server_join_times[guild_id] = datetime.now()
            guild_age = timedelta(0)
        
        if guild_age >= timedelta(days=14):
            try:
                print(f"🚪 Leaving server {guild_name} ({guild_id}) - Age: {guild_age.days} days")
                await guild.leave()
                
                # Send notification to main server
                main_guild = bot.get_guild(MAIN_SERVER)
                if main_guild:
                    # Find first text channel bot can send to
                    for channel in main_guild.text_channels:
                        if channel.permissions_for(main_guild.me).send_messages:
                            embed = discord.Embed(
                                title="🚪 Bot Left Server",
                                description=f"**Server:** {guild_name}\n**ID:** {guild_id}\n**Reason:** Server age ({guild_age.days} days) exceeded 14 days",
                                color=0xED4245,
                                timestamp=datetime.now()
                            )
                            await channel.send(embed=embed)
                            break
                
                # Remove from tracking
                if guild_id in server_join_times:
                    del server_join_times[guild_id]
                    
            except Exception as e:
                print(f"❌ Error leaving server {guild_name}: {e}")
        else:
            print(f"✅ Server {guild_name} is {guild_age.days} days old - OK")

@bot.event
async def on_guild_join(guild):
    """Track when bot joins a new server"""
    if guild.id != MAIN_SERVER:
        server_join_times[guild.id] = datetime.now()
        print(f"📝 Bot joined new server: {guild.name} ({guild.id})")
        
        # Send notification to main server
        main_guild = bot.get_guild(MAIN_SERVER)
        if main_guild:
            for channel in main_guild.text_channels:
                if channel.permissions_for(main_guild.me).send_messages:
                    embed = discord.Embed(
                        title="🏠 Bot Joined Server",
                        description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Members:** {guild.member_count}\n**Will leave after:** 14 days",
                        color=0x57F287,
                        timestamp=datetime.now()
                    )
                    await channel.send(embed=embed)
                    break

@bot.event
async def on_guild_remove(guild):
    """Remove server from tracking when bot leaves"""
    if guild.id in server_join_times:
        del server_join_times[guild.id]
        print(f"🗑️ Removed tracking for server: {guild.name} ({guild.id})")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Command not found. Use `!help` to see available commands.")
    else:
        print(f"❌ Command error: {error}")

def refresh_access_token(refresh_token):
    """Refresh an expired access token"""
    try:
        data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        response = requests.post('https://discord.com/api/v10/oauth2/token', data=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return None

def get_valid_token(user_id, access_token, refresh_token):
    """Get a valid access token, refreshing if needed"""
    # First test if current token works
    headers = {'Authorization': f'Bearer {access_token}'}
    test_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
    
    if test_response.status_code == 200:
        return access_token  # Token is still valid
    
    # Token is invalid, try to refresh
    print(f"🔄 Token expired for user {user_id}, refreshing...")
    new_tokens = refresh_access_token(refresh_token)
    
    if new_tokens:
        # Update the token in auths.txt
        update_token_in_file(user_id, new_tokens['access_token'], new_tokens['refresh_token'])
        return new_tokens['access_token']
    else:
        print(f"❌ Failed to refresh token for user {user_id}")
        return None

def update_token_in_file(user_id, new_access_token, new_refresh_token):
    """Update tokens in auths.txt file"""
    try:
        if not os.path.exists('auths.txt'):
            return False
        
        with open('auths.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split(',')
            if len(parts) >= 3 and parts[0] == user_id:
                # Update this user's tokens
                new_line = f"{user_id},{new_access_token},{new_refresh_token}\n"
                new_lines.append(new_line)
                updated = True
                print(f"✅ Updated tokens for user {user_id}")
            else:
                new_lines.append(line + '\n')
        
        if updated:
            with open('auths.txt', 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True
        
        return False
    except Exception as e:
        print(f"❌ Error updating tokens in file: {e}")
        return False

@bot.hybrid_command(name='get_token')
async def get_auth_token(ctx):
    """Get authentication link - FIXED VERSION"""
    try:
        redirect_url = "https://memberswave.netlify.app"
        
        # CORRECTED SCOPES
        scopes = "identify guilds.join"
        
        auth_params = {
            'client_id': CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': redirect_url,
            'scope': scopes,
            'prompt': 'consent'
        }
        
        # Build URL properly
        oauth_url = f"https://discord.com/oauth2/authorize?{urlencode(auth_params)}"
        
        embed = discord.Embed(
            title="🔐 Authentication Required",
            description="**Click the link below to get your authentication code:**",
            color=0x5865F2
        )
        embed.add_field(
            name="🚨 IMPORTANT",
            value="**Codes expire in 10 minutes!** Complete authentication quickly.",
            inline=False
        )
        embed.add_field(
            name="🔗 Auth Link", 
            value=f"[**👉 CLICK HERE TO AUTHENTICATE <a:shop:1463528173097582720>**]({oauth_url})",
            inline=False
        )
        embed.add_field(
            name="📝 Steps:",
            value="1. Click the link above\n2. Authorize the application\n3. **IMMEDIATELY** copy the code\n4. Use `!auth YOUR_CODE_HERE`",
            inline=False
        )
        
        await ctx.send(embed=embed)
        print(f"✅ Sent auth link to {ctx.author.name}")
        
    except Exception as e:
        await ctx.send(f"❌ Error generating auth link: {str(e)}")
        print(f"❌ Error in get_token: {e}")

@bot.hybrid_command(name='auth')
async def authenticate_user(ctx, authorization_code: str):
    """Authenticate user with code"""
    try:
        authorization_code = authorization_code.strip()
        current_user_id = str(ctx.author.id)
        
        print(f"🔐 PROCESSING CODE: {authorization_code} for user {current_user_id}")
        
        msg = await ctx.send("🔄 Starting authentication...")
        
        # Token exchange
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code', 
            'code': authorization_code,
            'redirect_uri': "https://memberswave.netlify.app"
        }
        
        await msg.edit(content="🔄 Exchanging code for token...")
        token_response = requests.post('https://discord.com/api/v10/oauth2/token', data=token_data)
        
        if token_response.status_code != 200:
            error_info = token_response.json()
            await msg.edit(content=f"❌ Token exchange failed: {error_info.get('error_description', 'Unknown error')}")
            return
        
        token_info = token_response.json()
        access_token = token_info['access_token']
        refresh_token = token_info['refresh_token']
        
        print(f"✅ Token obtained: {access_token[:20]}...")
        
        # Save to file
        username = ctx.author.name
        auth_entry = f"{current_user_id},{access_token},{refresh_token}\n"
        
        print(f"💾 Preparing to save: {auth_entry.strip()}")
        
        # Read existing entries
        existing_entries = []
        if os.path.exists('auths.txt'):
            try:
                with open('auths.txt', 'r', encoding='utf-8') as auth_file:
                    existing_entries = auth_file.readlines()
                print(f"📖 Read {len(existing_entries)} existing entries")
            except Exception as e:
                print(f"⚠️ Error reading auth file: {e}")
                existing_entries = []
        
        # Remove any existing entry for this user and clean up empty lines
        cleaned_entries = []
        for line in existing_entries:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) >= 1 and parts[0] == current_user_id:
                print(f"🔄 Replacing old entry for user {current_user_id}")
                continue
            cleaned_entries.append(line + '\n')
        
        # Add the new entry
        cleaned_entries.append(auth_entry)
        
        # Write back to file
        try:
            with open('auths.txt', 'w', encoding='utf-8') as auth_file:
                auth_file.writelines(cleaned_entries)
            print(f"✅ Successfully wrote {len(cleaned_entries)} entries to auths.txt")
        except Exception as e:
            print(f"❌ Error writing to auth file: {e}")
            await ctx.send(f"❌ Error saving authentication: {e}")
            return
        
        success_embed = discord.Embed(
            title="✅ AUTHENTICATION SUCCESSFUL!",
            description=f"**{username}** is now authenticated!",
            color=0x57F287
        )
        success_embed.add_field(name="User ID", value=f"`{current_user_id}`", inline=True)
        success_embed.add_field(name="Next Step", value="You will be added to servers when admin uses `!djoin SERVER_ID`", inline=False)
        
        await msg.edit(content="", embed=success_embed)
        print(f"✅ Authentication completed for user {current_user_id}")
        
    except Exception as error:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"❌ Exception: {error}")
        
@bot.hybrid_command(name='djoin')
async def join_server(ctx, target_server_id: str):
    """Add ALL authenticated users to a server - WITH TOKEN REFRESH"""
    try:
        # Check if bot is in the target server first
        bot_in_server = False
        server_name = "Unknown"
        
        for guild in bot.guilds:
            if str(guild.id) == target_server_id:
                bot_in_server = True
                server_name = guild.name
                break
        
        if not bot_in_server:
            invite_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands"
            
            embed = discord.Embed(
                title="❌ BOT NOT IN SERVER",
                description=f"Bot is not in server `{target_server_id}`",
                color=0xED4245
            )
            embed.add_field(
                name="🚨 Solution", 
                value=f"**[Add bot to server first]({invite_url})**\nThen use `!djoin {target_server_id}` again",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        if not os.path.exists('auths.txt'):
            await ctx.send("❌ No users are authenticated yet. Use `!get_token` to share with users.")
            return
        
        # Read all authenticated users
        authenticated_users = []
        with open('auths.txt', 'r') as auth_file:
            for line_num, line in enumerate(auth_file, 1):
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(',')
                if len(parts) >= 3:
                    user_id = parts[0]
                    access_token = parts[1]
                    refresh_token = parts[2] if len(parts) > 2 else ""
                    authenticated_users.append({
                        'user_id': user_id,
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'line_number': line_num
                    })
        
        if not authenticated_users:
            await ctx.send("❌ No valid authenticated users found in auths.txt")
            return
        
        total_users = len(authenticated_users)
        status_msg = await ctx.send(f"🚀 **MASS JOIN STARTED**\nAdding **{total_users}** authenticated users to **{server_name}**...\n🔄 Checking token validity...")
        
        success_count = 0
        failed_count = 0
        token_refreshed = 0
        joined_members = []
        
        # Process each user with token validation
        for index, user_data in enumerate(authenticated_users):
            user_id = user_data['user_id']
            access_token = user_data['access_token']
            refresh_token = user_data['refresh_token']
            
            # Update status every 10 users
            if index % 10 == 0:
                await status_msg.edit(content=f"🚀 **MASS JOIN IN PROGRESS**\nProcessing {index+1}/{total_users} users...\n✅ Successful: {success_count} | ❌ Failed: {failed_count} | 🔄 Refreshed: {token_refreshed}")
            
            try:
                # Get valid token (refresh if needed)
                valid_token = get_valid_token(user_id, access_token, refresh_token)
                
                if not valid_token:
                    print(f"❌ No valid token for user {user_id}, skipping...")
                    failed_count += 1
                    continue
                
                # If token was refreshed, count it
                if valid_token != access_token:
                    token_refreshed += 1
                
                api_url = f"https://discord.com/api/v10/guilds/{target_server_id}/members/{user_id}"
                join_data = {"access_token": valid_token}
                headers = {
                    "Authorization": f"Bot {BOT_TOKEN}",
                    "Content-Type": "application/json"
                }
                
                response = requests.put(api_url, headers=headers, json=join_data)
                
                if response.status_code in (201, 204):
                    success_count += 1
                    joined_members.append(f"✅ <@{user_id}> - Added successfully")
                    print(f"✅ Added user {user_id} to server {target_server_id}")
                else:
                    failed_count += 1
                    error_msg = response.json().get('message', 'Unknown error') if response.content else 'No details'
                    print(f"❌ Failed to add user {user_id}: {response.status_code} - {error_msg}")
                
                # Increased delay to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                failed_count += 1
                print(f"❌ Exception adding user {user_id}: {e}")
        
        # Final results
        final_embed = discord.Embed(
            title="🎯 MASS JOIN COMPLETED",
            description=f"**Server:** {server_name}\n**Total Processed:** {total_users} users",
            color=0x57F287 if success_count > 0 else 0xED4245
        )
        
        final_embed.add_field(name="✅ Successful", value=success_count, inline=True)
        final_embed.add_field(name="❌ Failed", value=failed_count, inline=True)
        final_embed.add_field(name="🔄 Tokens Refreshed", value=token_refreshed, inline=True)
        
        if joined_members:
            success_text = "\n".join(joined_members[:10])  # Show first 10
            if len(joined_members) > 10:
                success_text += f"\n... and {len(joined_members) - 10} more"
            final_embed.add_field(name="Successfully Joined", value=success_text, inline=False)
        
        await status_msg.edit(content="", embed=final_embed)
        print(f"✅ Mass join completed: {success_count} successful, {failed_count} failed")
        
    except Exception as error:
        await ctx.send(f"❌ Mass join error: {str(error)}")
        print(f"❌ MASS JOIN EXCEPTION: {error}")

@bot.hybrid_command(name='check_tokens')
async def check_token_validity(ctx):
    """Check which tokens are still valid"""
    try:
        if not os.path.exists('auths.txt'):
            await ctx.send("❌ No users are authenticated yet.")
            return
        
        users = []
        valid_count = 0
        expired_count = 0
        
        with open('auths.txt', 'r') as auth_file:
            for line in auth_file:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(',')
                if len(parts) >= 3:
                    user_id = parts[0]
                    access_token = parts[1]
                    
                    # Test token validity
                    headers = {'Authorization': f'Bearer {access_token}'}
                    test_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
                    
                    if test_response.status_code == 200:
                        status = "✅ VALID"
                        valid_count += 1
                    else:
                        status = "❌ EXPIRED"
                        expired_count += 1
                    
                    users.append(f"{status} <@{user_id}>")
        
        embed = discord.Embed(
            title="🔍 TOKEN VALIDITY CHECK",
            description=f"**Valid:** {valid_count} | **Expired:** {expired_count}",
            color=0x5865F2
        )
        
        if users:
            users_text = "\n".join(users[:15])
            if len(users) > 15:
                users_text += f"\n... and {len(users) - 15} more"
            embed.add_field(name="Token Status", value=users_text, inline=False)
        
        embed.add_field(
            name="💡 Tip", 
            value="Expired tokens will be automatically refreshed when using `!djoin`", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error checking tokens: {str(error)}")

@bot.hybrid_command(name='list_users')
async def list_authenticated_users(ctx):
    """List all authenticated users"""
    try:
        if not os.path.exists('auths.txt'):
            await ctx.send("❌ No users are authenticated yet.")
            return
        
        users = []
        with open('auths.txt', 'r') as auth_file:
            for line_num, line in enumerate(auth_file, 1):
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(',')
                if len(parts) >= 3:
                    user_id = parts[0]
                    token_preview = parts[1][:10] + "..." if len(parts[1]) > 10 else parts[1]
                    users.append(f"`{line_num}.` <@{user_id}> - `{token_preview}`")
        
        if not users:
            await ctx.send("❌ No valid authenticated users found.")
            return
        
        embed = discord.Embed(
            title="📋 AUTHENTICATED USERS",
            description=f"**Total: {len(users)} users**",
            color=0x5865F2
        )
        
        # Split users into chunks to avoid field length limits
        users_text = "\n".join(users[:20])  # Show first 20 users
        if len(users) > 20:
            users_text += f"\n\n... and {len(users) - 20} more users"
        
        embed.add_field(name="Users", value=users_text, inline=False)
        embed.add_field(
            name="Usage", 
            value=f"Use `!djoin SERVER_ID` to add all {len(users)} users to a server", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error listing users: {str(error)}")

@bot.hybrid_command(name='invite')
async def generate_invite(ctx):
    """Generate bot invite link for any server"""
    invite_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands"
    
    embed = discord.Embed(
        title="🤖 BOT INVITE LINK",
        description="**Use this link to add the bot to any server:**",
        color=0x5865F2
    )
    embed.add_field(
        name="🔗 Invite Link", 
        value=f"[**👉 CLICK HERE TO INVITE BOT 👈**]({invite_url})",
        inline=False
    )
    embed.add_field(
        name="⚠️ Note",
        value="Bot will automatically leave servers after 14 days (except main server)",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name='servers')
async def list_servers(ctx):
    """List all servers the bot is in"""
    try:
        if not bot.guilds:
            await ctx.send("❌ Bot is not in any servers.")
            return
        
        server_list = []
        current_time = datetime.now()
        
        for guild in bot.guilds:
            age_days = "Permanent" if guild.id == MAIN_SERVER else "Unknown"
            
            if guild.id in server_join_times:
                join_time = server_join_times[guild.id]
                age = current_time - join_time
                age_days = f"{age.days} days"
            
            server_list.append(f"`{guild.id}` - **{guild.name}** (Members: {guild.member_count}) - Age: {age_days}")
        
        embed = discord.Embed(
            title="🏠 BOT SERVERS",
            description=f"**Total: {len(bot.guilds)} servers**\n⭐ = Main Server (Never leaves)",
            color=0x5865F2
        )
        
        servers_text = "\n".join(server_list[:15])
        if len(server_list) > 15:
            servers_text += f"\n... and {len(server_list) - 15} more servers"
        
        embed.add_field(name="Servers", value=servers_text, inline=False)
        embed.add_field(
            name="ℹ️ Info", 
            value="• Bot leaves servers after 14 days\n• Main server (ID: {}) is permanent\n• Use `!djoin SERVER_ID` to add users".format(MAIN_SERVER), 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error listing servers: {str(error)}")

@bot.hybrid_command(name='server_age')
async def check_server_age(ctx, server_id: str = None):
    """Check how long the bot has been in a server"""
    try:
        if server_id:
            guild = bot.get_guild(int(server_id))
            if not guild:
                await ctx.send(f"❌ Bot is not in server with ID: {server_id}")
                return
        else:
            guild = ctx.guild
            if not guild:
                await ctx.send("❌ This command must be used in a server")
                return
        
        if guild.id == MAIN_SERVER:
            embed = discord.Embed(
                title="⭐ MAIN SERVER",
                description=f"**{guild.name}**\nID: `{guild.id}`",
                color=0xF1C40F
            )
            embed.add_field(name="Status", value="✅ **Permanent - Never leaves**", inline=False)
            embed.add_field(name="Members", value=guild.member_count, inline=True)
            embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
            await ctx.send(embed=embed)
            return
        
        if guild.id in server_join_times:
            join_time = server_join_times[guild.id]
            current_time = datetime.now()
            age = current_time - join_time
            days_left = max(0, 14 - age.days)
            
            embed = discord.Embed(
                title="📅 SERVER AGE",
                description=f"**{guild.name}**\nID: `{guild.id}`",
                color=0x3498DB,
                timestamp=join_time
            )
            embed.add_field(name="Joined On", value=f"<t:{int(join_time.timestamp())}:F>", inline=False)
            embed.add_field(name="Current Age", value=f"{age.days} days, {age.seconds // 3600} hours", inline=True)
            embed.add_field(name="Days Until Leave", value=f"{days_left} days", inline=True)
            embed.add_field(name="Will Leave On", value=f"<t:{int((join_time + timedelta(days=14)).timestamp())}:F>", inline=False)
            embed.add_field(name="Members", value=guild.member_count, inline=True)
            embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
            
            await ctx.send(embed=embed)
        else:
            # If we don't have tracking data, add it now
            server_join_times[guild.id] = datetime.now()
            await ctx.send(f"✅ Started tracking server **{guild.name}**. Will leave after 14 days.")
            
    except Exception as error:
        await ctx.send(f"❌ Error checking server age: {str(error)}")

@bot.hybrid_command(name='help')
async def show_help(ctx):
    """Show all available commands"""
    embed = discord.Embed(
        title="🤖 BOT COMMANDS - COMPLETE LIST",
        color=0x5865F2
    )
    
    embed.add_field(
        name="🔐 AUTHENTICATION", 
        value="`!get_token` - Get authentication link\n`!auth CODE` - Authenticate with code\n`!check_tokens` - Check token validity", 
        inline=False
    )
    
    embed.add_field(
        name="🚀 MASS JOINING", 
        value="`!djoin SERVER_ID` - Add ALL users to server\n`!servers` - List bot servers\n`!server_age [SERVER_ID]` - Check server age", 
        inline=False
    )
    
    embed.add_field(
        name="👥 USER MANAGEMENT", 
        value="`!list_users` - List authenticated users", 
        inline=False
    )
    
    embed.add_field(
        name="🔧 UTILITY", 
        value="`!invite` - Get bot invite link\n`!help` - Show this help", 
        inline=False
    )
    
    embed.add_field(
        name="⚠️ IMPORTANT NOTES",
        value="• Bot leaves servers after 14 days automatically\n• Main server (ID: {}) is permanent\n• All commands work as slash commands".format(MAIN_SERVER),
        inline=False
    )
    
    await ctx.send(embed=embed)

# START BOT
if __name__ == "__main__":
    print("🎯 STARTING COMPLETE DISCORD BOT...")
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
