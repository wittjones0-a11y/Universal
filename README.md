<<<<<<< HEAD
# Universal Moderation Bot 🤖

A comprehensive Discord moderation and logging bot built with discord.py. Features user verification, message moderation, automatic warnings, and complete audit logging.

## Features ✨

- **User Verification**: Verification system for new members with code validation
- **Message Moderation**: Auto-detection and handling of spam, profanity, and rule violations
- **Warning System**: Progressive warning system with auto-mute after 3 warnings
- **Moderation Actions**: Warn, mute, unmute, kick, ban, and unban commands
- **Activity Logging**: Complete logging of messages, edits, deletions, and member changes
- **Audit Logs**: Detailed moderation history for users
- **Auto-Moderation**: Automatic muting and actions based on configured rules

## Requirements 📋

- Python 3.8+
- Discord.py 2.3.2+
- A Discord bot token

## Installation 🚀

1. **Clone/Download the bot files**
   ```bash
   cd "Universal bot"
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables**
   - Copy `.env.example` to `.env`
   - Add your Discord bot token to the `.env` file
   ```
   DISCORD_TOKEN=your_token_here
   ```

5. **Create a Discord bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to "Bot" section and create a bot
   - Copy the token and paste it in `.env`
   - Enable these Intents:
     - Message Content Intent
     - Server Members Intent
     - Guild Moderation Events Intent

6. **Invite the bot to your server**
   - Go to OAuth2 > URL Generator
   - Select scopes: `bot` and `applications.commands`
   - Select permissions:
     - Moderate Members (timeout)
     - Kick Members
     - Ban Members
     - Send Messages
     - Read Message History
     - Manage Messages (for potential message deletion)
   - Use the generated URL to invite the bot

## Running the Bot 🎮

```bash
python main.py
```

The bot will start and connect to Discord.

## Commands 📝

All commands are now slash commands (use `/` prefix):

### Moderation Commands
- `/warn <member> [reason]` - Warn a user (3 warnings = auto-mute)
- `/mute <member> [duration] [reason]` - Mute a user (duration in seconds, default 300)
- `/unmute <member>` - Unmute a user
- `/kick <member> [reason]` - Kick a user from the server
- `/ban <member> [reason]` - Ban a user from the server
- `/unban <user_id>` - Unban a user
- `/warnings [member]` - View warnings for a user
- `/modlog <member>` - View detailed moderation history

### Verification Commands
- `/verify` - Start the verification process
- `/verified [member]` - Check verification status
- `/verificationsetup [channel]` - Setup verification channel (Admin only)

### Logging Commands
- `/logs [member]` - View activity logs
- `/logsetup [channel]` - Set the channel for audit logs (Admin only)

### General Commands
- `/help` - Show all available commands

## Configuration ⚙️

Edit `config.py` to customize:
- Spam thresholds
- Mute durations
- Warning limits
- Banned words
- Auto-moderation settings
- Verification timeout
- Logging preferences

## Database 💾

The bot uses SQLite for data storage. Database files are stored in the `data/` directory:
- `bot_data.db` - All user data, warnings, logs, and moderation history

Tables:
- `users` - User accounts and verification status
- `message_logs` - Message history
- `moderation_logs` - Moderation actions
- `warnings` - User warnings

## Features in Detail 📖

### Verification System
- New members receive a DM with instructions
- They use `/verify` to start verification
- They solve a verification code challenge in the configured channel
- Once verified, they gain access to the server
- Admin can use `/verificationsetup` to set the verification channel

### Auto-Moderation
- Messages are logged automatically
- Spam detection (configurable threshold)
- Profanity filtering (customizable word list)
- Automatic escalation: warnings → mute → ban

### Audit Logging
- All moderation actions are logged
- Message edits and deletions tracked
- Member role and nickname changes logged
- Member joins and leaves recorded

### Progressive Enforcement
1. **1st warning** - User warned
2. **2nd warning** - User warned
3. **3rd warning** - User automatically muted for 1 hour
4. Manual escalation available for staff

## Troubleshooting 🔧

**Bot doesn't respond to commands:**
- Ensure the bot has "Send Messages" permission
- Check that the bot role is higher than user roles for moderation
- Verify the `DISCORD_TOKEN` in `.env` is correct

**Moderation commands don't work:**
- Make sure the bot role has "Moderate Members" permission
- Check that your role is higher than the bot's role for moderation
- Only admins can use moderation commands

**Verification not working:**
- Check that the bot can send DMs to users
- Verify the timeout setting in `config.py`

**Database errors:**
- Delete `data/bot_data.db` to reset the database
- Ensure `data/` directory exists and is writable

## Support & Contributing 🤝

For issues or feature requests, feel free to modify the code!

## License 📄

This bot is provided as-is for educational and personal use.

---

Made with ❤️ for Discord server management
