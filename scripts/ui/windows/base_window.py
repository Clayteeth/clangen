import pygame
import pygame_gui
from pygame_gui.elements import UIWindow

from scripts.game_structure.ui_elements import UIImageButton
from scripts.utility import ui_scale, ui_scale_offset


class Window(UIWindow):
    """
    Basic window class, this sets blocking, creates an exit button, and handles the exit event
    """
    def __init__(
        self, relative_rect, window_display_title: str = None, object_id: str = None
    ):
        super().__init__(
            relative_rect,
            window_display_title=window_display_title,
            object_id=object_id,
        )

        self.set_blocking(True)

        scale_rect = ui_scale(pygame.Rect((0, 0), (22, 22)))
        scale_rect.topright = ui_scale_offset((-5, 5))
        self.back_button = UIImageButton(
            scale_rect,
            "",
            object_id="#exit_window_button",
            starting_height=10,
            container=self,
        )

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            if event.ui_element == self.back_button:
                self.kill()
