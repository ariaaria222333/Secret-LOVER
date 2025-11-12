import os
import discord
from discord.ext import commands
from discord import app_commands
import random
TOKEN = os.getenv("DISCORD_TOKEN")  # Railway will provide this
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
games = {}
CHALLENGES = [
    "Send your target a flirty compliment :wink:",
    "Confess your love using only emojis :smirk::sparkling_heart:",
    "Give your target your cheesiest pickup line :cheese_wedge:",
    "Describe your target like they're a movie star :star2:",
    "Send a mysterious coded message your target must decode :sleuth_or_spy:",
]
def assign_targets(players):
    shuffled = players[:]
    random.shuffle(shuffled)
    result = {}
    for i, p in enumerate(shuffled):
        result[p] = shuffled[(i + 1) % len(shuffled)]
    return result
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is online and commands are synced!")
@bot.tree.command(name="start", description="Start a Secret Lover game.")
async def start(interaction: discord.Interaction):
    games[interaction.guild_id] = {
        "players": [],
        "started": False,
        "scores": {},
        "targets": {}
    }
    await interaction.response.send_message(":cupid: **Secret Lover has begun!** Use `/join` to enter.")
@bot.tree.command(name="join", description="Join the current Secret Lover game.")
async def join(interaction: discord.Interaction):
    game = games.get(interaction.guild_id)
    if not game:
        return await interaction.response.send_message("No game running. Use `/start` first.")
    if game["started"]:
        return await interaction.response.send_message("Game already started!")
    user = interaction.user.id
    if user not in game["players"]:
        game["players"].append(user)
        game["scores"][user] = 0
    await interaction.response.send_message(f"{interaction.user.mention} joined the game!")
@bot.tree.command(name="begin", description="Assign secret lovers and begin.")
async def begin(interaction: discord.Interaction):
    game = games.get(interaction.guild_id)
    if not game:
        return await interaction.response.send_message("No game running.")
    if len(game["players"]) < 2:
        return await interaction.response.send_message("Need at least 2 players!")
    game["started"] = True
    game["targets"] = assign_targets(game["players"])
    # DM each player their target
    for pid, tid in game["targets"].items():
        user = interaction.guild.get_member(pid)
        target = interaction.guild.get_member(tid)
        if not user or not target:
            continue
        try:
            await user.send(f"Your secret target is **{target.display_name}** :cupid:")
        except discord.Forbidden:
            # Can't DM the user; ignore
            pass
    await interaction.response.send_message("Targets assigned! Use `/round` to start a challenge.")
@bot.tree.command(name="round", description="Start a new seduction challenge round.")
async def round_cmd(interaction: discord.Interaction):
    game = games.get(interaction.guild_id)
    if not game or not game["started"]:
        return await interaction.response.send_message("Game not started.")
    challenge = random.choice(CHALLENGES)
    await interaction.response.send_message(f"**New Seduction Challenge:**\n{challenge}")
@bot.tree.command(name="score", description="Show current scores.")
async def score(interaction: discord.Interaction):
    game = games.get(interaction.guild_id)
    if not game:
        return await interaction.response.send_message("No game running.")
    msg = ":heart: **Scores** :heart:\n"
    if not game["scores"]:
        msg += "No scores yet!"
    else:
        for pid, pts in game["scores"].items():
            member = interaction.guild.get_member(pid)
            name = member.display_name if member else f"User {pid}"
            msg += f"**{name}** — {pts} points\n"
    await interaction.response.send_message(msg)
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set!")
bot.run(TOKEN)
