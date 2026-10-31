import asyncio
from discord import app_commands
from discord.ext import commands
from utils.database.__database import is_administrator


async def predicate_LV3(ctx):
    return await asyncio.to_thread(is_administrator, ctx.author.id, 3)


is_botAdmin3 = commands.check(predicate_LV3)


async def require_op_team(interaction):
    role = interaction.client.settings.get("OPTeamRole", "OP Team")
    roles = getattr(interaction.user, "roles", [])
    if not any((r.id == role if isinstance(role, int) else r.name == role) for r in roles):
        raise app_commands.MissingRole(role)
    return True


def op_team():
    return app_commands.check(require_op_team)
