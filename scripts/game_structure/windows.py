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


class UpdateAvailablePopup(UIWindow):
    def __init__(self, show_checkbox: bool = False):
        super().__init__(
            ui_scale(pygame.Rect((200, 200), (400, 230))),
            window_display_title="Update available",
            object_id="#game_over_window",
            resizable=False,
        )
        self.set_blocking(True)

        self.begin_update_title = UIImageButton(
            ui_scale(pygame.Rect((97, 15), (200, 40))),
            "",
            object_id="#new_update_button",
            container=self,
        )

        latest_version_number = "{:.16}".format(get_latest_version_number())
        current_version_number = "{:.16}".format(get_version_info().version_number)

        self.game_over_message = UITextBoxTweaked(
            "update_available",
            ui_scale(pygame.Rect((10, 80), (400, -1))),
            line_spacing=0.8,
            object_id="#update_popup_title",
            container=self,
            text_kwargs={"latest_version_number": latest_version_number},
        )

        self.game_over_message = UITextBoxTweaked(
            "windows.current_version",
            ui_scale(pygame.Rect((11, 100), (400, -1))),
            line_spacing=0.8,
            object_id="#current_version",
            container=self,
            text_kwargs={"ver": current_version_number},
        )

        self.game_over_message = UITextBoxTweaked(
            "windows.install_update",
            ui_scale(pygame.Rect((10, 131), (200, -1))),
            line_spacing=0.8,
            object_id="#text_box_30",
            container=self,
        )

        self.box_unchecked = UIImageButton(
            ui_scale(pygame.Rect((7, 183), (34, 34))),
            "",
            object_id="@unchecked_checkbox",
            container=self,
        )
        self.box_checked = UIImageButton(
            ui_scale(pygame.Rect((7, 183), (34, 34))),
            "",
            object_id="@checked_checkbox",
            container=self,
        )
        self.box_text = UITextBoxTweaked(
            "windows.dont_ask_again",
            ui_scale(pygame.Rect((39, 190), (125, -1))),
            line_spacing=0.8,
            object_id="#text_box_30",
            container=self,
        )

        self.continue_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((278, 185), (102, 30))),
            "buttons.continue",
            get_button_dict(ButtonStyles.SQUOVAL, (77, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
        )

        self.cancel_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((187, 185), (78, 30))),
            "buttons.cancel",
            get_button_dict(ButtonStyles.SQUOVAL, (77, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
        )

        self.close_button = UIImageButton(
            ui_scale(pygame.Rect((740, 10), (44, 44))),
            "",
            object_id="#exit_window_button",
            container=self,
        )

        if show_checkbox:
            self.box_unchecked.enable()
            self.box_checked.hide()
        else:
            self.box_checked.hide()
            self.box_unchecked.hide()
            self.box_text.hide()

        self.continue_button.enable()
        self.cancel_button.enable()
        self.close_button.enable()

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.continue_button:
                self.x = UpdateWindow(
                    switch_get_value(Switch.cur_screen), self.announce_restart_callback
                )
                self.kill()
            elif (
                event.ui_element == self.close_button
                or event.ui_element == self.cancel_button
            ):
                self.kill()
            elif event.ui_element == self.box_unchecked:
                self.box_unchecked.disable()
                self.box_unchecked.hide()
                self.box_checked.enable()
                self.box_checked.show()
                with open(
                    f"{get_cache_dir()}/suppress_update_popup", "w", encoding="utf-8"
                ) as write_file:
                    write_file.write(get_latest_version_number())
            elif event.ui_element == self.box_checked:
                self.box_checked.disable()
                self.box_checked.hide()
                self.box_unchecked.enable()
                self.box_unchecked.show()
                if os.path.exists(f"{get_cache_dir()}/suppress_update_popup"):
                    os.remove(f"{get_cache_dir()}/suppress_update_popup")
        return super().process_event(event)

    def announce_restart_callback(self):
        self.x.kill()
        y = AnnounceRestart(switch_get_value(Switch.cur_screen))
        y.update(1)


class ChangelogPopup(UIWindow):
    def __init__(self):
        super().__init__(
            ui_scale(pygame.Rect((150, 150), (500, 400))),
            window_display_title="Changelog",
            object_id="#game_over_window",
            resizable=False,
        )
        self.set_blocking(True)

        self.changelog_popup_title = UITextBoxTweaked(
            "windows.whats_new",
            ui_scale(pygame.Rect((0, 10), (500, -1))),
            line_spacing=1,
            object_id="#changelog_popup_title",
            container=self,
            anchors={"centerx": "centerx"},
        )

        current_version_number = "{:.16}".format(get_version_info().version_number)

        self.changelog_popup_subtitle = UITextBoxTweaked(
            "windows.version_title",
            ui_scale(pygame.Rect((0, 35), (500, -1))),
            line_spacing=1,
            object_id="#changelog_popup_subtitle",
            container=self,
            anchors={"centerx": "centerx"},
            text_kwargs={"ver": current_version_number},
        )

        dynamic_changelog = False
        if (
            get_version_info().is_dev()
            and get_version_info().is_source_build
            and get_version_info().git_installed
        ):
            file_cont = subprocess.check_output(
                [
                    "git",
                    "log",
                    r"--pretty=format:%H|||%cd|||%b|||%s",
                    "-15",
                    "--no-decorate",
                    "--merges",
                    "--grep=Merge pull request",
                    "--date=short",
                ]
            ).decode("utf-8")
            dynamic_changelog = True
        else:
            with open("changelog.txt", "r", encoding="utf-8") as read_file:
                file_cont = read_file.read()

        if get_version_info().is_dev() and not get_version_info().is_source_build:
            dynamic_changelog = True

        if dynamic_changelog:
            commits = file_cont.splitlines()
            file_cont = ""
            for line in commits:
                info = line.split("|||")

                if len(info) < 4:
                    continue

                # Get PR number so we can link the PR
                pr_number = re_search(r"Merge pull request #([0-9]*?) ", info[3])
                if pr_number:
                    # For some reason, multi-line links on pygame_gui's text boxes don't work very well.
                    # So, to work around that, just add a little "link" at the end
                    info[
                        2
                    ] += f" <a href='https://github.com/ClanGenOfficial/clangen/pull/{pr_number.group(1)}'>(link)</a>"

                # Format: DATE- \n PR Title (link)
                file_cont += f"<b>{info[1]}</b>\n- {info[2]}\n"

        self.changelog_text = UITextBoxTweaked(
            file_cont,
            ui_scale(pygame.Rect((10, 65), (480, 325))),
            object_id="#text_box_30",
            line_spacing=0.95,
            starting_height=2,
            container=self,
            manager=MANAGER,
        )

        self.close_button = UIImageButton(
            ui_scale(pygame.Rect((470, 5), (22, 22))),
            "",
            object_id="#exit_window_button",
            starting_height=2,
            container=self,
        )

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.close_button:
                self.kill()
        return super().process_event(event)


class RelationshipLog(UIWindow):
    """This window allows the user to see the relationship log of a certain relationship."""

    def __init__(self, relationship, disable_button_list, hide_button_list):
        super().__init__(
            ui_scale(pygame.Rect((273, 122), (505, 550))),
            window_display_title="Relationship Log",
            object_id="#relationship_log_window",
            resizable=False,
        )
        self.hide_button_list = hide_button_list
        for button in self.hide_button_list:
            button.hide()

        self.exit_button = UIImageButton(
            ui_scale(pygame.Rect((470, 7), (22, 22))),
            "",
            object_id="#exit_window_button",
            container=self,
        )
        self.back_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((25, 645), (105, 30))),
            "buttons.back",
            get_button_dict(ButtonStyles.SQUOVAL, (105, 30)),
            object_id="@buttonstyles_squoval",
        )
        self.log_icon = UISurfaceImageButton(
            ui_scale(pygame.Rect((222, 404), (34, 34))),
            Icon.NOTEPAD,
            get_button_dict(ButtonStyles.ICON, (34, 34)),
            object_id="@buttonstyles_icon",
        )
        self.closing_buttons = [self.exit_button, self.back_button, self.log_icon]

        self.disable_button_list = []
        for button in disable_button_list:
            if button.is_enabled:
                self.disable_button_list.append(button)
                button.disable()

        opposite_log_string = None
        if not relationship.opposite_relationship:
            relationship.link_relationship()
        if (
            relationship.opposite_relationship
            and len(relationship.opposite_relationship.log) > 0
        ):
            opposite_log = relationship.opposite_relationship.log.copy()
            opposite_log.reverse()
            opposite_log_string = (
                f"{f'<br>-----------------------------<br>'.join(opposite_log)}<br>"
            )

        log = relationship.log.copy()
        log.reverse()
        log_string = (
            f"{f'<br>-----------------------------<br>'.join(log)}<br>"
            if len(relationship.log) > 0
            else i18n.t("windows.no_relation_logs")
        )

        if not opposite_log_string:
            self.log = pygame_gui.elements.UITextBox(
                log_string,
                ui_scale(pygame.Rect((15, 45), (476, 425))),
                object_id="#text_box_30_horizleft",
                manager=MANAGER,
                container=self,
            )
        else:
            self.log = pygame_gui.elements.UITextBox(
                log_string,
                ui_scale(pygame.Rect((15, 45), (476, 250))),
                object_id="#text_box_30_horizleft",
                manager=MANAGER,
                container=self,
            )
            self.opp_heading = pygame_gui.elements.UITextBox(
                "windows.other_perspective",
                ui_scale(pygame.Rect((15, 275), (-1, -1))),
                object_id="#text_box_30_horizleft",
                manager=MANAGER,
                container=self,
            )
            self.opp_heading.disable()
            self.opp_log = pygame_gui.elements.UITextBox(
                opposite_log_string,
                ui_scale(pygame.Rect((15, 305), (476, 232))),
                object_id="#text_box_30_horizleft",
                manager=MANAGER,
                container=self,
            )

    def closing_process(self):
        """Handles to enable and kill all processes when an exit button is clicked."""
        for button in self.disable_button_list:
            button.enable()

        for button in self.hide_button_list:
            button.show()
            button.enable()
        self.log_icon.kill()
        self.exit_button.kill()
        self.back_button.kill()
        self.kill()

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element in self.closing_buttons:
                self.closing_process()
        return super().process_event(event)


