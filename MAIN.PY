import os
import random
import discord
from discord.ext import commands
from discord import app_commands

# ================== CONFIG ==================

# In Replit, add a Secret called TOKEN with your bot token
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
raise ValueError(
"TOKEN environment variable not set. In Replit, add a secret named TOKEN with your bot token."
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== GAME STATE ==================

# games[guild_id] = {
# "channel_id": int, # channel where /lover_start was used
# "secret_channel_id": int | None,# secret room channel
# "is_active": bool,
# "players": set[int],
# "targets": dict[int, int],
# "scores": dict[int, int],
# "round": int,
# "max_rounds": int,
# "reaction_scored": set[(message_id, reactor_id, emoji_str)]
# }
games = {}

CHALLENGES = [
"Send your target a flirty compliment in the secret room 😉",
"Confess your 'secret love' to your target using **only emojis** 😏💖",
"Drop your cheesiest pickup line for your target 🧀",
"Describe your target like they’re the main character in a romance movie 🌟",
"Send a mysterious coded message that only your target can understand 🕵️",
"Tell your target their best trait, but exaggerate it wildly 😂",
]

POINT_EMOJIS = ["❤️", "😳", "😂"]
POINTS_PER_REACTION = 1
POINTS_PER_COMPLETION = 2


# ================== HELPERS ==================

def get_game(guild_id: int):
return games.get(guild_id)


def assign_targets(players: list[int]) -> dict[int, int]:
"""Assign each player a random target in a circle so nobody gets themselves."""
shuffled = players[:]
random.shuffle(shuffled)
targets = {}
for i, p in enumerate(shuffled):
targets[p] = shuffled[(i + 1) % len(shuffled)]
return targets


def format_scores(scores: dict[int, int], guild: discord.Guild) -> str:
if not scores:
return "No points yet. Everyone is shy 👀"

sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
lines = []
for i, (user_id, pts) in enumerate(sorted_scores, start=1):
member = guild.get_member(user_id)
name = member.display_name if member else f"User {user_id}"
lines.append(f"**{i}. {name}** — ❤️ {pts} points")
return "\n".join(lines)


async def ensure_secret_room(guild: discord.Guild, game: dict, base_channel: discord.abc.GuildChannel):
"""
Create a secret text channel visible only to game players + bot + admins.
If it already exists, just return it.
"""
if game.get("secret_channel_id"):
channel = guild.get_channel(game["secret_channel_id"])
if channel:
return channel

# permissions
overwrites = {}

# Hide from everyone by default
overwrites[guild.default_role] = discord.PermissionOverwrite(
view_channel=False
)

# Allow players
for user_id in game["players"]:
member = guild.get_member(user_id)
if member:
overwrites[member] = discord.PermissionOverwrite(
view_channel=True,
send_messages=True,
read_message_history=True
)

# Allow bot itself
bot_member = guild.get_member(bot.user.id)
if bot_member:
overwrites[bot_member] = discord.PermissionOverwrite(
view_channel=True,
send_messages=True,
read_message_history=True,
manage_channels=True,
manage_messages=True
)

# Optionally allow admins/mods (uncomment this if you want server admins to see)
# for role in guild.roles:
# if role.permissions.administrator:
# overwrites[role] = discord.PermissionOverwrite(
# view_channel=True,
# send_messages=True,
# read_message_history=True
# )

category = base_channel.category # keep same category if possible
channel_name = f"secret-lover-room"

secret_channel = await guild.create_text_channel(
name=channel_name,
category=category,
overwrites=overwrites,
reason="Secret Lover game secret room"
)

game["secret_channel_id"] = secret_channel.id
return secret_channel


# ================== EVENTS ==================

@bot.event
async def on_ready():
await bot.tree.sync()
print(f"Logged in as {bot.user} (ID: {bot.user.id})")
print("Slash commands synced. Bot is online!")


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User | discord.Member):
"""
Give points when a player's *target* reacts with special emojis to their message
in any channel (especially the secret room).
"""
if user.bot:
return

message = reaction.message
if not message.guild:
return

guild_id = message.guild.id
game = get_game(guild_id)
if not game or not game.get("is_active"):
return

author = message.author
if author.bot:
return

