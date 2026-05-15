#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reaction Roles Bot — discord.py v2

This bot does a few things:
  - Lets people self-assign roles by reacting to a pinned message
  - Supports multiple role messages (e.g. one for consoles, one for games)
  - Removes roles if someone un-reacts (can be turned off)
  - DMs the server owner whenever someone @mentions the bot (great for suggestions)
  - Posts pre-written messages to specific channels via slash commands

You'll need a .env file sitting in the same folder as this script.
Copy this and fill in your own values:

    DISCORD_TOKEN=your_bot_token_here
    GUILD_ID=your_server_id_here
    ADMIN_LOG_CHANNEL_ID=optional_channel_id_for_error_logs
    REACTION_ROLE_MESSAGE_IDS=message_id_one,message_id_two
    OWNER_USER_ID=your_discord_user_id_here
    RULES_CHANNEL_ID=your_rules_channel_id_here

Before starting the bot, run through this checklist:
  1. Create every role in REACTION_ROLE_MAP inside your Discord server first.
  2. In Server Settings -> Roles, drag the bot's role ABOVE all the roles it manages.
  3. Make sure the bot has the "Manage Roles" permission.
  4. In the Discord Developer Portal, turn on "Server Members Intent" and "Message Content Intent".
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Dict, Optional

import discord
from discord import app_commands
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Load the .env file
# Keeps all the sensitive stuff (tokens, IDs) out of the code itself so you
# don't accidentally push your bot token to GitHub. Not fun when that happens.
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# ---------------------------------------------------------------------------
# Logging setup
# By default this only shows INFO and above. If something's going wrong and
# you want to see everything the bot is doing, set LOG_LEVEL=DEBUG in .env.
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("reaction-roles-bot")


# ---------------------------------------------------------------------------
# Required values — the bot won't even start if these are missing.
# Better to crash early with a clear message than silently do nothing.
# ---------------------------------------------------------------------------

DISCORD_TOKEN = (os.getenv("DISCORD_TOKEN", "") or "").strip()
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in .env")

GUILD_ID_RAW = (os.getenv("GUILD_ID", "") or "").strip()
if not GUILD_ID_RAW.isdigit():
    raise RuntimeError("GUILD_ID missing/invalid in .env")
GUILD_ID = int(GUILD_ID_RAW)


# ---------------------------------------------------------------------------
# Optional values — the bot runs fine without these, but they unlock
# useful extras like error logging to a channel and DMs to the owner.
# ---------------------------------------------------------------------------

ADMIN_LOG_CHANNEL_ID_RAW = (os.getenv("ADMIN_LOG_CHANNEL_ID", "") or "").strip()
ADMIN_LOG_CHANNEL_ID: Optional[int] = (
    int(ADMIN_LOG_CHANNEL_ID_RAW) if ADMIN_LOG_CHANNEL_ID_RAW.isdigit() else None
)

OWNER_USER_ID_RAW = (os.getenv("OWNER_USER_ID", "") or "").strip()
OWNER_USER_ID: Optional[int] = (
    int(OWNER_USER_ID_RAW) if OWNER_USER_ID_RAW.isdigit() else None
)

RULES_CHANNEL_ID_RAW = (os.getenv("RULES_CHANNEL_ID", "") or "").strip()
RULES_CHANNEL_ID: Optional[int] = (
    int(RULES_CHANNEL_ID_RAW) if RULES_CHANNEL_ID_RAW.isdigit() else None
)


# ---------------------------------------------------------------------------
# Message IDs the bot watches for reactions
# List them all in .env separated by commas. Any reaction on any other message
# gets completely ignored — the bot won't touch it.
# ---------------------------------------------------------------------------

REACTION_ROLE_MESSAGE_IDS_RAW = (os.getenv("REACTION_ROLE_MESSAGE_IDS", "") or "").strip()
REACTION_ROLE_MESSAGE_IDS = {
    int(x.strip())
    for x in REACTION_ROLE_MESSAGE_IDS_RAW.split(",")
    if x.strip().isdigit()
}
if not REACTION_ROLE_MESSAGE_IDS:
    raise RuntimeError("REACTION_ROLE_MESSAGE_IDS missing/invalid in .env")


# ---------------------------------------------------------------------------
# The folder where all the .txt files for slash commands live.
# Just drop a new .txt file in here and hook it up to a slash command below.
# ---------------------------------------------------------------------------

MESSAGES_DIR = BASE_DIR / "messages"


# ---------------------------------------------------------------------------
# Emoji -> Role mapping
# Left side is the emoji users react with, right side is the exact role name
# in your server. Standard emojis just get pasted in as-is. Custom server
# emojis use the format: <:emojiname:emojiID>
#
# Quick tip: if you're not sure what string an emoji comes back as, react to
# a message while the bot is running and check the DEBUG line in the terminal.
# That's how these were verified to be correct.
# ---------------------------------------------------------------------------

