"""Explicit configuration loading and shared sync-confirmation button."""
import json
import os
from discord import ButtonStyle, ui
import discord
from types import CoroutineType
from typing import Union, List
from .__constants import ROOT, LEGACY_IDS


def load_settings(path=None, environ=None):
    environ = os.environ if environ is None else environ
    path = ROOT / "botconfig.json" if path is None else path
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    config = {**LEGACY_IDS, **config}
    for key in ("token", "database_ip", "database_port", "database_username", "database_password", "database_schema", "bot_type", "sentry_dsn"):
        if key in environ:
            config[key] = environ[key]
    config.setdefault("bot_type", "STABLE")
    if config["bot_type"] not in ("STABLE", "BETA"):
        raise ValueError("bot_type must be STABLE or BETA")
    required = ("MRP", "PBtest", "Coastal", "CoastalMRP", "CoastalApplications", "CoastalOPTeam", "CoastalMapUpdates")
    for key in required:
        if not isinstance(config.get(key), int) or config[key] <= 0:
            raise ValueError(f"Configure a positive integer for {key}")
    config.setdefault("OPTeamRole", "OP Team")
    config.setdefault("owner_ids", [306070011028439041])
    config["credentials_path"] = str(ROOT / config.get("credentials_path", "creds.json"))
    return config


class Colors:
    red = discord.Color.red()


class ButtonHandler(ui.Button):
    """
    Adds a Button to a specific message and returns it's value when pressed.

    Usage:
        To do something after the callback function is invoked (the button is pressed), you have to pass a
        coroutine to the class. IMPORTANT: The coroutine has to take two arguments (discord.Interaction, discord.View)
        to work.
    """

    def __init__(
            self,
            style: ButtonStyle,
            label: str,
            custom_id: Union[str, None] = None,
            emoji: Union[str, None] = None,
            url: Union[str, None] = None,
            disabled: bool = False,
            button_user: Union[discord.Member, discord.User, None] = None,
            roles: List[discord.Role] = None,
            interaction_message: Union[str, None] = None,
            ephemeral: bool = True,
            coroutine: CoroutineType = None,
            view_response=None,
    ):
        """
        Parameters:
            style: Label for the button
            label: Custom ID that represents this button. Default to None.
            custom_id: Style for this button. Default to None.
            emoji: An emoji for this button. Default to None.
            url: A URL for this button. Default to None.
            disabled: Whenever the button should be disabled or not. Default to False.
            button_user: The user that can perform this action, leave blank for everyone. Defaults to None.
            roles: The roles which the user needs to be able to click the button.
            interaction_message: The response message when pressing on a selection. Default to None.
            ephemeral: Whenever the response message should only be visible for the select_user or not. Default to True.
            coroutine: A coroutine that gets invoked after the button is pressed. If None is passed, the view is stopped after the button is pressed. Default to None.
        """
        self.style_ = style
        self.label_ = label
        self.custom_id_ = custom_id
        self.emoji_ = emoji
        self.url_ = url
        self.disabled_ = disabled
        self.button_user = button_user
        self.roles = roles
        self.interaction_message_ = interaction_message
        self.ephemeral_ = ephemeral
        self.coroutine = coroutine
        self.view_response = view_response

        if self.custom_id_:
            super().__init__(
                style=self.style_,
                label=self.label_,
                custom_id=self.custom_id_,
                emoji=self.emoji_,
                url=self.url_,
                disabled=self.disabled_,
            )
        else:
            super().__init__(
                style=self.style_,
                label=self.label_,
                emoji=self.emoji_,
                url=self.url_,
                disabled=self.disabled_,
            )

    async def callback(self, interaction: discord.Interaction):
        if self.button_user in [None, interaction.user] or any(
                role in interaction.user.roles for role in (self.roles or [])
        ):
            if self.custom_id_ is None:
                self.view.value = self.label_
                self.view_response = self.label_
            else:
                self.view.value = self.custom_id_
                self.view_response = self.custom_id_

            if self.interaction_message_:
                await interaction.response.send_message(
                    content=self.interaction_message_, ephemeral=self.ephemeral_
                )

            if self.coroutine is not None:
                await self.coroutine(interaction, self.view)
            else:
                self.view.stop()
        else:
            await interaction.response.send_message(
                content="You're not allowed to interact with that!", ephemeral=True
            )


