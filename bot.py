import os
import random
import sqlite3
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

DB_PATH = "raffle.db"
DEFAULT_SLOTS = 25
DEFAULT_ENTRY_FEE = 20


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raffle (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                title TEXT NOT NULL,
                prize TEXT NOT NULL,
                slot_count INTEGER NOT NULL,
                entry_fee REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                slot_number INTEGER PRIMARY KEY,
                user_id INTEGER,
                username TEXT,
                paid INTEGER NOT NULL DEFAULT 0
            )
        """)


def get_raffle():
    with db() as conn:
        return conn.execute("SELECT * FROM raffle WHERE id = 1").fetchone()


def get_slots():
    with db() as conn:
        return conn.execute("SELECT * FROM slots ORDER BY slot_number").fetchall()


def is_admin(interaction: discord.Interaction) -> bool:
    OWNER_ID = 1443381921651626046

    if interaction.user.id == OWNER_ID:
        return True

    if interaction.guild is None:
        return False

    perms = interaction.user.guild_permissions
    return perms.administrator or perms.manage_guild


    return f"${v:,.0f}" if float(v).is_integer() else f"${v:,.2f}"


class RaffleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        init_db()
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = RaffleBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="raffle_create", description="Create or replace the current raffle.")
@app_commands.describe(
    prize="Lawful non-medical prize",
    title="Raffle title",
    slots="Number of slots",
    entry_fee="Entry fee shown to members"
)
async def raffle_create(
    interaction: discord.Interaction,
    prize: str,
    title: str = "Aces Academy Raffle",
    slots: app_commands.Range[int, 2, 500] = DEFAULT_SLOTS,
    entry_fee: app_commands.Range[float, 0, 100000] = DEFAULT_ENTRY_FEE,
):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin permission required.", ephemeral=True)

    with db() as conn:
        conn.execute("DELETE FROM raffle")
        conn.execute("DELETE FROM slots")
        conn.execute(
            "INSERT INTO raffle (id, title, prize, slot_count, entry_fee, active) VALUES (1, ?, ?, ?, ?, 1)",
            (title, prize, slots, entry_fee),
        )
        conn.executemany(
            "INSERT INTO slots (slot_number, user_id, username, paid) VALUES (?, NULL, NULL, 0)",
            [(i,) for i in range(1, slots + 1)],
        )

    await interaction.response.send_message(
        f"✅ **{title}** created\n🏆 Prize: **{prize}**\n🎟️ Slots: **{slots}**\n💵 Entry: **{money(entry_fee)}**"
    )


@bot.tree.command(name="claim", description="Claim an available raffle slot.")
@app_commands.describe(slot="Slot number to claim")
async def claim(interaction: discord.Interaction, slot: int):
    raffle = get_raffle()
    if not raffle or not raffle["active"]:
        return await interaction.response.send_message("There is no active raffle.", ephemeral=True)

    if slot < 1 or slot > raffle["slot_count"]:
        return await interaction.response.send_message(
            f"Choose a slot from 1 to {raffle['slot_count']}.", ephemeral=True
        )

    with db() as conn:
        current = conn.execute("SELECT * FROM slots WHERE slot_number = ?", (slot,)).fetchone()
        if current["user_id"] is not None:
            return await interaction.response.send_message(
                f"Slot #{slot} is already claimed by **{current['username']}**.", ephemeral=True
            )

        conn.execute(
            "UPDATE slots SET user_id = ?, username = ?, paid = 0 WHERE slot_number = ?",
            (interaction.user.id, str(interaction.user), slot),
        )

    await interaction.response.send_message(
        f"🎟️ {interaction.user.mention} claimed **slot #{slot}**.\n"
        f"Status: **UNPAID** — an admin must mark it paid."
    )


@bot.tree.command(name="unclaim", description="Release your raffle slot.")
@app_commands.describe(slot="Slot number to release")
async def unclaim(interaction: discord.Interaction, slot: int):
    with db() as conn:
        current = conn.execute("SELECT * FROM slots WHERE slot_number = ?", (slot,)).fetchone()
        if not current or current["user_id"] is None:
            return await interaction.response.send_message("That slot is already open.", ephemeral=True)

        can_release = current["user_id"] == interaction.user.id or is_admin(interaction)
        if not can_release:
            return await interaction.response.send_message("You can only release your own slot.", ephemeral=True)

        if current["paid"] and not is_admin(interaction):
            return await interaction.response.send_message(
                "A paid slot can only be released by an admin.", ephemeral=True
            )

        conn.execute(
            "UPDATE slots SET user_id = NULL, username = NULL, paid = 0 WHERE slot_number = ?",
            (slot,),
        )

    await interaction.response.send_message(f"♻️ Slot **#{slot}** is open again.")


@bot.tree.command(name="mark_paid", description="Admin: mark a claimed slot as paid.")
@app_commands.describe(slot="Slot number")
async def mark_paid(interaction: discord.Interaction, slot: int):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin permission required.", ephemeral=True)

    with db() as conn:
        current = conn.execute("SELECT * FROM slots WHERE slot_number = ?", (slot,)).fetchone()
        if not current or current["user_id"] is None:
            return await interaction.response.send_message("That slot has not been claimed.", ephemeral=True)
        conn.execute("UPDATE slots SET paid = 1 WHERE slot_number = ?", (slot,))

    await interaction.response.send_message(f"✅ Slot **#{slot}** marked **PAID**.")


@bot.tree.command(name="mark_unpaid", description="Admin: mark a claimed slot as unpaid.")
@app_commands.describe(slot="Slot number")
async def mark_unpaid(interaction: discord.Interaction, slot: int):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin permission required.", ephemeral=True)

    with db() as conn:
        current = conn.execute("SELECT * FROM slots WHERE slot_number = ?", (slot,)).fetchone()
        if not current or current["user_id"] is None:
            return await interaction.response.send_message("That slot has not been claimed.", ephemeral=True)
        conn.execute("UPDATE slots SET paid = 0 WHERE slot_number = ?", (slot,))

    await interaction.response.send_message(f"🟡 Slot **#{slot}** marked **UNPAID**.")


@bot.tree.command(name="slots", description="Show the current raffle board.")
async def slots(interaction: discord.Interaction):
    raffle = get_raffle()
    if not raffle:
        return await interaction.response.send_message("No raffle has been created.", ephemeral=True)

    rows = get_slots()
    lines = []
    claimed = paid = 0
    for row in rows:
        if row["user_id"] is None:
            status = "⬜ OPEN"
        elif row["paid"]:
            status = f"✅ {row['username']}"
            claimed += 1
            paid += 1
        else:
            status = f"🟡 {row['username']} (unpaid)"
            claimed += 1
        lines.append(f"`#{row['slot_number']:02d}` {status}")

    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 1800:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)

    total_slots = raffle["slot_count"]
    filled = claimed

    bar_length = 20
    filled_blocks = round((filled / total_slots) * bar_length)
    progress_bar = "█" * filled_blocks + "░" * (bar_length - filled_blocks)

    header = (
        f"🎉 **RANDOMIZER STATUS** 🎉\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 **Prize:** {raffle['prize']}\n"
                f"💰 **Donation:** {money(raffle['entry_fee'])}\n"
                f"📊 **Spots:** {progress_bar} {filled}/{total_slots}\n"
        f"🏆 **Winners:** 1\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    slot_text = ""
    for row in rows:
        if row["user_id"] is None:
            name = "OPEN"
        else:
            name = row["username"]

        slot_text += f"⭐ {row['slot_number']:02d}. {name}\n"

    message = header + slot_text

    await interaction.response.send_message(message)

@bot.tree.command(name="draw", description="Admin: randomly select a winner from PAID entries.")
async def draw(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin permission required.", ephemeral=True)

    raffle = get_raffle()
    if not raffle:
        return await interaction.response.send_message("No raffle exists.", ephemeral=True)

    with db() as conn:
        eligible = conn.execute(
            "SELECT * FROM slots WHERE paid = 1 AND user_id IS NOT NULL ORDER BY slot_number"
        ).fetchall()

    if not eligible:
        return await interaction.response.send_message("There are no paid entries to draw from.", ephemeral=True)

    winner = random.SystemRandom().choice(eligible)

    await interaction.response.send_message(
        "🎲 **RANDOMIZER COMPLETE** 🎲\n\n"
        f"🏆 **WINNER:** <@{winner['user_id']}>\n"
        f"🎟️ **Winning slot:** #{winner['slot_number']}\n"
        f"🎁 **Prize:** {raffle['prize']}\n\n"
        "Congratulations! 🎉"
    )


@bot.tree.command(name="raffle_close", description="Admin: close claiming for the current raffle.")
async def raffle_close(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin permission required.", ephemeral=True)
    with db() as conn:
        conn.execute("UPDATE raffle SET active = 0 WHERE id = 1")
    await interaction.response.send_message("🔒 Raffle claiming is now closed.")


@bot.tree.command(name="raffle_open", description="Admin: reopen claiming for the current raffle.")
async def raffle_open(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin permission required.", ephemeral=True)
    with db() as conn:
        conn.execute("UPDATE raffle SET active = 1 WHERE id = 1")
    await interaction.response.send_message("🔓 Raffle claiming is now open.")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Add it to your .env file.")

bot.run(TOKEN)
