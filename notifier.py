"""
Notification Management Module
Handles user notifications with Windows-style compact design in notification area.
Fixed for proper threading.
"""

import tkinter as tk
from tkinter import messagebox, ttk
import logging
import json
from datetime import datetime
import threading
import time
from pathlib import Path

# Define the base directory of the script to make paths absolute
BASE_DIR = Path(__file__).resolve().parent

class NotificationManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.config = self._load_config()
        self.busy_delay_options = self.config.get('settings', {}).get('busy_delay_options', [10, 15, 30])
        self.auto_close_seconds = self.config.get('settings', {}).get('auto_close_seconds', 45)

    def _load_config(self):
        """Load settings from config file"""
        try:
            with open(BASE_DIR / 'reminder_config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load notification settings: {e}")
            return {}

    def show_reminder(self, reminder_type, message):
        """Show a reminder notification and get user response"""
        try:
            response = self._show_windows_style_notification(reminder_type, message)
            return response
        except Exception as e:
            logging.error(f"Error showing reminder notification: {e}")
            return {'action': 'skip', 'delay_minutes': 0}

    def _show_windows_style_notification(self, reminder_type, message):
        """Show compact Windows-style notification in corner"""
        response = {'action': 'skip', 'delay_minutes': 0}
        
        dialog = tk.Toplevel()
        
        def on_ok():
            response['action'] = 'ok'
            dialog.destroy()
        
        def on_busy():
            delay = self._show_compact_delay_dialog(dialog)
            if delay > 0:
                response['action'] = 'busy'
                response['delay_minutes'] = delay
            dialog.destroy()
        
        def on_skip():
            response['action'] = 'skip'
            dialog.destroy()

        dialog.title("")
        dialog.geometry("320x140")
        dialog.resizable(False, False)
        dialog.overrideredirect(True)
        
        try:
            dialog.attributes('-alpha', 0.98)
            dialog.attributes('-topmost', True)
        except tk.TclError:
            pass 
        
        self._position_notification_area(dialog)
        
        # --- Calming UI Theme ---
        canvas = tk.Canvas(dialog, highlightthickness=0, bg="#E8F5E8") # Sage green background
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Gentle shadow effect by drawing a slightly larger, darker rectangle underneath
        self._create_rounded_rectangle(canvas, 4, 4, 316, 136, radius=12, fill="#D5DBDB")
        
        # Main white content card
        bg_color = "#FFFFFF"
        self._create_rounded_rectangle(canvas, 2, 2, 318, 138, radius=10, fill=bg_color)

        content_frame = tk.Frame(canvas, bg=bg_color)
        content_frame.place(x=10, y=10, width=300, height=120)

        header_frame = tk.Frame(content_frame, bg=bg_color, height=25)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_frame.pack_propagate(False)
        
        app_label = tk.Label(
            header_frame, text="Wellness Reminder", font=('Segoe UI', 9, 'bold'),
            fg='#2D3748', bg=bg_color # Dark charcoal text
        )
        app_label.pack(side=tk.LEFT)
        
        close_btn = tk.Button(
            header_frame, text="×", font=('Segoe UI', 12, 'bold'), fg='#718096', bg=bg_color, # Medium gray text
            bd=0, highlightthickness=0, activebackground='#E57373', activeforeground='white',
            cursor='hand2', command=dialog.destroy
        )
        close_btn.pack(side=tk.RIGHT)
        
        message_frame = tk.Frame(content_frame, bg=bg_color)
        message_frame.pack(fill=tk.X, pady=(0, 8))
        
        icon_map = {'water': '💧', 'eye_rest': '👁️', 'stretch': '🧘', 'lunch': '🍽️', 'end_day': '🌅'}
        icon = icon_map.get(reminder_type, '🔔')
        clean_message = message.lstrip(icon + " ").strip()
        
        icon_label = tk.Label(message_frame, text=icon, font=('Segoe UI Emoji', 18), bg=bg_color)
        icon_label.grid(row=0, column=0, sticky='n', padx=(0, 10))
        
        message_label = tk.Label(
            message_frame, text=clean_message, font=('Segoe UI', 10), fg='#2D3748', bg=bg_color,
            wraplength=240, justify='left'
        )
        message_label.grid(row=0, column=1, sticky='w')
        message_frame.grid_columnconfigure(1, weight=1)
        
        self._create_task_specific_buttons(content_frame, reminder_type, on_ok, on_busy, on_skip)
        
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_skip())
        
        auto_close_timer = threading.Timer(self.auto_close_seconds, lambda: dialog.destroy() if dialog.winfo_exists() else None)
        auto_close_timer.daemon = True
        auto_close_timer.start()
        
        self._animate_slide_in(dialog)
        dialog.wait_window()
        
        auto_close_timer.cancel()
        
        return response

    def _create_task_specific_buttons(self, parent, reminder_type, on_ok, on_busy, on_skip):
        button_frame = tk.Frame(parent, bg=parent.cget('bg'))
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5,0))
        
        button_configs = {
            'water': [('✓ Drank', on_ok, '#20B2AA'), ('Later', on_busy, '#B0BEC5'), ('Skip', on_skip, '#CFD8DC')],
            'eye_rest': [('✓ Rested', on_ok, '#20B2AA'), ('Busy', on_busy, '#B0BEC5'), ('Skip', on_skip, '#CFD8DC')],
            'stretch': [('✓ Stretched', on_ok, '#20B2AA'), ('Later', on_busy, '#B0BEC5'), ('Skip', on_skip, '#CFD8DC')],
            'lunch': [('✓ Eating', on_ok, '#20B2AA'), ('In 15min', lambda: on_busy(15), '#B0BEC5'), ('Skip', on_skip, '#CFD8DC')],
            'end_day': [('✓ Done', on_ok, '#20B2AA'), ('15 more min', lambda: on_busy(15), '#B0BEC5')]
        }
        
        buttons = button_configs.get(reminder_type, button_configs['water'])
        
        for i, (text, command, bg_color) in enumerate(buttons):
            btn = self._create_modern_button(button_frame, text, command, bg_color)
            btn.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)

    @staticmethod
    def _create_modern_button(parent, text, command, bg_color):
        hover_color = NotificationManager._darken_color(bg_color)
        text_color = "#FFFFFF" if bg_color == "#20B2AA" else "#2D3748"
        btn = tk.Button(
            parent, text=text, font=('Segoe UI', 9, 'bold'), fg=text_color, bg=bg_color,
            activebackground=hover_color, activeforeground=text_color, bd=0, highlightthickness=0,
            cursor='hand2', command=command, relief='flat', pady=5
        )
        
        def on_enter(e, color=hover_color): btn.configure(bg=color)
        def on_leave(e, color=bg_color): btn.configure(bg=color)
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        return btn

    def _position_notification_area(self, window):
        try:
            window.update_idletasks()
            width, height = window.winfo_width(), window.winfo_height()
            screen_width, screen_height = window.winfo_screenwidth(), window.winfo_screenheight()
            x = screen_width - width - 20
            y = screen_height - height - 60
            window.geometry(f'{width}x{height}+{x}+{y}')
        except Exception as e:
            logging.warning(f"Could not position window: {e}")

    def _animate_slide_in(self, window):
        try:
            window.update_idletasks()
            start_x, end_x, current_y = window.winfo_screenwidth(), window.winfo_x(), window.winfo_y()
            steps = 15
            for i in range(steps + 1):
                progress = 1 - (1 - (i / steps)) ** 3
                current_x = int(start_x + (end_x - start_x) * progress)
                window.geometry(f'+{current_x}+{current_y}')
                window.update()
                time.sleep(0.015)
        except Exception as e:
            logging.warning(f"Animation failed: {e}")

    def _show_compact_delay_dialog(self, parent):
        delay_minutes = 0
        delay_dialog = tk.Toplevel(parent)
        
        def on_delay_select(minutes):
            nonlocal delay_minutes
            delay_minutes = minutes
            delay_dialog.destroy()
        
        delay_dialog.title("")
        delay_dialog.geometry("280x120")
        delay_dialog.resizable(False, False)
        delay_dialog.overrideredirect(True)
        delay_dialog.configure(bg='#FFFFFF')
        
        try:
            delay_dialog.attributes('-alpha', 0.98)
            delay_dialog.attributes('-topmost', True)
        except:
            pass
            
        self._center_on_parent(delay_dialog, parent)
        
        tk.Label(
            delay_dialog, text="⏰ Remind me in:", font=('Segoe UI', 11, 'bold'),
            fg='#2D3748', bg='#FFFFFF'
        ).pack(pady=(10, 8))
        
        buttons_frame = tk.Frame(delay_dialog, bg='#FFFFFF')
        buttons_frame.pack(pady=(0, 10))
        
        colors = ['#A3E4D7', '#D7BDE2', '#FAD7A0']
        for i, minutes in enumerate(self.busy_delay_options):
            btn = self._create_modern_button(
                buttons_frame, f"{minutes} min", lambda m=minutes: on_delay_select(m),
                colors[i % len(colors)]
            )
            btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        delay_dialog.wait_window()
        return delay_minutes

    def _center_on_parent(self, child, parent):
        try:
            child.update_idletasks()
            parent.update_idletasks()
            child_width, child_height = child.winfo_width(), child.winfo_height()
            parent_x, parent_y = parent.winfo_x(), parent.winfo_y()
            parent_width, parent_height = parent.winfo_width(), parent.winfo_height()
            x = parent_x + (parent_width // 2) - (child_width // 2)
            y = parent_y + (parent_height // 2) - (child_height // 2)
            child.geometry(f'{child_width}x{child_height}+{x}+{y}')
        except Exception as e:
            logging.warning(f"Could not center dialog: {e}")

    @staticmethod
    def _darken_color(color):
        try:
            r, g, b = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            return f'#{max(0, r-20):02x}{max(0, g-20):02x}{max(0, b-20):02x}'
        except:
            return color

    @staticmethod
    def _create_gradient(canvas, x1, y1, x2, y2, color1, color2):
        # This is not used in the new design, but kept for reference
        pass

    @staticmethod
    def _create_rounded_rectangle(canvas, x1, y1, x2, y2, radius=25, **kwargs):
        """Draws a rounded rectangle on the canvas."""
        points = [x1+radius, y1, x2-radius, y1,
                  x2, y1, x2, y1+radius,
                  x2, y2-radius, x2, y2,
                  x2-radius, y2, x1+radius, y2,
                  x1, y2, x1, y2-radius,
                  x1, y1+radius, x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True, splinesteps=8)


class MotivationalDialog:
    @staticmethod
    def show_motivational_message(message):
        is_welcome_message = "running in the background" in message
        if is_welcome_message:
            MotivationalDialog._create_glass_dialog(
                title="🎉 Welcome!",
                message=message,
                button_text="Got It!",
                button_color="#20B2AA",
                title_color="#27AE60"
            )
        else:
            MotivationalDialog._create_glass_dialog(
                title="🌟 A Friendly Nudge",
                message=message,
                button_text="I'll do better",
                button_color="#F6D55C",
                title_color="#D35400"
            )

    @staticmethod
    def _create_glass_dialog(title, message, button_text, button_color, title_color):
        dialog = tk.Toplevel()
        
        def on_understand():
            dialog.destroy()
        
        dialog.title("")
        dialog.geometry("380x200")
        dialog.resizable(False, False)
        dialog.overrideredirect(True)
        
        try:
            dialog.attributes('-alpha', 0.98)
            dialog.attributes('-topmost', True)
        except: pass
            
        MotivationalDialog._position_notification_area(dialog)
        
        canvas = tk.Canvas(dialog, highlightthickness=0, bg="#E8F5E8")
        canvas.pack(fill=tk.BOTH, expand=True)

        bg_color = "#FFFFFF"
        NotificationManager._create_rounded_rectangle(canvas, 4, 4, 376, 196, radius=12, fill="#D5DBDB")
        NotificationManager._create_rounded_rectangle(canvas, 2, 2, 378, 198, radius=10, fill=bg_color)

        content_frame = tk.Frame(canvas, bg=bg_color)
        content_frame.place(x=15, y=15, width=350, height=170)
        
        # Use grid layout for better control within the content frame
        content_frame.grid_rowconfigure(0, weight=1) # Title
        content_frame.grid_rowconfigure(1, weight=3) # Message
        content_frame.grid_rowconfigure(2, weight=1) # Button
        content_frame.grid_columnconfigure(0, weight=1)

        header_frame = tk.Frame(content_frame, bg=bg_color)
        header_frame.grid(row=0, column=0, sticky="ew")
        
        tk.Label(
            header_frame, text=title, font=('Segoe UI', 11, 'bold'),
            fg=title_color, bg=bg_color
        ).pack(side=tk.LEFT)
        
        message_label = tk.Label(
            content_frame, text=message, font=('Segoe UI', 10), fg='#2D3748', bg=bg_color,
            wraplength=340, justify='center'
        )
        message_label.grid(row=1, column=0, sticky="nsew")
        
        button_container = tk.Frame(content_frame, bg=bg_color)
        button_container.grid(row=2, column=0, sticky="s")

        action_btn = NotificationManager._create_modern_button(
            button_container, button_text, on_understand, button_color
        )
        action_btn.pack(pady=(0, 10))
        
        dialog.bind('<Return>', lambda e: on_understand())
        dialog.bind('<Escape>', lambda e: on_understand())
        
        MotivationalDialog._animate_slide_in(dialog)
        
        auto_close_timer = threading.Timer(30, lambda: dialog.destroy() if dialog.winfo_exists() else None)
        auto_close_timer.daemon = True
        auto_close_timer.start()
        
        dialog.wait_window()
        auto_close_timer.cancel()

    @staticmethod
    def _position_notification_area(window):
        NotificationManager._position_notification_area(None, window)

    @staticmethod
    def _animate_slide_in(window):
        NotificationManager._animate_slide_in(None, window)
