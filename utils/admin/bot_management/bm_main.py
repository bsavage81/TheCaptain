from . import __bm_commands as command_module
from . import posts


async def setup(bot):
    await command_module.setup(bot)
    await posts.setup(bot)
