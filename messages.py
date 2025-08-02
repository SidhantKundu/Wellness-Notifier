"""
Motivational Messages Module
Handles escalation logic and displays motivational messages.
Enhanced to trigger after just 2 skipped tasks for better intervention.
"""

import logging
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from notifier import MotivationalDialog

# Define the base directory of the script to make paths absolute
BASE_DIR = Path(__file__).resolve().parent

class MotivationalMessages:
    """Manages motivational messages and escalation logic"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.config = self._load_config()
        self.last_motivational_shown = None
        # Track the last skip count that triggered a message to avoid re-triggering
        self.last_triggered_skip_count = 0
        
        # Enhanced motivational messages with more encouraging tone
        self.messages = [
            "🌟 Hey! I noticed you've skipped a couple of wellness reminders. Small breaks make a big difference in your day. How about trying the next one?",
            
            "💪 You're doing great work, but don't forget about yourself! You've missed a couple of self-care moments - your future self will thank you for the next one.",
            
            "🧠 Taking micro-breaks actually boosts productivity and creativity. You've skipped a few - let's get back on track with just one small step.",
            
            "⚡ I know you're focused on your work, but your body and mind need attention too. You've missed some reminders - the next one is your chance to shine!",
            
            "🎯 Consistency beats perfection! You've skipped a couple of wellness moments, but every next choice is a fresh start. You've got this!",
            
            "🌱 Self-care isn't selfish - it's smart! You've bypassed some important moments today. Ready to invest 2 minutes in yourself?",
            
            "💝 You take care of everything else so well. Now it's time to take care of YOU. A couple of missed reminders - let's change that pattern!",
            
            "🔄 Breaking the skip cycle is easier than you think. You've missed some wellness moments, but the next reminder is your comeback moment!",
            
            "🏃‍♀️ Your mind and body are your most important tools. A couple of missed maintenance checks - time to give them some love!",
            
            "⏰ Two minutes of self-care now saves hours of fatigue later. You've skipped some reminders - make the next one count!"
        ]
        
        # Quick intervention messages for immediate skip patterns
        self.quick_intervention_messages = [
            "🤔 Two skips in a row? Your wellness matters more than any deadline. Take just 30 seconds for yourself.",
            
            "⚠️ Pattern alert! You've skipped two wellness reminders. Your productivity will actually improve with a quick break.",
            
            "🚦 Pause for a moment - two skipped reminders means your body is asking for attention. Listen to it!"
        ]
    
    def _load_config(self):
        """Load escalation configuration with lowered thresholds"""
        try:
            # Use absolute path for the config file
            with open(BASE_DIR / 'reminder_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                settings = config.get('settings', {})
                
                # Override default thresholds for more proactive intervention
                settings['escalation_threshold'] = 2  # Reduced from 3 to 2
                settings['escalation_window_hours'] = 2  # Reduced from 3 to 2
                
                return settings
        except Exception as e:
            logging.warning(f"Could not load escalation config: {e}")
            return {
                'escalation_threshold': 2,  # More aggressive intervention
                'escalation_window_hours': 2
            }
    
    def should_escalate(self):
        """
        Determine if escalation message should be shown.
        Triggers every time the total skip count for the day reaches a multiple of 2.
        """
        try:
            total_skips = self.db_manager.get_total_skips_today()

            is_new_milestone = (total_skips >= 2 and
                                total_skips % 2 == 0 and
                                total_skips > self.last_triggered_skip_count)

            if is_new_milestone:
                logging.info(f"Escalation triggered: {total_skips} total skips is a new milestone.")
                self.last_triggered_skip_count = total_skips
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking escalation criteria: {e}")
            return False

    def show_motivational_message(self):
        """Show a motivational message to the user with enhanced logic"""
        try:
            # The decision to show is now fully handled by should_escalate()
            message = self._select_appropriate_message()
            
            # Add current context for personalization
            context_info = self._get_context_info()
            if context_info:
                message += f"\n\n{context_info}"
            
            # Show the message
            MotivationalDialog.show_motivational_message(message)
            
            # Update last shown time (still useful for other potential logic)
            self.last_motivational_shown = datetime.now().isoformat()
            
            # Log the motivational intervention
            self._log_motivational_intervention()
            
            logging.info("Motivational message displayed")
            
        except Exception as e:
            logging.error(f"Error showing motivational message: {e}")
    
    def _select_appropriate_message(self):
        """Select appropriate message based on skip pattern"""
        try:
            # Check consecutive skips for different messaging
            total_skips = self.db_manager.get_total_skips_today()
            
            if total_skips >= 4: # If they've skipped 4 or more
                # More serious intervention for 4+ skips
                serious_messages = [
                    "🚨 You've skipped several wellness reminders now. Your health is your wealth - let's prioritize it together. Just one small step?",
                    "💼 I know work is demanding, but you've missed multiple self-care moments. High performers take care of themselves too!",
                    "🔥 You're on a skip streak, but let's start a wellness streak instead! Your body and mind are asking for attention."
                ]
                return random.choice(serious_messages)
            
            # Default to regular motivational messages for the first couple of triggers
            return random.choice(self.messages)
            
        except Exception as e:
            logging.error(f"Error selecting message: {e}")
            return random.choice(self.messages)
            
    def _get_context_info(self):
        """Get contextual information about user's wellness patterns - more encouraging"""
        try:
            # Get recent stats
            recent_responses = self.db_manager.get_recent_responses(hours=4)
            
            if not recent_responses:
                return "Every wellness choice is a step toward a better you! 🌟"
            
            skipped_count = sum(1 for r in recent_responses if r['response_type'] == 'skip')
            completed_count = sum(1 for r in recent_responses if r['response_type'] == 'ok')
            
            # Create encouraging context message
            if skipped_count > completed_count and completed_count > 0:
                return f"You've completed {completed_count} wellness tasks today - that's great! Let's add one more. 💪"
            elif completed_count > 0:
                return f"You've done well with {completed_count} wellness tasks! Keep the momentum going. 🌟"
            elif skipped_count <= 2:
                return "You're just getting started today. One small wellness choice can turn everything around! 🌱"
            else:
                return "It's never too late to start taking care of yourself. Your future self will thank you! ✨"
                
        except Exception as e:
            logging.error(f"Error getting context info: {e}")
            return "Every moment is a new chance to choose wellness! 🌟"
    
    def _log_motivational_intervention(self):
        """Log that a motivational intervention was shown"""
        try:
            # Create a special log entry for motivational interventions
            self.db_manager.reminders_table.insert({
                'task_name': 'motivational_intervention',
                'original_time': datetime.now().isoformat(),
                'response_type': 'shown',
                'delay_minutes': 0,
                'rescheduled_time': None,
                'final_status': 'intervention',
                'timestamp': datetime.now().isoformat(),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'trigger_reason': self._get_trigger_reason()
            })
            
        except Exception as e:
            logging.error(f"Error logging motivational intervention: {e}")
    
    def _get_trigger_reason(self):
        """Get the reason that triggered the motivational message"""
        try:
            total_skips = self.db_manager.get_total_skips_today()
            reasons = [f"total_skips:{total_skips}"]
            return ','.join(reasons)
            
        except Exception as e:
            logging.error(f"Error getting trigger reason: {e}")
            return 'error'
    
    def get_daily_motivation(self):
        """Get a daily motivational message (for future use)"""
        daily_messages = [
            "🌅 Start your day with intention - small wellness choices lead to big results!",
            "💫 Today is full of opportunities to take care of yourself. Seize them!",
            "🌱 Tiny, consistent wellness habits create extraordinary transformations.",
            "⚡ Your energy and focus multiply when you prioritize self-care.",
            "🎯 Make wellness a priority today, not an afterthought.",
            "🌟 You deserve to feel amazing - make choices that support that today!",
            "💪 Invest in your health today for a stronger, happier tomorrow.",
            "🧠 Your mind and body are your success tools - maintain them with care!"
        ]
        
        return random.choice(daily_messages)
    
    def customize_message_for_task(self, task_type, skip_count):
        """Customize motivational message based on specific task type"""
        task_specific_messages = {
            'water': [
                f"💧 You've skipped {skip_count} hydration reminders. Your brain is 75% water - let's fuel it properly!",
                f"🚰 {skip_count} missed water breaks can affect your concentration and energy. Your body is asking for hydration!"
            ],
            'eye_rest': [
                f"👁️ Your eyes work hard all day! {skip_count} missed breaks can strain your vision. Give them 20 seconds of love.",
                f"🔍 {skip_count} skipped eye rests add up fast. The 20-20-20 rule exists for a reason - your vision is precious!"
            ],
            'stretch': [
                f"🧘 {skip_count} missed stretch breaks means tension is building. Your posture and energy will thank you for moving!",
                f"💪 Your body isn't meant to stay still. {skip_count} skipped stretches - let's get that blood flowing!"
            ],
            'lunch': [
                f"🍽️ Skipping lunch {skip_count} times impacts your energy and focus. You deserve proper nourishment!",
                f"⏰ {skip_count} missed lunch breaks - your body needs fuel to maintain peak performance."
            ]
        }
        
        task_messages = task_specific_messages.get(task_type, self.messages)
        return random.choice(task_messages)
    
    def reset_daily_counters(self):
        """Reset daily tracking counters"""
        self.last_motivational_shown = None
        self.last_triggered_skip_count = 0
        logging.info("Motivational message counters reset for new day")
    
    def get_encouragement_for_completion(self):
        """Get encouraging message when user completes a task after intervention"""
        encouragement_messages = [
            "🎉 Awesome! You listened to your body and took action. That's what wellness champions do!",
            "⭐ Great choice! Every wellness decision you make is an investment in your best self.",
            "🙌 Perfect! You just proved that you can prioritize yourself. Keep this energy going!",
            "✨ Wonderful! Your future self is already thanking you for this moment of self-care.",
            "💪 That's the spirit! Small actions like this create big positive changes over time."
        ]
        
        return random.choice(encouragement_messages)
    
    def should_show_encouragement(self):
        """Check if user should receive encouragement after completing a task following skips"""
        try:
            # Get recent responses (last hour)
            recent_responses = self.db_manager.get_recent_responses(hours=1)
            
            if len(recent_responses) < 2:
                return False
            
            # Sort by timestamp (most recent first)
            recent_responses.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Check if the most recent response was 'ok' and previous ones were skips
            if recent_responses[0]['response_type'] == 'ok':
                # Check if there were skips before this completion
                skip_count = sum(1 for r in recent_responses[1:4] if r['response_type'] == 'skip')
                return skip_count >= 1
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking encouragement criteria: {e}")
            return False