REACTION_ROLE_MAP: Dict[str, str] = {
    # Console roles
    "❤️": "Switch",
    "💙": "PC",
    "💚": "Xbox",
    "💜": "Playstation",
    "🧡": "Retro",

    # Game roles
    "🔫": "Marvel Rivals",
    "👻": "Phasmophobia",
    "💸": "Lethal Company",
    "💉": "Outlast Trials",
    "😲": "Random Streams",
    "🤖": "R.E.P.O.",
    "💽": "League of Legends",
    "🥦": "Schedule I",

    # Member role
    "⭐" : "Goose"
}

# Flip this to False if you want people to keep their roles even after
# they remove their reaction. Leaving it True means roles come and go
# with reactions, which is usually what you want.
REMOVE_ROLE_ON_UNREACT = True


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def find_role_by_name(guild: discord.Guild, role_name: str) -> Optional[discord.Role]:
    """
    Finds a role in the server by name. Tries an exact match first, then
    does a case-insensitive check as a fallback so a capital letter difference
    doesn't silently break everything.
    """
    for r in guild.roles:
        if r.name == role_name:
            return r
    rn = role_name.lower()
    for r in guild.roles:
        if r.name.lower() == rn:
            return r
    return None


def normalize_emoji(payload_emoji: discord.PartialEmoji) -> str:
    """
    Turns the emoji object from a reaction event into a plain string we can
    look up in REACTION_ROLE_MAP.

    Regular unicode emojis just return as the character itself (e.g. "❤️").
    Custom server emojis return as "<:name:id>" or "<a:name:id>" if animated.
    """
    if payload_emoji.id is None:
        return payload_emoji.name
    prefix = "a" if payload_emoji.animated else ""
    return f"<{prefix}:{payload_emoji.name}:{payload_emoji.id}>"


def load_message(filename: str) -> Optional[str]:
    """
    Reads a .txt file from the messages/ folder and returns its contents.
    Returns None if the file doesn't exist, so slash commands can handle
    that gracefully instead of crashing.
    """
    path = MESSAGES_DIR / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


async def admin_log(client: discord.Client, text: str) -> None:
    """
    Posts an error or warning to the admin log channel. Really handy for
    catching role permission issues without having to stare at the terminal.
    Does nothing if ADMIN_LOG_CHANNEL_ID isn't set in .env.
    """
    if ADMIN_LOG_CHANNEL_ID is None:
        return
    chan = client.get_channel(ADMIN_LOG_CHANNEL_ID)
    if isinstance(chan, discord.TextChannel):
        try:
            await chan.send(text)
        except Exception:
            logger.exception("Failed to send admin log")


# ---------------------------------------------------------------------------
# Bot setup
# We need members intent so we can look up who reacted and assign them roles.
# Message content intent is needed so we can read what people say when they
# @mention the bot. Both also need to be enabled in the Developer Portal.
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class ReactionRolesBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # The command tree is what powers slash commands — it registers them
        # with Discord and routes interactions back to the right functions.
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self) -> None:
        assert self.user is not None

        # Push all slash commands to the server. Syncing to a specific guild
        # makes them show up instantly instead of waiting up to an hour for
        # global commands to propagate.
        guild_obj = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild_obj)
        await self.tree.sync(guild=guild_obj)

        logger.info("Logged in as %s (id=%s)", self.user, self.user.id)
        logger.info("Guild ID: %s", GUILD_ID)
        logger.info("Watching message IDs: %s", ", ".join(map(str, sorted(REACTION_ROLE_MESSAGE_IDS))))
        logger.info("Emoji mappings: %s", ", ".join(f"{k}->{v}" for k, v in REACTION_ROLE_MAP.items()))
        logger.info("Slash commands synced.")


bot = ReactionRolesBot(intents=intents)


# ---------------------------------------------------------------------------
# Slash commands
# Each command reads a .txt file from the messages/ folder and posts it.
# Only people with Manage Messages permission can trigger these so random
# members can't spam the channel with them.
#
# To add a new command: create a new .txt file in messages/ and copy the
# pattern below. The ephemeral=True on responses means only the person who
# ran the command sees the bot's reply — keeps the channel clean.
# ---------------------------------------------------------------------------

@bot.tree.command(name="rules", description="Post the server rules")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_rules(interaction: discord.Interaction) -> None:
    content = load_message("rules.txt")
    if content is None:
        await interaction.response.send_message("❌ Couldn't find rules.txt in the messages folder.", ephemeral=True)
        return

    # If a rules channel is set, post it there. Otherwise just post wherever
    # the command was used.
    if RULES_CHANNEL_ID:
        channel = bot.get_channel(RULES_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            await channel.send(content)
            await interaction.response.send_message("✅ Rules posted!", ephemeral=True)
            return

    await interaction.response.send_message(content)


@slash_rules.error
async def slash_rules_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)


@bot.tree.command(name="welcome", description="Post the welcome message")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_welcome(interaction: discord.Interaction) -> None:
    content = load_message("welcome.txt")
    if content is None:
        await interaction.response.send_message("❌ Couldn't find welcome.txt in the messages folder.", ephemeral=True)
        return
    await interaction.response.send_message(content)


@slash_welcome.error
async def slash_welcome_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)


