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


class ChangeCatToggles(UIWindow):
    """This window allows the user to edit various cat behavior toggles"""

    def __init__(self, cat):
        super().__init__(
            ui_scale(pygame.Rect((300, 215), (400, 185))),
            window_display_title="Change Cat Name",
            object_id="#change_cat_name_window",
            resizable=False,
        )
        self.the_cat = cat
        self.set_blocking(True)
        self.back_button = UIImageButton(
            ui_scale(pygame.Rect((370, 5), (22, 22))),
            "",
            object_id="#exit_window_button",
            container=self,
        )

        self.checkboxes = {}
        self.refresh_checkboxes()

        # Text
        self.text_1 = pygame_gui.elements.UITextBox(
            "windows.prevent_fading",
            ui_scale(pygame.Rect(55, 25, -1, 32)),
            object_id="#text_box_30_horizleft_pad_0_8",
            container=self,
        )

        self.text_2 = pygame_gui.elements.UITextBox(
            "windows.prevent_kits",
            ui_scale(pygame.Rect(55, 50, -1, 32)),
            object_id="#text_box_30_horizleft_pad_0_8",
            container=self,
        )

        self.text_3 = pygame_gui.elements.UITextBox(
            "windows.prevent_retirement",
            ui_scale(pygame.Rect(55, 75, -1, 32)),
            object_id="#text_box_30_horizleft_pad_0_8",
            container=self,
        )

        self.text_4 = pygame_gui.elements.UITextBox(
            "windows.prevent_romance",
            ui_scale(pygame.Rect(55, 100, -1, 32)),
            object_id="#text_box_30_horizleft_pad_0_8",
            container=self,
        )

        # Text

    def refresh_checkboxes(self):
        for x in self.checkboxes.values():
            x.kill()
        self.checkboxes = {}

        # Prevent Fading
        if self.the_cat == game.clan.instructor:
            box_type = "@checked_checkbox"
            tool_tip = "windows.prevent_fading_tooltip_guide"
        elif self.the_cat.prevent_fading:
            box_type = "@checked_checkbox"
            tool_tip = "windows.prevent_fading_tooltip"
        else:
            box_type = "@unchecked_checkbox"
            tool_tip = "windows.prevent_fading_tooltip"

        # Fading
        self.checkboxes["prevent_fading"] = UIImageButton(
            ui_scale(pygame.Rect((22, 25), (34, 34))),
            "",
            container=self,
            object_id=box_type,
            tool_tip_text=tool_tip,
        )

        if self.the_cat == game.clan.instructor:
            self.checkboxes["prevent_fading"].disable()

        # No Kits
        self.checkboxes["prevent_kits"] = UIImageButton(
            ui_scale(pygame.Rect((22, 50), (34, 34))),
            "",
            container=self,
            object_id=(
                "@checked_checkbox" if self.the_cat.no_kits else "@unchecked_checkbox"
            ),
            tool_tip_text="windows.prevent_kits_tooltip",
        )

        # No Retire
        self.checkboxes["prevent_retire"] = UIImageButton(
            ui_scale(pygame.Rect((22, 75), (34, 34))),
            "",
            container=self,
            object_id=(
                "@checked_checkbox" if self.the_cat.no_retire else "@unchecked_checkbox"
            ),
            tool_tip_text=(
                "windows.prevent_retirement_tooltip_yes"
                if self.the_cat.no_retire
                else "windows.prevent_retirement_tooltip_no"
            ),
        )

        # No mates
        self.checkboxes["prevent_mates"] = UIImageButton(
            ui_scale(pygame.Rect((22, 100), (34, 34))),
            "",
            container=self,
            object_id=(
                "@checked_checkbox" if self.the_cat.no_mates else "@unchecked_checkbox"
            ),
            tool_tip_text="windows.prevent_romance_tooltip",
        )

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.back_button:
                game.all_screens[GameScreen.PROFILE].exit_screen()
                game.all_screens[GameScreen.PROFILE].screen_switches()
                self.kill()
            elif event.ui_element == self.checkboxes["prevent_fading"]:
                self.the_cat.prevent_fading = not self.the_cat.prevent_fading
                self.refresh_checkboxes()
            elif event.ui_element == self.checkboxes["prevent_kits"]:
                self.the_cat.no_kits = not self.the_cat.no_kits
                self.refresh_checkboxes()
            elif event.ui_element == self.checkboxes["prevent_retire"]:
                self.the_cat.no_retire = not self.the_cat.no_retire
                self.refresh_checkboxes()
            elif event.ui_element == self.checkboxes["prevent_mates"]:
                self.the_cat.no_mates = not self.the_cat.no_mates
                self.refresh_checkboxes()

        return super().process_event(event)


