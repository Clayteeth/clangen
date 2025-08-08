import os
import shutil
import subprocess
import threading
import time
from collections import namedtuple
from platform import system
from random import choice
from re import search as re_search
from re import sub
from typing import TYPE_CHECKING

import i18n
import pygame
import pygame_gui
import ujson
from pygame_gui.elements import UIWindow
from pygame_gui.windows import UIMessageWindow

from scripts.cat.cats import Cat
from scripts.cat.history import History
from scripts.cat.names import Name
from scripts.cat.save_load import save_cats
from scripts.game_structure import image_cache
from scripts.game_structure.game.switches import (
    Switch,
    switch_get_value,
    switch_set_value,
    switch_append_list_value,
    switch_remove_list_value,
)
from scripts.game_structure.game_essentials import game
from scripts.game_structure.localization import (
    get_lang_config,
    get_custom_pronouns,
    add_custom_pronouns,
)
from scripts.game_structure.screen_settings import MANAGER
from scripts.game_structure.ui_elements import (
    UIImageButton,
    UITextBoxTweaked,
    UISurfaceImageButton,
    UIDropDown,
    UIModifiedScrollingContainer,
)
from scripts.housekeeping.datadir import (
    get_save_dir,
    get_cache_dir,
    get_saved_images_dir,
    open_data_dir,
)
from scripts.housekeeping.progress_bar_updater import UIUpdateProgressBar
from scripts.housekeeping.update import (
    self_update,
    UpdateChannel,
    get_latest_version_number,
)
from scripts.housekeeping.version import get_version_info
from scripts.screens.enums import GameScreen
from scripts.ui.generate_box import BoxStyles, get_box
from scripts.ui.generate_button import ButtonStyles, get_button_dict
from scripts.ui.icon import Icon
from scripts.utility import (
    ui_scale,
    quit,
    update_sprite,
    logger,
    process_text,
    ui_scale_dimensions,
    ui_scale_offset,
    shorten_text_to_fit,
)

if TYPE_CHECKING:
    from scripts.screens.Screens import Screens




class ConfirmDisplayChanges(UIMessageWindow):
    def __init__(self, source_screen: "Screens"):
        super().__init__(
            ui_scale(pygame.Rect((275, 270), (250, 160))),
            "This is a test!",
            MANAGER,
            object_id="#confirm_display_changes_window",
            always_on_top=True,
        )
        self.set_blocking(True)

        self.dismiss_button.kill()
        self.text_block.kill()

        button_size = (-1, 30)
        button_spacing = 10
        button_vertical_space = (button_spacing * 2) + button_size[1]

        dismiss_button_rect = ui_scale(pygame.Rect((0, 0), (140, 30)))
        dismiss_button_rect.bottomright = ui_scale_offset(
            (-button_spacing, -button_spacing)
        )

        self.dismiss_button = UISurfaceImageButton(
            dismiss_button_rect,
            "windows.confirm_changes",
            get_button_dict(ButtonStyles.SQUOVAL, (140, 30)),
            MANAGER,
            container=self,
            object_id="@buttonstyles_squoval",
            anchors={
                "left": "right",
                "top": "bottom",
                "right": "right",
                "bottom": "bottom",
            },
        )

        revert_rect = ui_scale(pygame.Rect((0, 0), (75, 30)))
        revert_rect.bottomleft = ui_scale_offset((button_spacing, -button_spacing))

        self.revert_button = UISurfaceImageButton(
            revert_rect,
            "windows.revert",
            get_button_dict(ButtonStyles.SQUOVAL, (75, 30)),
            MANAGER,
            container=self,
            object_id="@buttonstyles_squoval",
            anchors={
                "left": "left",
                "bottom": "bottom",
            },
        )

        rect = ui_scale(pygame.Rect((0, 0), (22, 22)))
        rect.topright = ui_scale_offset((-5, 7))
        self.back_button = UIImageButton(
            rect,
            "",
            object_id="#exit_window_button",
            container=self,
            visible=True,
            anchors={"top": "top", "right": "right"},
        )

        text_block_rect = pygame.Rect(
            ui_scale_offset((0, 22)),
            (
                self.get_container().get_size()[0],
                -1,
            ),
        )
        self.text_block = pygame_gui.elements.UITextBox(
            "windows.display_change_confirm",
            text_block_rect,
            manager=MANAGER,
            object_id="#text_box_30_horizcenter",
            container=self,
            anchors={
                "left": "left",
                "top": "top",
                "right": "right",
                "bottom": "bottom",
            },
            text_kwargs={"count": 10},
        )
        self.text_block.disable()
        self.text_block.rebuild_from_changed_theme_data()

        # make a timeout that will call in 10 seconds - if this window isn't closed,
        # it'll be used to revert the change
        pygame.time.set_timer(pygame.USEREVENT + 10, 10000, loops=1)

        self.source_screen_name = source_screen.name.replace(" ", "_")

    def revert_changes(self):
        """Revert the changes made to screen scaling"""
        from scripts.game_structure.screen_settings import toggle_fullscreen
        from scripts.screens.all_screens import AllScreens

        toggle_fullscreen(
            None,
            source_screen=getattr(AllScreens, self.source_screen_name),
            show_confirm_dialog=False,
        )

    def process_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if (
                event.ui_element == self.back_button
                or event.ui_element == self.dismiss_button
            ):
                self.kill()
            elif event.ui_element == self.revert_button:
                self.revert_changes()
        elif event.type == pygame.USEREVENT + 10:
            self.revert_changes()
            self.kill()
        return super().process_event(event)
