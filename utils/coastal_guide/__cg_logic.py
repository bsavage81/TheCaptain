import asyncio
import discord
from dataclasses import dataclass
from utils.core_features.__constants import REALM_NAME, GUIDE_DEFAULTS


@dataclass(frozen=True)
class GuideContent:
    web_url: str = ""
    pdf_url: str = ""
    question: str = ""
    answer: str = ""
    answer_match: str = "contains"

    def accepts(self, response):
        response = response.strip().casefold()
        expected = self.answer.casefold()
        if not expected:
            return False
        return (
            expected in response
            if self.answer_match == "contains"
            else response == expected
        )

    @property
    def configured(self):
        return bool((self.web_url or self.pdf_url) and self.question and self.answer)


def load_guide_content(settings, questions=None):
    """Guide cells are opt-in; POI B1:B6 is never assumed to be guide content."""
    import re

    values = {}
    cells = settings.get("guide_cells", {})
    if not isinstance(cells, dict) or set(cells) - {
        "web_url",
        "pdf_url",
        "question",
        "answer",
    }:
        raise ValueError(
            "guide_cells supports web_url, pdf_url, question and answer only"
        )
    for key in ("web_url", "pdf_url", "question", "answer"):
        value = (
            settings[f"guide_{key}"]
            if settings.get("configuration_source") == "database"
            else settings.get(f"guide_{key}", GUIDE_DEFAULTS[key])
        ) or ""
        if key in cells:
            address = cells[key]
            if not isinstance(address, str) or not re.fullmatch(
                r"[A-Z]+[1-9][0-9]*", address
            ):
                raise ValueError("Guide cells must be explicit uppercase A1 addresses")
            if questions is None:
                raise ValueError(
                    "Guide cell selection requires the markers Questions worksheet"
                )
            value = questions.acell(address).value or ""
        if not isinstance(value, str):
            raise ValueError("Guide settings must be strings")
        values[key] = value.strip()
    for key in ("web_url", "pdf_url"):
        if values[key] and not values[key].startswith(("https://", "http://")):
            raise ValueError("Guide links must use HTTP or HTTPS")
    match = (
        settings["guide_answer_match"]
        if settings.get("configuration_source") == "database"
        else settings.get("guide_answer_match", GUIDE_DEFAULTS["answer_match"])
    )
    if match not in ("contains", "exact"):
        raise ValueError("guide_answer_match must be contains or exact")
    return GuideContent(**values, answer_match=match)


async def post_guide_announcement(bot, interaction):
    content = bot.guide_content
    if not content.configured:
        await interaction.response.send_message(
            "Season 10 guide content is awaiting operator configuration. Contact an OP.",
            ephemeral=True,
        )
        return
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "Use this command in a server channel.", ephemeral=True
        )
        return
    command_channel = f"<#{bot.settings['bot_spam_channel_coastal']}>"
    message = (
        "@everyone, Ahoy there mateys! After much time on the harsh seas, "
        "we have finally found a welcoming shore: **"
        + bot.settings.get("realm_name", REALM_NAME)
        + "**! "
        "Before stepping onto these new lands, every sailor must read and agree to the Season 10 guide, and fill out the Coastal Application */applycoastal*. "
        "Take your time, as there are new and amended rules to learn!\n\n"
        f"Please head to {command_channel} and use **/guide**.\n\n"
        "I will DM you the guide, ask you a question, and then ask whether you agree to the rules. "
        "Answer correctly and agree to the guide to receive your Season 10 guide and active player roles. "
        "Make sure your DMs are open!\n\n"
        "The full guide can also be found here:\n\n"
    )
    if content.web_url:
        message += f"**Online version of the guide**\n{content.web_url}\n\n"
    if content.pdf_url:
        message += f"**PDF version of the guide**\n{content.pdf_url}\n\n"
    message += "Thank you for sailing with us. Let's have some fun in Season 10!"
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await interaction.channel.send(
            message,
            allowed_mentions=discord.AllowedMentions(
                everyone=True, roles=False, users=False
            ),
        )
    except discord.HTTPException:
        await interaction.followup.send(
            "I couldn't post the announcement. Check my channel permissions and try again.",
            ephemeral=True,
        )
        return
    await interaction.followup.send(
        "Season 10 guide announcement posted.", ephemeral=True
    )


async def run_guide(cog, interaction):
    bot = cog.bot
    if not bot.guide_content.configured:
        await interaction.response.send_message(
            "Season 10 guide content is awaiting operator configuration. Contact an OP.",
            ephemeral=True,
        )
        return
    guild = bot.get_guild(bot.settings["Coastal"])
    role = guild.get_role(bot.settings["CoastalGuideRole"]) if guild else None
    active = guild.get_role(bot.settings["CoastalActiveRole"]) if guild else None
    responsechannel = (
        guild.get_channel(bot.settings["CoastalGuideResponses"]) if guild else None
    )
    author = guild.get_member(interaction.user.id) if guild else None
    if not all((role, active, responsechannel, author)):
        await interaction.response.send_message(
            "Coastal guide roles, channel or member unavailable.", ephemeral=True
        )
        return
    if author.id in cog.sessions:
        await interaction.response.send_message(
            "Finish your current guide first.", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    cog.sessions.add(author.id)
    try:
        channel = await interaction.user.create_dm()
        await interaction.followup.send("Check your DMs", ephemeral=True)
        await converse(bot, channel, author, role, active, responsechannel)
    except discord.HTTPException:
        await interaction.followup.send(
            "Guide delivery or role assignment failed. Contact an OP.", ephemeral=True
        )
    finally:
        cog.sessions.discard(author.id)


async def converse(bot, channel, author, role, realmactiverole, responsechannel):
    def check(message):
        return (
            message.content is not None
            and message.channel == channel
            and message.author.id == author.id
        )

    content = bot.guide_content
    if not content.configured:
        raise ValueError("Season 10 guide is not configured")
    embed = discord.Embed(
        title="Season 10 Guide Agreement",
        description="Read the guide, and then answer the questions that follow.",
        color=0x336F75,
    )
    if content.web_url:
        embed.add_field(
            name="Online version of the guide", value=content.web_url, inline=False
        )
    if content.pdf_url:
        embed.add_field(
            name="PDF version of the guide", value=content.pdf_url, inline=False
        )
    embed.set_thumbnail(url=bot.settings.get("logo_url"))
    await channel.send(embed=embed)
    await channel.send(content.question)
    try:
        while True:
            answer = await bot.wait_for("message", timeout=60.0, check=check)
            if content.accepts(answer.content):
                await channel.send("Great Job!!!")
                break
            await channel.send("Wrong! Try again: ")
        await channel.send("Do you agree to the guide? Please answer yes or no.")
        answer = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await channel.send("I grow tired of waiting, try again later...")
        return
    if answer.content.strip().casefold() == "yes":
        await author.add_roles(role)
        await author.add_roles(realmactiverole)
        await channel.send(
            f"Great! Have fun Playing {bot.settings.get('realm_name', REALM_NAME)}"
        )
        embed = discord.Embed(
            title="Season 10 Guide Agreement",
            description=author.name + " has agreed to the season 10 guide!",
            color=0x000800,
        )
        embed.set_thumbnail(url=bot.settings.get("logo_url"))
        await responsechannel.send(embed=embed)
    else:
        await channel.send("Please get with an OP to discuss your concerns")