if author.id not in game["players"]:
return

targets = game["targets"]
if author.id not in targets:
return

target_id = targets[author.id]
if user.id != target_id:
return

emoji_str = str(reaction.emoji)
if emoji_str not in POINT_EMOJIS:
return

key = (message.id, user.id, emoji_str)
if key in game["reaction_scored"]:
return

game["reaction_scored"].add(key)
game["scores"][author.id] = game["scores"].get(author.id, 0) + POINTS_PER_REACTION

print(f"Gave {POINTS_PER_REACTION} point(s) to {author} because their target reacted {emoji_str}.")


# ================== SLASH COMMANDS ==================

@bot.tree.command(name="lover_start", description="Start a new Secret Lover game in this channel.")
@app_commands.describe(max_rounds="How many rounds you want to play (default 3).")
async def lover_start(interaction: discord.Interaction, max_rounds: int = 3):
guild_id = interaction.guild_id
channel = interaction.channel

games[guild_id] = {
"channel_id": channel.id,
"secret_channel_id": None,
"is_active": False, # becomes True when we actually begin
"players": set(),
"targets": {},
"scores": {},
"round": 0,
"max_rounds": max_rounds,
"reaction_scored": set(),
}

await interaction.response.send_message(
f"💘 **Secret Lover** started in {channel.mention}!\n"
f"Use `/lover_join` to enter the game.\n"
f"When ready, `/lover_begin` will assign secret lovers "
f"and create a **secret room** just for the players.\n"
f"The game will have up to **{max_rounds} rounds**."
)


@bot.tree.command(name="lover_join", description="Join the current Secret Lover game.")
async def lover_join(interaction: discord.Interaction):
guild_id = interaction.guild_id
user = interaction.user

game = get_game(guild_id)
if not game:
await interaction.response.send_message(
"There is no Secret Lover game right now. Start one with `/lover_start`.",
ephemeral=True,
)
return

if game["is_active"]:
await interaction.response.send_message(
"The game has already begun, you can’t join now 💔",
ephemeral=True,
)
return

if user.id in game["players"]:
await interaction.response.send_message(
"You’re already in the game 😉",
ephemeral=True,
)
return

game["players"].add(user.id)
game["scores"].setdefault(user.id, 0)

await interaction.response.send_message(f"💞 {user.mention} joined the Secret Lover game!")


@bot.tree.command(name="lover_begin", description="Lock players, assign secret lovers, make the secret room, and begin.")
async def lover_begin(interaction: discord.Interaction):
guild_id = interaction.guild_id
guild = interaction.guild
game = get_game(guild_id)

if not game:
await interaction.response.send_message(
"There is no Secret Lover game. Start one with `/lover_start`."
)
return

if game["is_active"]:
await interaction.response.send_message("The game is already active!")
return

players = list(game["players"])
if len(players) < 2:
await interaction.response.send_message(
"You need at least **2 players** to start! 💔"
)
return

# Assign targets & activate game
game["targets"] = assign_targets(players)
game["is_active"] = True
game["round"] = 0
game["reaction_scored"] = set()

# DM each player their target
for pid, tid in game["targets"].items():
member = guild.get_member(pid)
target_member = guild.get_member(tid)
if not member or not target_member:
continue
try:
dm = await member.create_dm()
await dm.send(
f"💘 **Secret Lover** 💘\n"
f"Your secret target is: **{target_member.display_name}**\n\n"
f"You'll be playing inside a **secret room** on the server.\n"
f"Watch for the bot to announce it!"
)
except discord.Forbidden:
pass

# Create secret room channel
base_channel = interaction.channel
secret_channel = await ensure_secret_room(guild, game, base_channel)

await secret_channel.send(
"💘 **Welcome to the Secret Lover Room** 💘\n"
"Only players in this game can see this channel.\n"
"Your secret targets have been DMed to you.\n"
"Use `/lover_round` to start the first seduction challenge 💌"
)

await interaction.response.send_message(
f"🔒 Lobby locked, secret lovers assigned, and secret room created: {secret_channel.mention}\n"
f"Head there for all your flirty challenges!"
)


