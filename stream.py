import discord
from discord.ext import commands
import asyncio

intents = discord.Intents.default()
intents.messages = True
intents.reactions = True
intents.voice_states = True
intents.message_content = True  # Ajoutez cette ligne pour activer l'intent message_content
intents.members = True  # Ajoutez cette ligne pour activer l'intent members

bot = commands.Bot(command_prefix="!", intents=intents)

# ID du canal vocal que tu veux restreindre
voice_channel_id = ""

# Dictionnaire pour stocker les IDs de guilde et de message
confirmation_messages = {}

# Dictionnaire pour suivre les membres qui ont déjà reçu une demande de confirmation
pending_confirmations = {}

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    print("Guildes auxquelles le bot est connecté :")
    for guild in bot.guilds:
        print(f"Nom de la guilde : {guild.name}, ID de la guilde : {guild.id}")
        print("Membres de la guilde :")
        for member in guild.members:
            print(f"Nom du membre : {member.name}, ID du membre : {member.id}")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == voice_channel_id:
        # Vérifie si le membre a déjà une demande de confirmation en attente
        if member.id in pending_confirmations:
            return

        # Empêche les événements ultérieurs pour ce membre jusqu'à la confirmation
        bot.prevent_double_confirmation = True

        # Déplace immédiatement l'utilisateur hors du canal vocal
        await member.move_to(None)

        # Envoie un message de confirmation en privé (DM)
        try:
            msg = await member.send("Veux-tu vraiment te connecter au canal vocal ? Réagis avec ✅ pour confirmer.")
            await msg.add_reaction("✅")

            # Stocke l'ID de la guilde et du message
            confirmation_messages[msg.id] = (member.guild.id, member.id)
            pending_confirmations[member.id] = msg.id

            def check(reaction, user):
                return user == member and str(reaction.emoji) == "✅" and reaction.message.id == msg.id

            try:
                # Attend la réaction de l'utilisateur
                reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await member.send("Tu n'as pas confirmé à temps.")
                # Supprime l'entrée du dictionnaire après le timeout
                if member.id in pending_confirmations:
                    del pending_confirmations[member.id]
            else:
                # Vérifie si l'utilisateur est toujours en attente de rejoindre le même canal vocal
                if bot.prevent_double_confirmation:
                    # Vérifie si le membre est toujours connecté à un canal vocal
                    if member.voice and member.voice.channel:
                        # Permet au membre de rejoindre le canal vocal
                        channel = discord.utils.get(member.guild.voice_channels, id=voice_channel_id)
                        await member.move_to(channel)
                        await member.send("Tu as confirmé et as été déplacé dans le canal vocal.")
                    else:
                        await member.send("Tu n'es plus connecté à un canal vocal.")
                    # Supprime l'entrée du dictionnaire après confirmation
                    if member.id in pending_confirmations:
                        del pending_confirmations[member.id]
                bot.prevent_double_confirmation = False
        except discord.Forbidden:
            print(f"Impossible d'envoyer un DM à {member.name}")

@bot.event
async def on_raw_reaction_add(payload):
    # Ignorer les réactions du bot
    if payload.user_id == bot.user.id:
        return

    # Vérifie si le message ID est dans le dictionnaire
    if payload.message_id in confirmation_messages:
        guild_id, member_id = confirmation_messages[payload.message_id]

        # Récupérer la guilde
        guild = bot.get_guild(guild_id)
        if guild is None:
            print(f"Impossible de trouver la guilde avec l'ID {guild_id}")
            return

        # Récupérer le membre
        member = guild.get_member(member_id)
        if member is None:
            print(f"Impossible de trouver le membre avec l'ID {member_id}")
            return

        # Vérifie si la réaction est celle de confirmation
        if str(payload.emoji) == "✅":
            # Vérifie si le membre est toujours connecté à un canal vocal
            if member.voice and member.voice.channel:
                # Permet au membre de rejoindre le canal vocal
                channel = discord.utils.get(guild.voice_channels, id=voice_channel_id)
                if channel:
                    await member.move_to(channel)
                    await member.send("Tu as confirmé et as été déplacé dans le canal vocal.")
                else:
                    print(f"Impossible de trouver le canal vocal avec l'ID {voice_channel_id}")
            else:
                await member.send("Tu n'es plus connecté à un canal vocal.")
            # Supprime l'entrée du dictionnaire après confirmation
            if member.id in pending_confirmations:
                del pending_confirmations[member.id]

bot.run('')

