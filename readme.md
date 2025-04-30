# Discord Bot Template

A simple, reusable Discord bot template with owner/moderator permissions, help system, cog management, and slash commands.

## Features

- **Permission System**: Built-in bot owner and server moderator permission controls
- **Help System**: Automated help command generation via decorators
- **Reloadable Cogs**: Easy shutdown and reboot commands
- **Slash Commands**: Integrated slash command support
- **Clean Structure**: Organized file structure for easy expansion

## Setup

1. **Install Requirements**

```bash
pip install -r requirements.txt
```

2. **Configure the Bot**

Edit `config.py` with your:
- Discord bot token
- Bot owner Discord ID
- Moderator role IDs
- Command prefix
- Other settings

3. **Run the Bot**

```bash
# Create and activate a virtual environment (optional)
python -m venv venv
venv\Scripts\activate

# Run the bot
python main.py
```

## Project Structure

```
discord-bot/
├── main.py           # Main bot entry point
├── config.py         # Bot configuration
├── utils.py          # Utility functions and decorators
├── cogs/
│   ├── commands.py   # Regular command cog
│   ├── slash.py      # Slash command cog
│   └── ...           # Add more cogs as needed
├── requirements.txt  # Python package requirements
├── .gitignore        # Git ignore file
└── README.md         # Documentation
```

## Adding Commands

### Regular Commands

Add new commands to `cogs/commands.py` or create new cog files. Use the decorators to specify permissions:

```python
@commands.command()
@owner_only()  # For owner-only commands
@command_help("owner", "Description of command", "usage")
async def my_command(self, ctx):
    await ctx.send("Command response")
```

```python
@commands.command()
@mod_only()  # For moderator commands
@command_help("mod", "Description of command", "usage")
async def mod_command(self, ctx):
    await ctx.send("Moderator command response")
```

```python
@commands.command()
@command_help("general", "Description of command", "usage")
async def general_command(self, ctx):
    await ctx.send("General command response")
```

### Slash Commands

Add new slash commands to `cogs/slash.py`:

```python
@app_commands.command(name="command_name", description="Command description")
@is_owner()  # For owner-only commands
async def slash_command(self, interaction: discord.Interaction):
    await interaction.response.send_message("Command response")
```

## Loading New Cogs

To add a new cog file:

1. Create a new Python file in the `cogs` directory
2. Define your cog class inheriting from `commands.Cog`
3. Add the setup function at the end of the file:

```python
async def setup(bot):
    await bot.add_cog(YourCogName(bot))
```

The bot will automatically load all cogs in the `cogs` directory on startup.

## Permissions

- **Owner**: Full access to all commands
- **Moderators**: Access to moderation commands
- **Users**: Access to general commands

## Help System

The help system is automatically populated from command decorators, separating commands by permission level:

- `!help` - Shows all commands available to the user
- `!help command_name` - Shows detailed help for a specific command

## License

This template is available for free use.

## Extending

This template is designed for easy extension. Add new cogs, commands, and features as needed for your specific bot use case.
