import discord
from discord.ext import commands, tasks
import os
import requests
from dotenv import load_dotenv

# Charger les variables depuis le fichier .env
load_dotenv()

# Récupération des variables d'environnement
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
NOTIFICATION_CHANNEL_ID = int(os.getenv("NOTIFICATION_CHANNEL_ID"))
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
STREAMER_NAME = os.getenv("STREAMER_NAME")

# Crée une instance de bot
intents = discord.Intents.default()
intents.members = True  # Pour gérer les membres (mute, unmute)
bot = commands.Bot(command_prefix="!", intents=intents)

# Liste pour éviter les boucles infinies
processing_users = set()
twitch_access_token = None


def get_twitch_access_token():
    """
    Obtenir un token d'accès Twitch pour utiliser leur API.
    """
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        print("Erreur lors de la récupération du token Twitch :", response.json())
        return None


def check_stream_status():
    """
    Vérifie si le streameur est en ligne.
    """
    global twitch_access_token
    if twitch_access_token is None:
        twitch_access_token = get_twitch_access_token()

    url = f"https://api.twitch.tv/helix/streams?user_login={STREAMER_NAME}"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_access_token}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data["data"]:  # Si le tableau 'data' contient des informations
            return True, data["data"][0]["title"]
        return False, None
    elif response.status_code == 401:  # Si le token a expiré
        twitch_access_token = get_twitch_access_token()
        return False, None
    else:
        print("Erreur lors de la vérification du statut Twitch :", response.json())
        return False, None


@tasks.loop(minutes=1)
async def notify_stream():
    """
    Tâche périodique pour vérifier si le streamer est en live et notifier le canal.
    """
    is_live, title = check_stream_status()
    if is_live:
        notification_channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if notification_channel:
            await notification_channel.send(
                f"🎥 **{STREAMER_NAME} est en live !** 🎮\n"
                f"**Titre du stream :** {title}\n"
                f"Regardez le stream ici : https://www.twitch.tv/{STREAMER_NAME}"
            )


@bot.event
async def on_ready():
    """
    Démarre la tâche périodique une fois que le bot est prêt.
    """
    print(f"{bot.user.name} est connecté.")
    notify_stream.start()


# Gère les permission du canal vocal
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
