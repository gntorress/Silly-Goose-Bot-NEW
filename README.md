# Discord Reaction Roles Bot

A small Discord bot I made for my own server with friends.
Mostly built to make role setup and server management easier without needing a bunch of extra bots.

It’s pretty customized for my server right now, but everything is easy to change if you want to use it for your own community.

## What it does

* Reaction roles for games/consoles
* Supports multiple reaction role messages
* Removes roles when reactions are removed
* DMs the server owner when someone mentions the bot
* Slash commands for posting rules/welcome messages
* Loads reusable messages from `.txt` files
* Optional admin/error logging channel

---

## Setup

### 1. Install dependencies

```bash
pip install discord.py python-dotenv
```

---

### 2. Create a `.env` file

Put this in the same folder as the bot:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
ADMIN_LOG_CHANNEL_ID=optional_channel_id
REACTION_ROLE_MESSAGE_IDS=message_id_one,message_id_two
OWNER_USER_ID=your_discord_user_id_here
RULES_CHANNEL_ID=your_rules_channel_id_here
```

---

### 3. Important Discord setup stuff

Before running the bot:

* Create all the roles listed in `REACTION_ROLE_MAP`
* Drag the bot role ABOVE the roles it manages
* Give the bot:

  * `Manage Roles`
  * `Read Messages`
  * `Send Messages`
* Enable these intents in the Discord Developer Portal:

  * Server Members Intent
  * Message Content Intent

---

## Running the bot

```bash
python bot.py
```
OR follow some tutorials on how to use Railway for the bot to run 24/7 

---

## Customizing it

Most of the customization is inside this section:

```python
REACTION_ROLE_MAP = {
    "❤️": "Switch",
    "💙": "PC",
    "💚": "Xbox",
}
```

Just swap the emojis and role names to match your own server.

You can also:

* Add more reaction role messages
* Add more slash commands
* Change the text files in `/messages`
* Turn role removal on/off with:

```python
REMOVE_ROLE_ON_UNREACT = True
```

---

## Slash Commands

Current commands:

* `/rules`
* `/welcome`

Both pull from text files inside the `messages/` folder.

---

## Notes

This was mainly built for a private friend server, so some things are opinionated and hardcoded for our setup.
But the structure is simple enough to tweak however you want.

If something breaks, check:

* Bot role hierarchy
* Permissions
* Emoji mappings
* Your `.env` values

Because 90% of Discord bot problems are one of those. There are some built in debugs to help with seeing what is being pulled 

---

## Future ideas

Improvements I might add later:

* More admin tools
* Goose related fun facts
* More memeber commands (FAQ, help, ect)

---

## License

N/A