class SelectFocusClans(UIWindow):
    """This window allows the user to select the clans to be sabotaged, aided or raided in the focus setting."""

    def __init__(self):
        super().__init__(
            ui_scale(pygame.Rect((250, 120), (300, 225))),
            window_display_title="Change Cat Name",
            object_id="#change_cat_name_window",
            resizable=False,
        )
        self.set_blocking(True)
        self.back_button = UIImageButton(
            ui_scale(pygame.Rect((270, 5), (22, 22))),
            "",
            object_id="#exit_window_button",
            container=self,
        )
        self.save_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((80, 180), (139, 30))),
            "windows.change_focus",
            get_button_dict(ButtonStyles.SQUOVAL, (139, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
        )
        self.save_button.disable()

        self.checkboxes = {}
        self.refresh_checkboxes()

        # Text
        self.texts = {}
        self.texts["prompt"] = pygame_gui.elements.UITextBox(
            "windows.focus_prompt",
            ui_scale(pygame.Rect((0, 5), (300, 30))),
            object_id="#text_box_30_horizcenter",
            container=self,
        )
        n = 0
        for clan in game.clan.all_clans:
            self.texts[clan.name] = pygame_gui.elements.UITextBox(
                clan.name + "clan",
                ui_scale(pygame.Rect(107, n * 27 + 38, -1, 25)),
                object_id="#text_box_30_horizleft_pad_0_8",
                container=self,
            )
            n += 1

    def refresh_checkboxes(self):
        for x in self.checkboxes.values():
            x.kill()
        self.checkboxes = {}

        n = 0
        for clan in game.clan.all_clans:
            box_type = "@unchecked_checkbox"
            if clan.name in game.clan.clans_in_focus:
                box_type = "@checked_checkbox"

            self.checkboxes[clan.name] = UIImageButton(
                ui_scale(pygame.Rect((75, n * 27 + 35), (34, 34))),
                "",
                container=self,
                object_id=box_type,
            )
            n += 1

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.back_button:
                game.clan.clans_in_focus = []
                game.all_screens[GameScreen.WARRIOR_DEN].exit_screen()
                game.all_screens[GameScreen.WARRIOR_DEN].screen_switches()
                self.kill()
            if event.ui_element == self.save_button:
                game.all_screens[GameScreen.WARRIOR_DEN].save_focus()
                game.all_screens[GameScreen.WARRIOR_DEN].exit_screen()
                game.all_screens[GameScreen.WARRIOR_DEN].screen_switches()
                self.kill()
            if event.ui_element in self.checkboxes.values():
                for clan_name, value in self.checkboxes.items():
                    if value == event.ui_element:
                        if value.object_ids[1] == "@unchecked_checkbox":
                            game.clan.clans_in_focus.append(clan_name)
                        if value.object_ids[1] == "@checked_checkbox":
                            game.clan.clans_in_focus.remove(clan_name)
                        self.refresh_checkboxes()
                if len(game.clan.clans_in_focus) < 1 and self.save_button.is_enabled:
                    self.save_button.disable()
                if (
                    len(game.clan.clans_in_focus) >= 1
                    and not self.save_button.is_enabled
                ):
                    self.save_button.enable()

        return super().process_event(event)


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
