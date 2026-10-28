from . import __bm_commands as command_module


async def setup(bot):
    await command_module.setup(bot)
