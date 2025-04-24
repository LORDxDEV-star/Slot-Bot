import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime

# Load configuration from JSON
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["token"]
GUILD_ID = config["guild_id"]
OWNER_ID = config["owner_id"]
LOG_CHANNEL_ID = config["log_channel_id"]
SLOT_CATEGORY_NAME = config["slot_category_name"]
EMBED_COLOR = config["embed_color"]
INVITE_URL = config["invite_url"]
SUPPORT_URL = config["support_url"]

# Create bot instance with slash commands
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents, application_id=YOUR_APP_ID)

# Load users data from JSON
if os.path.exists("users.json"):
    with open("users.json", "r") as f:
        users_data = json.load(f)
else:
    users_data = {}

# Helper function to save users data
def save_users_data():
    with open("users.json", "w") as f:
        json.dump(users_data, f, indent=4)

# Register commands
@bot.event
async def on_ready():
    print(f"Bot is logged in as {bot.user}")
    
    # Syncing slash commands
    try:
        await bot.tree.sync()
        print("Slash commands have been synced successfully.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# /giveslot Command: Grants a slot to a user
@bot.tree.command(name="giveslot", description="Grant a slot to a user")
@app_commands.describe(user="The user to give the slot to", usage_count="How many times they can ping")
async def giveslot(interaction: discord.Interaction, user: discord.Member, usage_count: int):
    if interaction.user.id != int(OWNER_ID):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if user.id not in users_data:
        users_data[user.id] = {"usage_count": 0, "slot_active": False}
    
    users_data[user.id]["usage_count"] = usage_count
    users_data[user.id]["slot_active"] = True

    save_users_data()

    # Create a new channel for the user
    guild = bot.get_guild(int(GUILD_ID))
    category = discord.utils.get(guild.categories, name=SLOT_CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(SLOT_CATEGORY_NAME)

    channel_name = f"{user.name}-slot"
    channel = await guild.create_text_channel(channel_name, category=category)

    # Send an embed message with slot info
    embed = discord.Embed(
        title="Slot Granted",
        description=f"{user.mention}, you have been granted a slot to use @everyone and @here.",
        color=int(EMBED_COLOR, 16)
    )
    embed.add_field(name="Usage Limit", value=f"{usage_count} uses.")
    embed.add_field(name="Slot Active", value="Yes")
    embed.add_field(name="Time Period", value="Not set")

    await channel.send(embed=embed)

    # Log in the log channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    log_embed = discord.Embed(
        title="Slot Granted",
        description=f"{interaction.user.mention} granted a slot to {user.mention}.",
        color=int(EMBED_COLOR, 16)
    )
    log_embed.add_field(name="User", value=user.mention)
    log_embed.add_field(name="Usage Limit", value=str(usage_count))
    await log_channel.send(embed=log_embed)

    # Send confirmation DM to the user
    await user.send(
        f"You have been granted a slot to use @everyone and @here. Your usage limit is {usage_count} times."
    )

    await interaction.response.send_message(f"Slot granted to {user.mention} successfully!", ephemeral=True)

# /removeslot Command: Removes a user's slot
@bot.tree.command(name="removeslot", description="Remove a slot from a user")
async def removeslot(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != int(OWNER_ID):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    if user.id not in users_data or not users_data[user.id]["slot_active"]:
        await interaction.response.send_message("This user doesn't have an active slot.", ephemeral=True)
        return

    # Remove the slot
    users_data[user.id]["slot_active"] = False
    save_users_data()

    # Delete the user's slot channel
    channel_name = f"{user.name}-slot"
    guild = bot.get_guild(int(GUILD_ID))
    channel = discord.utils.get(guild.text_channels, name=channel_name)
    if channel:
        await channel.delete()

    # Log in the log channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    log_embed = discord.Embed(
        title="Slot Removed",
        description=f"{interaction.user.mention} removed a slot from {user.mention}.",
        color=int(EMBED_COLOR, 16)
    )
    log_embed.add_field(name="User", value=user.mention)
    await log_channel.send(embed=log_embed)

    # Send confirmation DM to the user
    await user.send("Your slot has been removed.")

    await interaction.response.send_message(f"Slot removed from {user.mention} successfully!", ephemeral=True)

# /slotstats Command: Shows the current stats of a user's slot usage
@bot.tree.command(name="slotstats", description="Shows the slot usage stats of a user")
async def slotstats(interaction: discord.Interaction, user: discord.Member):
    if user.id not in users_data:
        await interaction.response.send_message(f"{user.mention} has no slot granted.", ephemeral=True)
        return

    stats = users_data[user.id]
    usage_count = stats["usage_count"]
    slot_active = "Yes" if stats["slot_active"] else "No"

    embed = discord.Embed(
        title=f"Slot Stats for {user.name}",
        color=int(EMBED_COLOR, 16)
    )
    embed.add_field(name="Slot Active", value=slot_active)
    embed.add_field(name="Usage Limit", value=str(usage_count))
    embed.add_field(name="Pings Remaining", value=str(usage_count - stats["usage_count"]))
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /use-slot Command: Allows a user to use their slot to ping @everyone or @here
@bot.tree.command(name="use-slot", description="Use your granted slot to ping @everyone or @here")
async def use_slot(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in users_data or not users_data[user_id]["slot_active"]:
        await interaction.response.send_message("You don't have an active slot.", ephemeral=True)
        return

    stats = users_data[user_id]
    usage_count = stats["usage_count"]

    if stats["usage_count"] >= usage_count:
        await interaction.response.send_message("You have reached your usage limit for today.", ephemeral=True)
        return

    stats["usage_count"] += 1
    save_users_data()

    # Send ping in the same channel as the user
    channel = interaction.channel
    await channel.send(f"@everyone @here **USE MM**")

    # Send sticky message (if not already present)
    sticky_message = "USE MM"
    async for message in channel.history(limit=100):
        if message.content == sticky_message:
            return

    await channel.send(sticky_message)

    # Log the usage in the log channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    log_embed = discord.Embed(
        title="Slot Usage",
        description=f"{interaction.user.mention} used their slot to ping @everyone/@here.",
        color=int(EMBED_COLOR, 16)
    )
    await log_channel.send(embed=log_embed)

    await interaction.response.send_message(f"Successfully used your slot!", ephemeral=True)

# Run the bot
bot.run(TOKEN)
