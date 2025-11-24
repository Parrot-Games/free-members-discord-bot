import discord
import requests
import json
import os
import asyncio
from discord.ext import commands
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
    
    print(f"✅ Config loaded")
    print(f"🔑 Token: {BOT_TOKEN[:20]}...")
    print(f"🆔 Client ID: {CLIENT_ID}")
    print(f"🔒 Secret: {CLIENT_SECRET[:8]}...")
    
except Exception as e:
    print(f"❌ Config error: {e}")
    exit(1)

# Create bot
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=['!', '?'], intents=intents)
bot.remove_command("help")

@bot.event
async def on_ready():
    print(f'🎯 Bot is ready: {bot.user}')
    print(f'📋 Loaded commands: {[command.name for command in bot.commands]}')

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

@bot.command(name='get_token')
async def get_auth_token(ctx):
    """Get authentication link - FIXED VERSION"""
    try:
        redirect_url = "https://parrotgames.free.nf/discord-redirect.html"
        
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
            value=f"[**👉 CLICK HERE TO AUTHENTICATE 👈**]({oauth_url})",
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

@bot.command(name='auth')
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
            'redirect_uri': "https://parrotgames.free.nf/discord-redirect.html"
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
        success_embed.add_field(name="Next Step", value="You will be added to servers when admin uses `!join SERVER_ID`", inline=False)
        
        await msg.edit(content="", embed=success_embed)
        print(f"✅ Authentication completed for user {current_user_id}")
        
    except Exception as error:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"❌ Exception: {error}")

@bot.command(name='join')
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
                value=f"**[Add bot to server first]({invite_url})**\nThen use `!join {target_server_id}` again",
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

@bot.command(name='check_tokens')
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
            value="Expired tokens will be automatically refreshed when using `!join`", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error checking tokens: {str(error)}")

@bot.command(name='list_users')
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
            value=f"Use `!join SERVER_ID` to add all {len(users)} users to a server", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error listing users: {str(error)}")

@bot.command(name='clear_users')
async def clear_authenticated_users(ctx):
    """Clear all authenticated users (reset)"""
    try:
        if os.path.exists('auths.txt'):
            # Count users before clearing
            user_count = 0
            with open('auths.txt', 'r') as auth_file:
                for line in auth_file:
                    if line.strip():
                        user_count += 1
            
            os.remove('auths.txt')
            await ctx.send(f"✅ Cleared **{user_count}** authenticated users. File reset.")
        else:
            await ctx.send("✅ No auth file found. Already clean.")
            
    except Exception as error:
        await ctx.send(f"❌ Error clearing users: {str(error)}")

@bot.command(name='invite')
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
    
    await ctx.send(embed=embed)

@bot.command(name='servers')
async def list_servers(ctx):
    """List all servers the bot is in"""
    try:
        if not bot.guilds:
            await ctx.send("❌ Bot is not in any servers.")
            return
        
        server_list = []
        for guild in bot.guilds:
            server_list.append(f"`{guild.id}` - **{guild.name}** (Members: {guild.member_count})")
        
        embed = discord.Embed(
            title="🏠 BOT SERVERS",
            description=f"**Total: {len(bot.guilds)} servers**",
            color=0x5865F2
        )
        
        servers_text = "\n".join(server_list[:15])
        if len(server_list) > 15:
            servers_text += f"\n... and {len(server_list) - 15} more servers"
        
        embed.add_field(name="Servers", value=servers_text, inline=False)
        embed.add_field(
            name="Usage", 
            value="Use `!join SERVER_ID` to add users to a server", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error listing servers: {str(error)}")

@bot.command(name='help')
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
        value="`!join SERVER_ID` - Add ALL users to server\n`!servers` - List bot servers", 
        inline=False
    )
    
    embed.add_field(
        name="👥 USER MANAGEMENT", 
        value="`!list_users` - List authenticated users\n`!clear_users` - Reset all users", 
        inline=False
    )
    
    embed.add_field(
        name="🔧 UTILITY", 
        value="`!invite` - Get bot invite link\n`!help` - Show this help", 
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