class SaveError(UIWindow):
    def __init__(self, error_text):
        super().__init__(
            ui_scale(pygame.Rect((150, 150), (500, 400))),
            window_display_title="Changelog",
            object_id="#game_over_window",
            resizable=False,
        )
        self.set_blocking(True)
        self.changelog_popup_title = pygame_gui.elements.UITextBox(
            "windows.save_failed_title",
            ui_scale(pygame.Rect((20, 10), (445, 375))),
            object_id="#text_box_30",
            container=self,
            text_kwargs={"error": error_text},
        )

        self.close_button = UIImageButton(
            ui_scale(pygame.Rect((470, 5), (22, 22))),
            "",
            object_id="#exit_window_button",
            starting_height=2,
            container=self,
        )

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.close_button:
                self.kill()
        return super().process_event(event)


class SaveAsImage(UIWindow):
    def __init__(self, image_to_save, file_name):
        super().__init__(
            ui_scale(pygame.Rect((200, 175), (400, 250))),
            object_id="#game_over_window",
            resizable=False,
        )

        self.set_blocking(True)

        self.image_to_save = image_to_save
        self.file_name = file_name
        self.scale_factor = 1

        button_layout_rect = ui_scale(pygame.Rect((0, 5), (22, 22)))
        button_layout_rect.topright = ui_scale_offset((-1, 5))

        self.close_button = UIImageButton(
            button_layout_rect,
            "",
            object_id="#exit_window_button",
            starting_height=2,
            container=self,
            anchors={"right": "right", "top": "top"},
        )

        self.save_as_image = UISurfaceImageButton(
            ui_scale(pygame.Rect((0, 90), (135, 30))),
            "screens.sprite_inspect.save_image",
            get_button_dict(ButtonStyles.SQUOVAL, (135, 30)),
            object_id="@buttonstyles_squoval",
            sound_id="save",
            container=self,
            anchors={"centerx": "centerx"},
        )

        self.open_data_directory_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((0, 175), (178, 30))),
            "buttons.open_data_directory",
            get_button_dict(ButtonStyles.SQUOVAL, (178, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
            starting_height=2,
            tool_tip_text="buttons.open_data_directory_tooltip",
            anchors={"centerx": "centerx"},
        )

        self.small_size_button = UIImageButton(
            ui_scale(pygame.Rect((54, 50), (97, 30))),
            "",
            object_id="#image_small_button",
            container=self,
            starting_height=2,
        )
        self.small_size_button.disable()

        self.medium_size_button = UIImageButton(
            ui_scale(pygame.Rect((151, 50), (97, 30))),
            "",
            object_id="#image_medium_button",
            container=self,
            starting_height=2,
        )

        self.large_size_button = UIImageButton(
            ui_scale(pygame.Rect((248, 50), (97, 30))),
            "",
            object_id="#image_large_button",
            container=self,
            starting_height=2,
        )

        self.confirm_text = pygame_gui.elements.UITextBox(
            "",
            ui_scale(pygame.Rect((5, 125), (390, 45))),
            object_id="#text_box_26_horizcenter_vertcenter_spacing_95",
            container=self,
            starting_height=2,
        )

    def save_image(self):
        file_name = self.file_name
        file_number = ""
        i = 0
        while True:
            if os.path.isfile(
                f"{get_saved_images_dir()}/{file_name + file_number}.png"
            ):
                i += 1
                file_number = f"_{i}"
            else:
                break

        scaled_image = pygame.transform.scale_by(self.image_to_save, self.scale_factor)
        pygame.image.save(
            scaled_image, f"{get_saved_images_dir()}/{file_name + file_number}.png"
        )
        return f"{file_name + file_number}.png"

    def process_event(self, event) -> bool:
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.close_button:
                self.kill()
            elif event.ui_element == self.open_data_directory_button:
                open_data_dir()
                return True
            elif event.ui_element == self.save_as_image:
                file_name = self.save_image()
                self.confirm_text.set_text(
                    "windows.confirm_saved_image", text_kwargs={"file_name": file_name}
                )
            elif event.ui_element == self.small_size_button:
                self.scale_factor = 1
                self.small_size_button.disable()
                self.medium_size_button.enable()
                self.large_size_button.enable()
            elif event.ui_element == self.medium_size_button:
                self.scale_factor = 4
                self.small_size_button.enable()
                self.medium_size_button.disable()
                self.large_size_button.enable()
            elif event.ui_element == self.large_size_button:
                self.scale_factor = 6
                self.small_size_button.enable()
                self.medium_size_button.enable()
                self.large_size_button.disable()

        return super().process_event(event)


class EventLoading(UIWindow):
    """Handles the event loading animation"""

    def __init__(self, pos):
        if pos is None:
            pos = (350, 300)

        super().__init__(
            ui_scale(pygame.Rect(pos, (100, 100))),
            window_display_title="Game Over",
            object_id="#loading_window",
            resizable=False,
        )

        self.set_blocking(True)

        self.frames = self.load_images()
        self.end_animation = False

        self.animated_image = pygame_gui.elements.UIImage(
            ui_scale(pygame.Rect(0, 0, 100, 100)),
            self.frames[0],
            container=self,
        )

        self.animation_thread = threading.Thread(target=self.animate)
        self.animation_thread.start()

    @staticmethod
    def load_images():
        frames = []
        for i in range(0, 16):
            frames.append(
                pygame.image.load(f"resources/images/loading_animate/timeskip/{i}.png")
            )

        return frames

    def animate(self):
        """Loops over the event frames and displays the animation"""
        i = 0
        while not self.end_animation:
            i = (i + 1) % (len(self.frames))

            self.animated_image.set_image(self.frames[i])
            time.sleep(0.125)

    def kill(self):
        self.end_animation = True
        super().kill()


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
