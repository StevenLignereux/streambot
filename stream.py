import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

# Charger les variables depuis le fichier .env
load_dotenv()

# Récupération des variables d'environnement
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(
    os.getenv("CHANNEL_ID")
)  # Assurez-vous que CHANNEL_ID est bien un nombre

# Vérifications
if not TOKEN:
    print("Erreur : Le token du bot n'est pas défini dans le fichier .env.")
    exit(1)

if not CHANNEL_ID:
    print("Erreur : L'ID du canal n'est pas défini dans le fichier .env.")
    exit(1)

# Crée une instance de bot
intents = discord.Intents.default()
intents.members = True  # Pour gérer les membres (mute, unmute)
bot = commands.Bot(command_prefix="!", intents=intents)

# Liste pour éviter les boucles infinies
processing_users = set()


@bot.event
async def on_voice_state_update(member, before, after):
    # Vérifie si l'utilisateur rejoint le canal vocal spécifique
    if after.channel is not None and after.channel.id == CHANNEL_ID:
        # Empêche les boucles infinies en vérifiant si l'utilisateur est déjà en cours de traitement
        if member.id in processing_users:
            return

        # Ajoute l'utilisateur à la liste de traitement
        processing_users.add(member.id)

        try:
            # Vérifie si le bot a les permissions nécessaires
            if not after.channel.guild.me.guild_permissions.mute_members:
                print("Le bot n'a pas la permission de mute des membres.")
                return

            # Mute l'utilisateur immédiatement
            await member.edit(mute=True)

            # Ajout d'un délai pour éviter le rate limit
            await asyncio.sleep(1)

            # Envoie un message privé à l'utilisateur
            try:
                dm = await member.create_dm()  # Crée un canal de message privé
                await dm.send(
                    "Tu es actuellement mute dans le canal réservé au stream. "
                    "Ce canal est réservé aux streams. Si tu souhaites être démuté, "
                    "réponds par 'oui'. Sinon, tu seras expulsé du canal vocal."
                )

                # Attendre la réponse de l'utilisateur dans le DM pendant un certain temps
                def check(m):
                    return (
                        m.author == member
                        and m.channel == dm
                        and m.content.lower() in ["oui", "non"]
                    )

                try:
                    response = await bot.wait_for("message", check=check, timeout=30.0)

                    if response.content.lower() == "oui":
                        # Démute l'utilisateur si la réponse est "oui"
                        await member.edit(mute=False)
                        await dm.send("Tu as été démuté.")
                    else:
                        # Expulse l'utilisateur du canal vocal si la réponse est "non"
                        await member.move_to(
                            None
                        )  # Déplace l'utilisateur en dehors du canal vocal
                        await dm.send(
                            "Tu as été expulsé du canal vocal pour ne pas avoir confirmé."
                        )

                except asyncio.TimeoutError:
                    # Si l'utilisateur ne répond pas à temps, expulsion
                    await member.move_to(None)
                    await dm.send(
                        "Tu n'as pas répondu à temps, et as été expulsé du canal vocal."
                    )

            except discord.errors.Forbidden:
                # Si le bot ne peut pas envoyer de message privé (ex. si l'utilisateur a les DMs fermés)
                await member.move_to(None)
                print(f"Impossible d'envoyer un message à {member.name}. DMs fermés ?")

        except Exception as e:
            print(f"Une erreur s'est produite : {e}")

        finally:
            # Retire l'utilisateur de la liste de traitement
            processing_users.remove(member.id)


# Commande pour démarrer le bot
@bot.command()
async def start(ctx):
    await ctx.send(
        "Le bot est en ligne et prêt à gérer les mutings dans le canal de stream."
    )


# Lancer le bot
bot.run(TOKEN)
