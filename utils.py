"""
Utility Functions Module
Date/time helpers and daily reset management.
"""

import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

# Define the base directory of the script to make paths absolute
BASE_DIR = Path(__file__).resolve().parent

class DateTimeUtils:
    """Utility class for date and time operations"""
    
    @staticmethod
    def get_current_date():
        """Get current date as string"""
        return datetime.now().strftime('%Y-%m-%d')
    
    @staticmethod
    def get_current_time():
        """Get current time as string"""
        return datetime.now().strftime('%H:%M:%S')
    
    @staticmethod
    def get_current_datetime():
        """Get current datetime as ISO string"""
        return datetime.now().isoformat()
    
    @staticmethod
    def parse_time(time_str):
        """Parse time string (HH:MM) to datetime object for today"""
        try:
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            today = datetime.now().date()
            return datetime.combine(today, time_obj)
        except ValueError as e:
            logging.error(f"Error parsing time {time_str}: {e}")
            return None
    
    @staticmethod
    def is_new_day(last_date_str):
        """Check if it's a new day compared to last_date_str"""
        if not last_date_str:
            return True
        
        try:
            last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
            current_date = datetime.now().date()
            return current_date > last_date
        except ValueError:
            return True
    
    @staticmethod
    def time_until_next_occurrence(target_time_str):
        """Calculate time until next occurrence of target time"""
        try:
            target_time = DateTimeUtils.parse_time(target_time_str)
            current_time = datetime.now()
            
            if target_time <= current_time:
                # If target time has passed today, schedule for tomorrow
                target_time += timedelta(days=1)
            
            return target_time - current_time
        except Exception as e:
            logging.error(f"Error calculating time until {target_time_str}: {e}")
            return timedelta(0)
    
    @staticmethod
    def format_duration(duration_seconds):
        """Format duration in seconds to human readable string"""
        if duration_seconds < 60:
            return f"{duration_seconds:.0f} seconds"
        elif duration_seconds < 3600:
            minutes = duration_seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = duration_seconds / 3600
            return f"{hours:.1f} hours"

class DailyResetManager:
    """Manages daily reset operations"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.datetime_utils = DateTimeUtils()
    
    def should_reset(self):
        """Check if daily reset should be performed"""
        try:
            last_reset_date = self.db_manager.get_setting('last_reset_date')
            return self.datetime_utils.is_new_day(last_reset_date)
        except Exception as e:
            logging.error(f"Error checking if reset needed: {e}")
            return False
    
    def perform_daily_reset(self):
        """Perform daily reset operations"""
        try:
            current_date = self.datetime_utils.get_current_date()
            
            logging.info("Starting daily reset...")
            
            # Archive old data before clearing
            self._archive_previous_day_summary()
            
            # Clear today's data (in case of multiple resets)
            self.db_manager.clear_daily_data()
            
            # Archive old data based on retention policy
            self._cleanup_old_data()
            
            # Update last reset date
            self.db_manager.update_settings('last_reset_date', current_date)
            
            logging.info(f"Daily reset completed for {current_date}")
            
        except Exception as e:
            logging.error(f"Error performing daily reset: {e}")
    
    def _archive_previous_day_summary(self):
        """Archive previous day's summary before reset"""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            summary = self.db_manager.get_daily_summary(yesterday)
            
            if summary:
                # Log summary for reference
                logging.info(f"Previous day ({yesterday}) summary: {len(summary)} task types tracked")
                
                for task_summary in summary:
                    task_name = task_summary.get('task_name', 'unknown')
                    total = task_summary.get('total_count', 0)
                    ok_count = task_summary.get('ok_count', 0)
                    skip_count = task_summary.get('skip_count', 0)
                    busy_count = task_summary.get('busy_count', 0)
                    
                    completion_rate = (ok_count / total * 100) if total > 0 else 0
                    
                    logging.info(
                        f"  {task_name}: {total} reminders, "
                        f"{ok_count} completed ({completion_rate:.1f}%), "
                        f"{skip_count} skipped, {busy_count} delayed"
                    )
            
        except Exception as e:
            logging.error(f"Error archiving previous day summary: {e}")
    
    def _cleanup_old_data(self):
        """Clean up old data based on retention policy"""
        try:
            # Load retention policy from config
            retention_days = self._get_retention_days()
            
            if retention_days > 0:
                self.db_manager.archive_old_data(retention_days)
                logging.info(f"Cleaned up data older than {retention_days} days")
            
        except Exception as e:
            logging.error(f"Error cleaning up old data: {e}")
    
    def _get_retention_days(self):
        """Get data retention days from configuration"""
        try:
            # Use absolute path for the config file
            with open(BASE_DIR / 'reminder_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('settings', {}).get('data_retention_days', 30)
        except Exception as e:
            logging.warning(f"Could not load retention policy: {e}")
            return 30  # Default to 30 days

class ConfigManager:
    """Manages configuration file operations"""
    
    @staticmethod
    def load_config(config_path=None):
        """Load configuration from file"""
        if config_path is None:
            config_path = BASE_DIR / 'reminder_config.json'
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Configuration file {config_path} not found")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing configuration file: {e}")
            return None
    
    @staticmethod
    def save_config(config, config_path=None):
        """Save configuration to file"""
        if config_path is None:
            config_path = BASE_DIR / 'reminder_config.json'
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logging.info(f"Configuration saved to {config_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")
            return False
    
    @staticmethod
    def validate_config(config):
        """Validate configuration structure"""
        required_sections = ['reminders', 'settings']
        required_reminder_fields = ['message', 'enabled']
        
        try:
            # Check main sections
            for section in required_sections:
                if section not in config:
                    logging.error(f"Missing required section: {section}")
                    return False
            
            # Check reminders
            reminders = config['reminders']
            for reminder_name, reminder_config in reminders.items():
                for field in required_reminder_fields:
                    if field not in reminder_config:
                        logging.error(f"Missing field '{field}' in reminder '{reminder_name}'")
                        return False
                
                # Check time-based reminders have 'time' field
                if reminder_name in ['lunch', 'end_day']:
                    if 'time' not in reminder_config:
                        logging.error(f"Missing 'time' field in reminder '{reminder_name}'")
                        return False
                
                # Check interval-based reminders have 'interval_minutes' field
                elif 'interval_minutes' not in reminder_config:
                    logging.error(f"Missing 'interval_minutes' field in reminder '{reminder_name}'")
                    return False
            
            logging.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logging.error(f"Error validating configuration: {e}")
            return False

class SystemUtils:
    """System-related utility functions"""
    
    @staticmethod
    def is_windows():
        """Check if running on Windows"""
        import platform
        return platform.system().lower() == 'windows'
    
    @staticmethod
    def get_system_info():
        """Get basic system information"""
        import platform
        return {
            'system': platform.system(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python_version': platform.python_version()
        }
    
    @staticmethod
    def create_directories(directories):
        """Create directories if they don't exist"""
        from pathlib import Path
        
        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                logging.info(f"Directory created/verified: {directory}")
            except Exception as e:
                logging.error(f"Error creating directory {directory}: {e}")
    
    @staticmethod
    def check_dependencies():
        """Check if required dependencies are available"""
        required_modules = ['schedule', 'tinydb', 'tkinter']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            logging.error(f"Missing required modules: {', '.join(missing_modules)}")
            return False
        
        logging.info("All required dependencies are available")
        return True
