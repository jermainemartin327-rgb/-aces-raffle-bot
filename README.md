# Aces Raffle Bot

A simple Discord raffle bot with:

- 25 slots by default
- $20 entry display by default
- Slash commands
- Member slot claiming
- Paid / unpaid tracking
- Admin-only payment marking
- Random winner chosen only from paid entries
- SQLite persistence
- Editable lawful non-medical prize field

## 1. Create a Discord application

1. Go to the Discord Developer Portal.
2. Create a new application.
3. Open **Bot** and create/add the bot.
4. Copy the bot token.
5. Under OAuth2 > URL Generator, select:
   - `bot`
   - `applications.commands`
6. Recommended bot permissions:
   - Send Messages
   - View Channels
   - Use Application Commands
7. Invite the bot to your server.

## 2. Install

Python 3.10+ recommended.

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your token:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here
```

`GUILD_ID` is optional, but adding it makes slash-command updates appear much faster in that server.

## 3. Run

```bash
python bot.py
```

## Commands

- `/raffle_create prize:<prize>` — admin creates the raffle
- `/claim slot:<number>` — member claims a slot
- `/unclaim slot:<number>` — member releases an unpaid slot
- `/slots` — shows the board
- `/mark_paid slot:<number>` — admin marks a slot paid
- `/mark_unpaid slot:<number>` — admin reverses paid status
- `/raffle_close` — admin closes new claims
- `/raffle_open` — admin reopens claims
- `/draw` — randomly chooses from paid entries

## Default settings

The bot defaults to **25 slots** and an **entry fee display of $20**, but admins can change both in `/raffle_create`.

Payment collection itself is not handled by this bot. Admins verify payment separately and use `/mark_paid`.