# ---------------------------------------------------------------------------
# Reaction add handler
# Using the RAW event here instead of on_reaction_add means this still works
# after a bot restart, even if the message isn't in the cache anymore.
# ---------------------------------------------------------------------------

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    # Only care about reactions happening in our server
    if payload.guild_id != GUILD_ID:
        return

    # Handy debug line — shows exactly what message ID and emoji the bot saw.
    # Great for verifying emoji strings are correct. Remove once everything's working.
    print(f"DEBUG: message_id={payload.message_id}, emoji={normalize_emoji(payload.emoji)}, watching={REACTION_ROLE_MESSAGE_IDS}")

    # Ignore anything that isn't one of our designated role messages
    if payload.message_id not in REACTION_ROLE_MESSAGE_IDS:
        return

    # Don't react to other bots reacting
    if payload.member is not None and payload.member.bot:
        return

    emoji_key = normalize_emoji(payload.emoji)
    role_name = REACTION_ROLE_MAP.get(emoji_key)
    if not role_name:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    member = payload.member or guild.get_member(payload.user_id)
    if member is None:
        return

    role_obj = find_role_by_name(guild, role_name)
    if role_obj is None:
        await admin_log(bot, f"⚠️ Role not found in server: '{role_name}' (triggered by emoji {emoji_key})")
        return

    me = guild.me
    if me is None or not me.guild_permissions.manage_roles:
        await admin_log(bot, "🚫 Bot is missing the Manage Roles permission.")
        return

    # Discord blocks bots from assigning roles that are above their own role
    # in the hierarchy. Fix it by dragging the bot's role higher in Server Settings.
    if role_obj >= me.top_role:
        await admin_log(bot, f"🚫 Can't assign '{role_obj.name}' — move the bot's role above it in Server Settings.")
        return

    try:
        if role_obj not in member.roles:
            await member.add_roles(role_obj, reason=f"Reaction role via {emoji_key}")
    except discord.Forbidden:
        await admin_log(bot, f"🚫 Permission denied adding '{role_obj.name}' to user {payload.user_id}")
    except Exception as e:
        logger.exception("Unexpected error adding reaction role: %s", e)
        await admin_log(bot, f"🚨 Unexpected error adding '{role_obj.name}' to {payload.user_id}: {type(e).__name__}")


# ---------------------------------------------------------------------------
# Reaction remove handler
# Same logic as above but in reverse — strips the role when someone
# un-reacts. Only runs if REMOVE_ROLE_ON_UNREACT is True.
# ---------------------------------------------------------------------------

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
    if not REMOVE_ROLE_ON_UNREACT:
        return

    if payload.guild_id != GUILD_ID:
        return

    if payload.message_id not in REACTION_ROLE_MESSAGE_IDS:
        return

    emoji_key = normalize_emoji(payload.emoji)
    role_name = REACTION_ROLE_MAP.get(emoji_key)
    if not role_name:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    # Unlike the add event, reaction remove doesn't include the member object,
    # so we have to look them up from the guild cache manually.
    member = guild.get_member(payload.user_id)
    if member is None:
        return

    role_obj = find_role_by_name(guild, role_name)
    if role_obj is None:
        return

    me = guild.me
    if me is None or not me.guild_permissions.manage_roles:
        return

    if role_obj >= me.top_role:
        return

    try:
        if role_obj in member.roles:
            await member.remove_roles(role_obj, reason=f"Reaction removed via {emoji_key}")
    except discord.Forbidden:
        await admin_log(bot, f"🚫 Permission denied removing '{role_obj.name}' from user {payload.user_id}")
    except Exception as e:
        logger.exception("Unexpected error removing reaction role: %s", e)


# ---------------------------------------------------------------------------
# Mention handler
# Whenever someone @mentions the bot, the owner gets a DM with the full
# message and a jump link. Makes it easy to collect suggestions or catch
# people asking for help without needing a dedicated suggestions channel.
# ---------------------------------------------------------------------------

@bot.event
async def on_message(message: discord.Message) -> None:
    # Ignore other bots so we don't get into weird loops
    if message.author.bot:
        return
    
    print(f"DEBUG: message received from {message.author}, mentions={message.mentions}, bot={bot.user}")

    print(f"DEBUG: OWNER_USER_ID={OWNER_USER_ID}")
    
    # Only do anything if the bot was actually mentioned
    if bot.user not in message.mentions:
        return

    if OWNER_USER_ID is None:
        return

    owner = await bot.fetch_user(OWNER_USER_ID)
    if owner is None:
        return

    server_name = message.guild.name if message.guild else "DM"
    channel_name = f"#{message.channel.name}" if hasattr(message.channel, "name") else "unknown channel"

    dm_text = (
        f"📬 **New mention in {server_name} / {channel_name}**\n"
        f"**From:** {message.author} (`{message.author.id}`)\n"
        f"**Message:** {message.content}\n"
        f"**Jump to message:** {message.jump_url}"
    )

    try:
        await owner.send(dm_text)
    except discord.Forbidden:
        logger.warning("Couldn't DM the owner — check that your privacy settings allow DMs from server members.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