@bot.tree.command(name="lover_room", description="Get a link to the secret room, if there is one.")
async def lover_room(interaction: discord.Interaction):
guild_id = interaction.guild_id
guild = interaction.guild
game = get_game(guild_id)

if not game or not game.get("secret_channel_id"):
await interaction.response.send_message(
"There is no secret room yet. Start a game with `/lover_start` and `/lover_begin`.",
ephemeral=True,
)
return

channel = guild.get_channel(game["secret_channel_id"])
if not channel:
await interaction.response.send_message(
"The secret room seems to be missing. Ask an admin to check channel permissions.",
ephemeral=True,
)
return

await interaction.response.send_message(
f"Your secret room is: {channel.mention}", ephemeral=True
)


@bot.tree.command(name="lover_round", description="Start a new seduction challenge round in the secret room.")
async def lover_round(interaction: discord.Interaction):
guild_id = interaction.guild_id
guild = interaction.guild
game = get_game(guild_id)

if not game or not game["is_active"]:
await interaction.response.send_message(
"There is no active Secret Lover game. Start one with `/lover_start`."
)
return

if game["round"] >= game["max_rounds"]:
await interaction.response.send_message(
"You’ve already played all the rounds! Use `/lover_end` to finish the game."
)
return

# Find the secret room
channel = None
if game.get("secret_channel_id"):
channel = guild.get_channel(game["secret_channel_id"])

if channel is None:
# fallback to the command channel
channel = interaction.channel

game["round"] += 1
challenge = random.choice(CHALLENGES)

# Acknowledge command (ephemeral to avoid clutter)
await interaction.response.send_message(
f"Starting **Round {game['round']}** in {channel.mention}!", ephemeral=True
)

await channel.send(
f"💌 **Secret Lover – Round {game['round']}** 💌\n"
f"**Challenge:** {challenge}\n\n"
f"Once you’ve done your challenge, use `/lover_done` to claim your points.\n"
f"If your *target* reacts to your message with {', '.join(POINT_EMOJIS)}, "
f"you earn extra points automatically!"
)


@bot.tree.command(name="lover_done", description="Claim points for completing your current round challenge.")
async def lover_done(interaction: discord.Interaction):
guild_id = interaction.guild_id
user = interaction.user
game = get_game(guild_id)

if not game or not game["is_active"]:
await interaction.response.send_message(
"There is no active Secret Lover game right now.",
ephemeral=True,
)
return

if user.id not in game["players"]:
await interaction.response.send_message(
"You’re not in this Secret Lover game.",
ephemeral=True,
)
return

game["scores"][user.id] = game["scores"].get(user.id, 0) + POINTS_PER_COMPLETION

await interaction.response.send_message(
f"💖 {user.mention} claimed **{POINTS_PER_COMPLETION} points** for completing the challenge!"
)


@bot.tree.command(name="lover_scores", description="Show the current Secret Lover leaderboard.")
async def lover_scores(interaction: discord.Interaction):
guild_id = interaction.guild_id
guild = interaction.guild
game = get_game(guild_id)

if not game:
await interaction.response.send_message("There is no Secret Lover game right now.")
return

text = format_scores(game["scores"], guild)
await interaction.response.send_message(f"📊 **Secret Lover Leaderboard** 📊\n{text}")


@bot.tree.command(name="lover_end", description="End the game and announce the Top Lover.")
async def lover_end(interaction: discord.Interaction):
guild_id = interaction.guild_id
guild = interaction.guild
game = get_game(guild_id)

if not game:
await interaction.response.send_message("There is no Secret Lover game to end.")
return

scores = game["scores"]
if not scores:
await interaction.response.send_message("No one scored any points. Love remains a mystery 💔")
games.pop(guild_id, None)
return

sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
winner_id, winner_points = sorted_scores[0]
winner_member = guild.get_member(winner_id)
winner_name = winner_member.display_name if winner_member else f"User {winner_id}"

leaderboard_text = format_scores(scores, guild)

await interaction.response.send_message(
f"👑 **Top Lover Announcement** 👑\n\n"
f"The **Top Lover** is **{winner_name}** with **{winner_points} points**!\n\n"
f"Full leaderboard:\n{leaderboard_text}"
)

games.pop(guild_id, None)


# ================== RUN BOT ==================

bot.run(TOKEN)

