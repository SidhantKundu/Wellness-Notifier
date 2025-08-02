"""
Database Management Module
Handles local data storage using TinyDB for simplicity and portability.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

class DatabaseManager:
    def __init__(self, db_path="data/wellness_reminders.json"):
        # Handle both absolute and relative paths robustly
        path_obj = Path(db_path)
        if path_obj.is_absolute():
            self.db_path = path_obj
        else:
            # Resolve relative paths from the script's location
            script_dir = Path(__file__).resolve().parent
            self.db_path = script_dir / db_path
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use caching middleware for better performance
        self.db = TinyDB(
            self.db_path,
            storage=CachingMiddleware(JSONStorage)
        )
        
        # Define tables
        self.reminders_table = self.db.table('reminders')
        self.daily_stats_table = self.db.table('daily_stats')
        self.settings_table = self.db.table('settings')
        
        logging.info(f"Database initialized at {self.db_path}")

    def clear_all_data(self):
        """Truncate all tables for a fresh start."""
        try:
            self.reminders_table.truncate()
            self.daily_stats_table.truncate()
            self.settings_table.truncate()
            logging.info("All database tables have been cleared.")
        except Exception as e:
            logging.error(f"Error clearing all data from database: {e}")
    
    def initialize_database(self):
        """Initialize database with default settings if needed"""
        try:
            # Check if settings exist, if not create defaults
            if not self.settings_table.all():
                self.settings_table.insert({
                    'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
                    'app_version': '1.0.0',
                    'created_at': datetime.now().isoformat()
                })
            
            logging.info("Database initialization completed")
            
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            raise
    
    def log_reminder_response(self, reminder_type, response_type, delay_minutes=0, rescheduled_time=None):
        """Log a reminder response to the database"""
        try:
            current_time = datetime.now()
            
            record = {
                'task_name': reminder_type,
                'original_time': current_time.isoformat(),
                'response_type': response_type,  # 'ok', 'busy', 'skip'
                'delay_minutes': delay_minutes,
                'rescheduled_time': rescheduled_time.isoformat() if rescheduled_time else None,
                'final_status': 'completed' if response_type == 'ok' else 'pending' if response_type == 'busy' else 'skipped',
                'timestamp': current_time.isoformat(),
                'date': current_time.strftime('%Y-%m-%d')
            }
            
            self.reminders_table.insert(record)
            
            # Update daily statistics
            self.update_daily_stats(reminder_type, response_type)
            
            logging.info(f"Logged reminder response: {reminder_type} - {response_type}")
            
        except Exception as e:
            logging.error(f"Error logging reminder response: {e}")
    
    def update_daily_stats(self, reminder_type, response_type):
        """Update daily statistics for the reminder"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Query for today's stats
            DailyStats = Query()
            existing_stats_list = self.daily_stats_table.search(
                (DailyStats.date == today) & (DailyStats.task_name == reminder_type)
            )
            
            if existing_stats_list:
                # Update existing record
                existing_stats = existing_stats_list[0]
                doc_id_to_update = existing_stats.doc_id
                
                # Prepare the data to update
                update_data = {
                    f'{response_type}_count': existing_stats.get(f'{response_type}_count', 0) + 1,
                    'total_count': existing_stats.get('total_count', 0) + 1,
                    'last_updated': datetime.now().isoformat()
                }
                
                self.daily_stats_table.update(update_data, doc_ids=[doc_id_to_update])
            else:
                # Create new record
                stats = {
                    'date': today,
                    'task_name': reminder_type,
                    'ok_count': 1 if response_type == 'ok' else 0,
                    'busy_count': 1 if response_type == 'busy' else 0,
                    'skip_count': 1 if response_type == 'skip' else 0,
                    'total_count': 1,
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
                
                self.daily_stats_table.insert(stats)
            
        except Exception as e:
            logging.error(f"Error updating daily stats: {e}")
    
    def get_recent_responses(self, hours=3):
        """Get recent reminder responses within specified hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_str = cutoff_time.isoformat()
            
            Reminder = Query()
            recent_responses = self.reminders_table.search(
                Reminder.timestamp > cutoff_str
            )
            
            return recent_responses
            
        except Exception as e:
            logging.error(f"Error getting recent responses: {e}")
            return []
    
    def get_total_skips_today(self):
        """Get the total count of skipped tasks for the current day."""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            Reminder = Query()
            todays_skips = self.reminders_table.search(
                (Reminder.date == today) &
                (Reminder.response_type == 'skip') &
                (~Reminder.task_name.test(lambda x: x.endswith('_rescheduled')))
            )
            return len(todays_skips)
        except Exception as e:
            logging.error(f"Error getting total skips for today: {e}")
            return 0

    def get_consecutive_skips(self):
        """Get count of consecutive skips from most recent responses"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            Reminder = Query()
            today_responses = self.reminders_table.search(
                (Reminder.date == today) & 
                (~Reminder.task_name.test(lambda x: x.endswith('_rescheduled'))) &
                (~Reminder.task_name.test(lambda x: x == 'motivational_intervention'))
            )
            
            # Sort by timestamp descending (most recent first)
            today_responses.sort(key=lambda x: x['timestamp'], reverse=True)
            
            consecutive_skips = 0
            for response in today_responses:
                if response['response_type'] == 'skip':
                    consecutive_skips += 1
                else:
                    break
            
            return consecutive_skips
            
        except Exception as e:
            logging.error(f"Error getting consecutive skips: {e}")
            return 0
    
    def get_overlapping_tasks(self):
        """Get count of overlapping/pending tasks"""
        try:
            # Count busy responses that haven't been resolved yet
            recent_busy = self.get_recent_responses(hours=2)
            busy_count = sum(1 for response in recent_busy 
                           if response['response_type'] == 'busy' 
                           and response.get('final_status') == 'pending')
            return busy_count
            
        except Exception as e:
            logging.error(f"Error getting overlapping tasks: {e}")
            return 0
    
    def get_daily_summary(self, date=None):
        """Get daily summary statistics"""
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            DailyStats = Query()
            daily_stats = self.daily_stats_table.search(DailyStats.date == date)
            
            return daily_stats
            
        except Exception as e:
            logging.error(f"Error getting daily summary: {e}")
            return []
    
    def get_completion_rate(self, days=7):
        """Get completion rate over the last N days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            DailyStats = Query()
            recent_stats = self.daily_stats_table.search(DailyStats.date >= cutoff_str)
            
            total_reminders = sum(stat.get('total_count', 0) for stat in recent_stats)
            completed_reminders = sum(stat.get('ok_count', 0) for stat in recent_stats)
            
            if total_reminders > 0:
                return (completed_reminders / total_reminders) * 100
            return 0.0
            
        except Exception as e:
            logging.error(f"Error calculating completion rate: {e}")
            return 0.0
    
    def get_task_performance(self, task_name, days=7):
        """Get performance statistics for a specific task"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            DailyStats = Query()
            task_stats = self.daily_stats_table.search(
                (DailyStats.date >= cutoff_str) & 
                (DailyStats.task_name == task_name)
            )
            
            total_count = sum(stat.get('total_count', 0) for stat in task_stats)
            ok_count = sum(stat.get('ok_count', 0) for stat in task_stats)
            skip_count = sum(stat.get('skip_count', 0) for stat in task_stats)
            busy_count = sum(stat.get('busy_count', 0) for stat in task_stats)
            
            return {
                'task_name': task_name,
                'total_count': total_count,
                'ok_count': ok_count,
                'skip_count': skip_count,
                'busy_count': busy_count,
                'completion_rate': (ok_count / total_count * 100) if total_count > 0 else 0,
                'skip_rate': (skip_count / total_count * 100) if total_count > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"Error getting task performance: {e}")
            return {}
    
    def clear_daily_data(self):
        """Clear today's reminder data (for daily reset)"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            Reminder = Query()
            self.reminders_table.remove(Reminder.date == today)
            
            DailyStats = Query()
            self.daily_stats_table.remove(DailyStats.date == today)
            
            logging.info("Daily data cleared for reset")
            
        except Exception as e:
            logging.error(f"Error clearing daily data: {e}")
    
    def archive_old_data(self, retention_days=30):
        """Archive data older than retention_days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            # Archive to separate file before deletion
            archive_path = self.db_path.parent / f"archive_{cutoff_date.strftime('%Y%m%d')}.json"
            
            Reminder = Query()
            old_reminders = self.reminders_table.search(Reminder.date < cutoff_str)
            
            DailyStats = Query()
            old_stats = self.daily_stats_table.search(DailyStats.date < cutoff_str)
            
            if old_reminders or old_stats:
                archive_data = {
                    'reminders': old_reminders,
                    'daily_stats': old_stats,
                    'archived_on': datetime.now().isoformat()
                }
                
                with open(archive_path, 'w') as f:
                    json.dump(archive_data, f, indent=2)
                
                # Remove old data from main database
                self.reminders_table.remove(Reminder.date < cutoff_str)
                self.daily_stats_table.remove(DailyStats.date < cutoff_str)
                
                logging.info(f"Archived {len(old_reminders)} reminders and {len(old_stats)} daily stats to {archive_path}")
            
        except Exception as e:
            logging.error(f"Error archiving old data: {e}")
    
    def update_settings(self, key, value):
        """Update a setting in the database"""
        try:
            Settings = Query()
            if self.settings_table.search(Settings.last_reset_date.exists()):
                self.settings_table.update({key: value}, Settings.last_reset_date.exists())
            else:
                self.settings_table.insert({key: value})
            
            logging.info(f"Updated setting {key} = {value}")
            
        except Exception as e:
            logging.error(f"Error updating setting {key}: {e}")
    
    def get_setting(self, key, default=None):
        """Get a setting from the database"""
        try:
            Settings = Query()
            settings_doc = self.settings_table.get(Settings[key].exists())
            
            if settings_doc:
                return settings_doc[key]
            else:
                return default
                
        except Exception as e:
            logging.error(f"Error getting setting {key}: {e}")
            return default
    
    def get_wellness_insights(self):
        """Get insights about wellness patterns"""
        try:
            # Get data for the last week
            week_performance = {}
            task_types = ['water', 'eye_rest', 'stretch', 'lunch', 'end_day']
            
            for task in task_types:
                perf = self.get_task_performance(task, days=7)
                if perf:
                    week_performance[task] = perf
            
            # Overall completion rate
            overall_rate = self.get_completion_rate(days=7)
            
            # Recent patterns
            recent_responses = self.get_recent_responses(hours=24)
            
            return {
                'overall_completion_rate': overall_rate,
                'task_performance': week_performance,
                'recent_activity_count': len(recent_responses),
                'consecutive_skips': self.get_consecutive_skips(),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error generating wellness insights: {e}")
            return {}
    
    def close(self):
        """Close the database connection"""
        try:
            self.db.close()
            logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database: {e}")
