import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import sqlite3
import json
import typing
import random
from typing import Dict, List, Optional, Union, Any
import traceback
import os
from utils import command_help, owner_only, mod_only

# Option letter mapping for buttons
OPTION_LETTERS = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭"]

class QuizRegistrationView(discord.ui.View):
    def __init__(self, quiz_name: str, db, logger):
        super().__init__(timeout=None)  # Persistent view
        self.quiz_name = quiz_name
        self.db = db
        self.logger = logger
    
    @discord.ui.button(label="Register for Quiz", style=discord.ButtonStyle.primary, emoji="📝")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get quiz details
            quiz = await self.db.get_quiz_by_name(interaction.guild.id, self.quiz_name)
            
            if not quiz:
                await interaction.followup.send(f"❌ Quiz with name '{self.quiz_name}' not found.", ephemeral=True)
                return
            
            # Check if user is already registered
            if await self.db.is_user_registered(quiz['quiz_id'], interaction.user.id):
                await interaction.followup.send(f"❌ You are already registered for the quiz '{self.quiz_name}'.", ephemeral=True)
                return
            
            # Register user
            success = await self.db.register_user(quiz['quiz_id'], interaction.user.id, interaction.guild.id)
            
            if not success:
                await interaction.followup.send("❌ Failed to register for the quiz. Please try again.", ephemeral=True)
                return
            
            # Add role to user if it exists
            if quiz['role_id']:
                role = interaction.guild.get_role(quiz['role_id'])
                if role:
                    try:
                        await interaction.user.add_roles(role)
                        await interaction.followup.send(f"✅ You have been registered for quiz '{self.quiz_name}' and given the {role.mention} role.", ephemeral=True)
                    except:
                        await interaction.followup.send(f"✅ You have been registered for quiz '{self.quiz_name}', but I couldn't assign the role.", ephemeral=True)
                else:
                    await interaction.followup.send(f"✅ You have been registered for quiz '{self.quiz_name}'.", ephemeral=True)
            else:
                await interaction.followup.send(f"✅ You have been registered for quiz '{self.quiz_name}'.", ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error registering user via button: {str(e)}\n{traceback.format_exc()}")
            await interaction.followup.send("❌ An error occurred while trying to register for the quiz.", ephemeral=True)

class QuizDatabase:
    """Database handler for quiz system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.db_path = "data/quiz.db"
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Initialize database
        self._init_db()
        
    def _init_db(self):
        """Initialize database tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create quizzes table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                category_id INTEGER,
                role_id INTEGER,
                UNIQUE(guild_id, name)
            )
            ''')
            
            # Create rounds table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rounds (
                round_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id) ON DELETE CASCADE,
                UNIQUE(quiz_id, name)
            )
            ''')
            
            # Create questions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                options TEXT NOT NULL,  -- JSON array of options
                correct_index INTEGER NOT NULL,
                points INTEGER NOT NULL DEFAULT 100,
                position INTEGER NOT NULL,
                FOREIGN KEY (round_id) REFERENCES rounds (round_id) ON DELETE CASCADE
            )
            ''')
            
            # Create user registrations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id) ON DELETE CASCADE,
                UNIQUE(quiz_id, user_id)
            )
            ''')
            
            # Create responses table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                option_index INTEGER NOT NULL,
                is_correct BOOLEAN NOT NULL,
                points_awarded INTEGER NOT NULL,
                response_time REAL NOT NULL,  -- time taken to respond in seconds
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions (question_id) ON DELETE CASCADE
            )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error initializing quiz database: {str(e)}\n{traceback.format_exc()}")
    
    async def create_quiz(self, guild_id: int, name: str, creator_id: int, category_id: int = None, role_id: int = None) -> int:
        """Create a new quiz and return its ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO quizzes (guild_id, name, created_by, category_id, role_id) VALUES (?, ?, ?, ?, ?)",
                (guild_id, name, creator_id, category_id, role_id)
            )
            
            quiz_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return quiz_id
            
        except sqlite3.IntegrityError:
            # Quiz with this name already exists
            return None
        except Exception as e:
            self.logger.error(f"Error creating quiz: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def add_round(self, quiz_id: int, name: str) -> int:
        """Add a round to a quiz and return its ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the next position for this round
            cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM rounds WHERE quiz_id = ?", (quiz_id,))
            position = cursor.fetchone()[0]
            
            cursor.execute(
                "INSERT INTO rounds (quiz_id, name, position) VALUES (?, ?, ?)",
                (quiz_id, name, position)
            )
            
            round_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return round_id
            
        except sqlite3.IntegrityError:
            # Round with this name already exists
            return None
        except Exception as e:
            self.logger.error(f"Error adding round: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def add_question(self, round_id: int, question_text: str, options: List[str], 
                           correct_index: int, points: int = 100) -> int:
        """Add a question to a round and return its ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get the next position for this question
            cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM questions WHERE round_id = ?", (round_id,))
            position = cursor.fetchone()[0]
            
            # Convert options list to JSON string
            options_json = json.dumps(options)
            
            cursor.execute(
                "INSERT INTO questions (round_id, question_text, options, correct_index, points, position) VALUES (?, ?, ?, ?, ?, ?)",
                (round_id, question_text, options_json, correct_index, points, position)
            )
            
            question_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return question_id
            
        except Exception as e:
            self.logger.error(f"Error adding question: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def register_user(self, quiz_id: int, user_id: int, guild_id: int) -> bool:
        """Register a user for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO registrations (quiz_id, user_id, guild_id) VALUES (?, ?, ?)",
                (quiz_id, user_id, guild_id)
            )
            
            conn.commit()
            conn.close()
            
            return True
            
        except sqlite3.IntegrityError:
            # User already registered
            return False
        except Exception as e:
            self.logger.error(f"Error registering user: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def record_response(self, quiz_id: int, question_id: int, user_id: int, 
                             option_index: int, is_correct: bool, points_awarded: int, 
                             response_time: float) -> bool:
        """Record a user's response to a question"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """INSERT INTO responses 
                   (quiz_id, question_id, user_id, option_index, is_correct, points_awarded, response_time) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (quiz_id, question_id, user_id, option_index, is_correct, points_awarded, response_time)
            )
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error recording response: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def get_quiz_by_name(self, guild_id: int, name: str) -> Dict:
        """Get quiz details by name"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM quizzes WHERE guild_id = ? AND name = ?",
                (guild_id, name)
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting quiz: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def get_round_by_name(self, quiz_id: int, name: str) -> Dict:
        """Get round details by name"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM rounds WHERE quiz_id = ? AND name = ?",
                (quiz_id, name)
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting round: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def get_question(self, question_id: int) -> Dict:
        """Get question details by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM questions WHERE question_id = ?",
                (question_id,)
            )
            
            row = cursor.fetchone()
            
            if row:
                result = dict(row)
                # Parse options from JSON
                result['options'] = json.loads(result['options'])
                return result
            
            conn.close()
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting question: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def get_questions_for_round(self, round_id: int) -> List[Dict]:
        """Get all questions for a round"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM questions WHERE round_id = ? ORDER BY position",
                (round_id,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            questions = []
            for row in rows:
                question = dict(row)
                # Parse options from JSON
                question['options'] = json.loads(question['options'])
                questions.append(question)
                
            return questions
            
        except Exception as e:
            self.logger.error(f"Error getting questions: {str(e)}\n{traceback.format_exc()}")
            return []
    
    async def get_rounds_for_quiz(self, quiz_id: int) -> List[Dict]:
        """Get all rounds for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM rounds WHERE quiz_id = ? ORDER BY position",
                (quiz_id,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Error getting rounds: {str(e)}\n{traceback.format_exc()}")
            return []
    
    async def get_quiz_registrations(self, quiz_id: int) -> List[int]:
        """Get all user IDs registered for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT user_id FROM registrations WHERE quiz_id = ?",
                (quiz_id,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in rows]
            
        except Exception as e:
            self.logger.error(f"Error getting registrations: {str(e)}\n{traceback.format_exc()}")
            return []
    
    async def is_user_registered(self, quiz_id: int, user_id: int) -> bool:
        """Check if a user is registered for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT COUNT(*) FROM registrations WHERE quiz_id = ? AND user_id = ?",
                (quiz_id, user_id)
            )
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            self.logger.error(f"Error checking registration: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def get_user_score(self, quiz_id: int, user_id: int) -> int:
        """Get a user's total score for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT SUM(points_awarded) FROM responses WHERE quiz_id = ? AND user_id = ?",
                (quiz_id, user_id)
            )
            
            total = cursor.fetchone()[0]
            conn.close()
            
            return total or 0
            
        except Exception as e:
            self.logger.error(f"Error getting user score: {str(e)}\n{traceback.format_exc()}")
            return 0
    
    async def get_leaderboard(self, quiz_id: int, limit: int = 10) -> List[Dict]:
        """Get the leaderboard for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT user_id, SUM(points_awarded) as total_points, 
                          COUNT(CASE WHEN is_correct = 1 THEN 1 END) as correct_answers,
                          COUNT(*) as total_answers
                   FROM responses 
                   WHERE quiz_id = ? 
                   GROUP BY user_id 
                   ORDER BY total_points DESC
                   LIMIT ?""",
                (quiz_id, limit)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {str(e)}\n{traceback.format_exc()}")
            return []
    
    async def get_user_rank(self, quiz_id: int, user_id: int) -> Dict:
        """Get a user's rank and stats for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get user's stats
            cursor.execute(
                """SELECT SUM(points_awarded) as total_points, 
                          COUNT(CASE WHEN is_correct = 1 THEN 1 END) as correct_answers,
                          COUNT(*) as total_answers
                   FROM responses 
                   WHERE quiz_id = ? AND user_id = ?""",
                (quiz_id, user_id)
            )
            
            stats = cursor.fetchone()
            
            if not stats or stats['total_points'] is None:
                conn.close()
                return None
                
            stats = dict(stats)
            
            # Get user's rank
            cursor.execute(
                """SELECT COUNT(*) + 1 FROM (
                       SELECT user_id, SUM(points_awarded) as total_points
                       FROM responses
                       WHERE quiz_id = ?
                       GROUP BY user_id
                       HAVING total_points > ?
                   )""",
                (quiz_id, stats['total_points'] or 0)
            )
            
            rank = cursor.fetchone()[0]
            conn.close()
            
            stats['rank'] = rank
            stats['user_id'] = user_id
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting user rank: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def update_quiz_channels(self, quiz_id: int, category_id: int, role_id: int) -> bool:
        """Update the category and role IDs for a quiz"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE quizzes SET category_id = ?, role_id = ? WHERE quiz_id = ?",
                (category_id, role_id, quiz_id)
            )
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating quiz channels: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def set_quiz_active(self, quiz_id: int, is_active: bool) -> bool:
        """Set a quiz's active status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE quizzes SET is_active = ? WHERE quiz_id = ?",
                (is_active, quiz_id)
            )
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting quiz active status: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def get_active_quizzes(self, guild_id: int) -> List[Dict]:
        """Get all active quizzes for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM quizzes WHERE guild_id = ? AND is_active = 1",
                (guild_id,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Error getting active quizzes: {str(e)}\n{traceback.format_exc()}")
            return []

class QuestionView(discord.ui.View):
    """Interactive view for quiz questions with buttons for options"""
    
    def __init__(self, quiz_cog, quiz_id, question, timeout=30.0):
        super().__init__(timeout=timeout)
        self.quiz_cog = quiz_cog
        self.quiz_id = quiz_id
        self.question = question
        self.question_id = question['question_id']
        self.correct_index = question['correct_index']
        self.points = question['points']
        self.options = question['options']
        self.responses = {}  # user_id -> {option_index, timestamp}
        self.start_time = datetime.datetime.now()
        
        # Add option buttons
        for i, option in enumerate(self.options):
            button = discord.ui.Button(
                label=f"{OPTION_LETTERS[i]} {option}",
                custom_id=f"option_{i}",
                style=discord.ButtonStyle.primary
            )
            button.callback = self.create_callback(i)
            self.add_item(button)
    
    def create_callback(self, option_index):
        """Create a callback for the given option index"""
        async def callback(interaction):
            user_id = interaction.user.id
            
            # Check if user already answered
            if user_id in self.responses:
                await interaction.response.send_message("You've already answered this question!", ephemeral=True)
                return
            
            # Calculate response time
            now = datetime.datetime.now()
            response_time = (now - self.start_time).total_seconds()
            
            # Record response
            self.responses[user_id] = {
                "option_index": option_index,
                "timestamp": now,
                "response_time": response_time
            }
            
            # Check if correct
            is_correct = option_index == self.correct_index
            
            # Calculate points (faster answers get more points)
            time_factor = max(0, 1 - (response_time / self.timeout))
            speed_bonus = int(self.points * 0.5 * time_factor)  # Up to 50% bonus for speed
            points_awarded = self.points + speed_bonus if is_correct else 0
            
            # Record in database
            await self.quiz_cog.db.record_response(
                self.quiz_id, 
                self.question_id, 
                user_id, 
                option_index,
                is_correct, 
                points_awarded, 
                response_time
            )
            
            # Send feedback to user
            if is_correct:
                await interaction.response.send_message(
                    f"✅ Correct! You earned {points_awarded} points (including {speed_bonus} speed bonus).", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Incorrect answer.", ephemeral=True)
                
            # Update leaderboard if needed
            await self.quiz_cog.update_leaderboard(self.quiz_id)
                
        return callback
    
    async def on_timeout(self):
        """Handle when the question times out"""
        # Disable all buttons
        for item in self.children:
            item.disabled = True

async def wait_for_message_with_exit(bot, ctx, prompt, cleanup_func=None):
    """Helper function to wait for message with exit capability"""
    message = await ctx.send(prompt + "\n\n*Type 'exit', 'cancel', or 'quit' to stop the quiz creation.*")
    
    try:
        response = await bot.wait_for(
            'message', 
            check=lambda msg: msg.author == ctx.author and msg.channel == ctx.channel,
            timeout=300.0  # 5 minute timeout
        )
        
        await message.delete()
        await response.delete()
        
        # Check for exit keywords
        content = response.content.strip().lower()
        if content in ['exit', 'cancel', 'quit', 'stop']:
            if cleanup_func:
                await cleanup_func()
            raise commands.UserInputError("Quiz creation cancelled by user.")
        
        return response.content.strip()
        
    except asyncio.TimeoutError:
        await message.delete()
        if cleanup_func:
            await cleanup_func()
        raise commands.UserInputError("Quiz creation timed out.")
    
async def wait_for_continue_or_cancel(ctx, message_content):
    """Show continue/cancel options with reactions"""
    msg = await ctx.send(f"{message_content}\n\n✅ - Continue\n❌ - Cancel quiz creation")
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
    
    try:
        reaction, user = await ctx.bot.wait_for('reaction_add', timeout=60.0, check=check)
        await msg.delete()
        
        if str(reaction.emoji) == "❌":
            raise commands.UserInputError("Quiz creation cancelled by user.")
        return True
        
    except asyncio.TimeoutError:
        await msg.delete()
        raise commands.UserInputError("Quiz creation timed out.")

class QuizCreationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.cancelled = False
        self.result = None
    
    @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Cancel Quiz Creation", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cancelled = True
        await interaction.response.send_message("❌ Quiz creation cancelled.", ephemeral=True)
        self.stop()

class QuizProgressTracker:
    def __init__(self, total_rounds):
        self.total_rounds = total_rounds
        self.current_round = 0
        self.questions_added = 0
        self.start_time = discord.utils.utcnow()
    
    def get_progress_embed(self, quiz_name):
        embed = discord.Embed(
            title=f"📊 Quiz Creation Progress",
            description=f"Creating quiz: **{quiz_name}**",
            color=discord.Color.blue()
        )
        
        # Progress bar visualization
        progress_percentage = (self.current_round / self.total_rounds) * 100 if self.total_rounds > 0 else 0
        filled_blocks = int(progress_percentage / 10)
        empty_blocks = 10 - filled_blocks
        progress_bar = "█" * filled_blocks + "░" * empty_blocks
        
        embed.add_field(
            name="Overall Progress", 
            value=f"`{progress_bar}` {progress_percentage:.1f}%\nRound {self.current_round}/{self.total_rounds}",
            inline=False
        )
        
        embed.add_field(name="Questions Added", value=f"🔢 {self.questions_added}", inline=True)
        
        # Time elapsed
        elapsed = discord.utils.utcnow() - self.start_time
        elapsed_mins = int(elapsed.total_seconds() / 60)
        elapsed_secs = int(elapsed.total_seconds() % 60)
        embed.add_field(name="Time Elapsed", value=f"⏱️ {elapsed_mins}m {elapsed_secs}s", inline=True)
        
        # Estimated time remaining (rough calculation)
        if self.current_round > 0:
            avg_time_per_round = elapsed.total_seconds() / self.current_round
            remaining_rounds = self.total_rounds - self.current_round
            est_remaining = int((avg_time_per_round * remaining_rounds) / 60)
            embed.add_field(name="Est. Remaining", value=f"⏳ ~{est_remaining}min", inline=True)
        
        embed.set_footer(text="💡 Type 'exit' at any prompt to cancel")
        embed.timestamp = discord.utils.utcnow()
        
        return embed

class Quiz(commands.Cog):
    """Quiz system for Discord servers"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.db = QuizDatabase(bot)
        
        # Active quizzes with their leaderboard messages
        self.active_quizzes = {}  # quiz_id -> {message, task, etc.}
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        # Cancel all leaderboard update tasks
        for quiz_data in self.active_quizzes.values():
            if quiz_data.get('leaderboard_task'):
                quiz_data['leaderboard_task'].cancel()
    
    # === User Registration ===
    
    @command_help("general", "Register for a quiz", "register <quiz_name>")
    @commands.hybrid_command(name="register", description="Register for a quiz")
    @commands.guild_only()
    async def register_quiz(self, ctx, quiz_name: str):
        """Register for a specified quiz"""
        await ctx.defer()
        
        try:
            # Get quiz details
            quiz = await self.db.get_quiz_by_name(ctx.guild.id, quiz_name)
            
            if not quiz:
                await ctx.send(f"❌ Quiz with name '{quiz_name}' not found.")
                return
            
            # Check if user is already registered
            if await self.db.is_user_registered(quiz['quiz_id'], ctx.author.id):
                await ctx.send(f"❌ You are already registered for the quiz '{quiz_name}'.")
                return
            
            # Register user
            success = await self.db.register_user(quiz['quiz_id'], ctx.author.id, ctx.guild.id)
            
            if not success:
                await ctx.send("❌ Failed to register for the quiz. Please try again.")
                return
            
            # Add role to user if it exists
            if quiz['role_id']:
                role = ctx.guild.get_role(quiz['role_id'])
                if role:
                    try:
                        await ctx.author.add_roles(role)
                        await ctx.send(f"✅ You have been registered for quiz '{quiz_name}' and given the {role.mention} role.")
                    except:
                        await ctx.send(f"✅ You have been registered for quiz '{quiz_name}', but I couldn't assign the role.")
                else:
                    await ctx.send(f"✅ You have been registered for quiz '{quiz_name}'.")
            else:
                await ctx.send(f"✅ You have been registered for quiz '{quiz_name}'.")
                
        except Exception as e:
            self.logger.error(f"Error registering user: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to register for the quiz.")
    
    # === Quiz Master Commands ===

    @command_help("mod", "Send quiz registration embed to a channel", "give <channel> <quiz_name>")
    @commands.hybrid_command(name="give", description="Send quiz registration embed to specified channel")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)  # Adjust permissions as needed
    async def give_quiz(self, ctx, channel: discord.TextChannel, quiz_name: str):
        """Send a quiz registration embed with button to specified channel"""
        await ctx.defer()

        try:
            # Get quiz details
            quiz = await self.db.get_quiz_by_name(ctx.guild.id, quiz_name)

            if not quiz:
                await ctx.send(f"❌ Quiz with name '{quiz_name}' not found.")
                return

            # Create embed
            embed = discord.Embed(
                title=f"📝 Quiz Registration: {quiz_name}",
                description=f"Click the button below to register for the **{quiz_name}** quiz!",
                color=discord.Color.blue()
            )

            # Add quiz details to embed if available
            if quiz.get('description'):
                embed.add_field(name="Description", value=quiz['description'], inline=False)

            if quiz.get('role_id'):
                role = ctx.guild.get_role(quiz['role_id'])
                if role:
                    embed.add_field(name="Role", value=f"You'll receive the {role.mention} role upon registration", inline=False)

            # Add footer
            embed.set_footer(text=f"Quiz ID: {quiz['quiz_id']}")
            embed.timestamp = discord.utils.utcnow()

            # Create view with registration button
            view = QuizRegistrationView(quiz_name, self.db, self.logger)

            # Send embed to specified channel
            message = await channel.send(embed=embed, view=view)

            # Confirm to command user
            await ctx.send(f"✅ Quiz registration embed sent to {channel.mention}")

            # Make the view persistent (optional - if you want buttons to work after bot restart)
            # You'll need to add this message ID to your database and recreate views on bot startup

        except discord.Forbidden:
            await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}")
        except Exception as e:
            self.logger.error(f"Error sending quiz embed: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while sending the quiz registration embed.")
            
    @command_help("mod", "Create a new quiz", "quiz <name> <rounds: optional = 5>")
    @mod_only()
    @commands.hybrid_command(name="quiz", description="Create a new quiz")
    @commands.guild_only()
    async def create_quiz_with_exit(self, ctx: commands.Context, name: str, rounds: int = 5):
        """Create a new quiz with channels and role - with exit capability"""
        await ctx.defer()
        
        # Variables to track created resources for cleanup
        created_category = None
        created_role = None
        created_quiz_id = None

        # Progress tracker for quiz creation
        progress_tracker = QuizProgressTracker(rounds)
        
        async def cleanup():
            """Clean up created resources if quiz creation is cancelled"""
            try:
                if created_category:
                    await created_category.delete(reason="Quiz creation cancelled")
                if created_role:
                    await created_role.delete(reason="Quiz creation cancelled")
                if created_quiz_id:
                    await self.db.delete_quiz(created_quiz_id)  # You'll need this method
                await ctx.send("🧹 Cleaned up partially created quiz resources.")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
        
        try:
            # Check if quiz with this name already exists
            existing = await self.db.get_quiz_by_name(ctx.guild.id, name)
            if existing:
                await ctx.send(f"❌ A quiz with the name '{name}' already exists.")
                return
            
            # Ask for confirmation before starting
            view = QuizCreationView()
            confirm_msg = await ctx.send(
                f"🎯 **Starting quiz creation for '{name}' with {rounds} rounds**\n\n"
                "This will be an interactive process. You can cancel at any time by:\n"
                "• Typing `exit`, `cancel`, or `quit`\n"
                "• Clicking the cancel button\n"
                "• Not responding for 5 minutes\n\n"
                "Ready to begin?",
                view=view
            )
            
            await view.wait()
            await confirm_msg.delete()
            
            if view.cancelled:
                return
            
            # Create channels and role
            category, text_channel, voice_channel, role = await self._create_quiz_channels(ctx.guild, name)
            created_category = category
            created_role = role
            
            # Create quiz in database
            quiz_id = await self.db.create_quiz(
                ctx.guild.id, 
                name, 
                ctx.author.id,
                category.id if category else None,
                role.id if role else None
            )
            created_quiz_id = quiz_id
            
            if not quiz_id:
                await cleanup()
                await ctx.send("❌ Failed to create quiz. Please try again.")
                return
            
            # Send confirmation
            embed = discord.Embed(
                title=f"✅ Quiz '{name}' Created",
                description="Your quiz has been set up successfully!",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Category", value=category.mention if category else "None", inline=True)
            embed.add_field(name="Text Channel", value=text_channel.mention if text_channel else "None", inline=True)
            embed.add_field(name="Voice Channel", value=voice_channel.mention if voice_channel else "None", inline=True)
            embed.add_field(name="Role", value=role.mention if role else "None", inline=True)
            
            await ctx.send(embed=embed)

            # Send initial progress tracker
            progress_tracker.current_round = 0
            progress_embed = progress_tracker.get_progress_embed(name)
            progress_message = await ctx.send(embed=progress_embed)

            # Add rounds with exit capability
            for i in range(rounds):
                round_name = f"Round {i + 1}"
                progress_tracker.current_round = i + 1
                
                # Update progress
                progress_embed = progress_tracker.get_progress_embed(name)
                await progress_message.edit(embed=progress_embed)
                
                # Check if user wants to continue
                await wait_for_continue_or_cancel(ctx, f"📝 **Creating {round_name}**")
                
                round_id = await self.db.add_round(quiz_id, round_name)
                
                if not round_id:
                    await ctx.send(f"❌ Failed to add round '{round_name}'. Please try again.")
                    continue
                
                # Get number of questions with exit capability
                no_of_questions_str = await wait_for_message_with_exit(
                    self.bot, ctx, 
                    f"Please enter the number of questions for {round_name}:",
                    cleanup
                )
                
                try:
                    no_of_questions = int(no_of_questions_str)
                except ValueError:
                    await ctx.send("❌ Invalid number of questions. Using default value of 1.")
                    no_of_questions = 1

                if no_of_questions > 0:
                    for j in range(no_of_questions):
                        # Get question with exit capability
                        question_text = await wait_for_message_with_exit(
                            self.bot, ctx,
                            f"Please enter the question for question {j + 1} of {round_name}:",
                            cleanup
                        )

                        # Get options with exit capability
                        options_text = await wait_for_message_with_exit(
                            self.bot, ctx,
                            f"Please enter the options for question {j + 1} (comma-separated):",
                            cleanup
                        )

                        # Get correct index with exit capability
                        correct_index_str = await wait_for_message_with_exit(
                            self.bot, ctx,
                            f"Please enter the correct option index for question {j + 1}:",
                            cleanup
                        )
                        
                        try:
                            correct_index = int(correct_index_str)
                        except ValueError:
                            await ctx.send("❌ Invalid correct index. Please enter a valid integer.")
                            continue

                        options_list = [opt.strip() for opt in options_text.split(',')]
                        
                        # Get points with exit capability
                        points_str = await wait_for_message_with_exit(
                            self.bot, ctx,
                            f"Please enter the points for question {j + 1}:",
                            cleanup
                        )

                        try:
                            points = int(points_str)
                        except ValueError:
                            await ctx.send("❌ Invalid points. Please enter a valid integer.")
                            continue
                            
                        # Validate inputs
                        if correct_index < 0 or correct_index >= len(options_list):
                            await ctx.send(f"❌ Correct index must be between 0 and {len(options_list) - 1}.")
                            continue
                        
                        if points < 1:
                            await ctx.send("❌ Points must be at least 1.")
                            continue
                        
                        # Add question
                        question_id = await self.db.add_question(
                            round_id, 
                            question_text, 
                            options_list, 
                            correct_index, 
                            points
                        )
                        
                        if not question_id:
                            await ctx.send("❌ Failed to add question. Please try again.")
                            continue
                        
                        # Update progress tracker
                        progress_tracker.questions_added += 1
                        progress_embed = progress_tracker.get_progress_embed(name)
                        await progress_message.edit(embed=progress_embed)
                        
                        # Create preview embed
                        embed = discord.Embed(
                            title=f"✅ Question Added",
                            description=f"Added to quiz '{name}', round '{round_name}'",
                            color=discord.Color.green()
                        )
                        
                        embed.add_field(name="Question", value=question_text, inline=False)
                        
                        options_text = ""
                        for k, opt in enumerate(options_list):
                            marker = "✓" if k == correct_index else ""
                            options_text += f"{chr(65 + k)} {opt} {marker}\n"  # A, B, C, D
                            
                        embed.add_field(name="Options", value=options_text, inline=False)
                        embed.add_field(name="Points", value=str(points), inline=True)
                        
                        await ctx.send(embed=embed)
            
            # Final progress update
            progress_tracker.current_round = rounds
            progress_embed = progress_tracker.get_progress_embed(name)
            progress_embed.color = discord.Color.green()
            progress_embed.title = "✅ Quiz Creation Complete!"
            await progress_message.edit(embed=progress_embed)
            
            await ctx.send(f"🎉 Quiz '{name}' created successfully with {rounds} rounds!")
            
        except commands.UserInputError as e:
            # User cancelled or timed out
            await cleanup()
            if progress_message:
                try:
                    await progress_message.delete()
                except:
                    pass
            await ctx.send(f"❌ {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error creating quiz: {str(e)}\n{traceback.format_exc()}")
            await cleanup()
            if progress_message:
                try:
                    await progress_message.delete()
                except:
                    pass
            await ctx.send("❌ An error occurred while trying to create the quiz.")

    @command_help("mod", "Add a round to a quiz", "add_round <quiz> <name>")
    @mod_only()
    @commands.hybrid_command(name="add_round", description="Add a round to a quiz")
    @commands.guild_only()
    async def add_round(self, ctx, quiz: str, name: str):
        """Add a round to an existing quiz"""
        await ctx.defer()
        
        try:
            # Get quiz details
            quiz_data = await self.db.get_quiz_by_name(ctx.guild.id, quiz)
            
            if not quiz_data:
                await ctx.send(f"❌ Quiz with name '{quiz}' not found.")
                return
            
            # Check if round with this name already exists
            rounds = await self.db.get_rounds_for_quiz(quiz_data['quiz_id'])
            if any(r['name'].lower() == name.lower() for r in rounds):
                await ctx.send(f"❌ A round with the name '{name}' already exists in this quiz.")
                return
            
            # Add round
            round_id = await self.db.add_round(quiz_data['quiz_id'], name)
            
            if not round_id:
                await ctx.send("❌ Failed to add round. Please try again.")
                return
            
            await ctx.send(f"✅ Round '{name}' added to quiz '{quiz}'.")
                
        except Exception as e:
            self.logger.error(f"Error adding round: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to add the round.")
    
    @command_help("mod", "Add a question to a quiz round", "add_question <quiz> <round> <question> <options> <correct_index> [points]")
    @mod_only()
    @commands.hybrid_command(name="add_question", description="Add a question to a quiz round")
    @commands.guild_only()
    async def add_question(
        self, 
        ctx, 
        quiz: str, 
        round_name: str, 
        question: str, 
        options: str, 
        correct_index: int, 
        points: int = 100
    ):
        """Add a question to a quiz round"""
        await ctx.defer()
        
        try:
            # Get quiz details
            quiz_data = await self.db.get_quiz_by_name(ctx.guild.id, quiz)
            
            if not quiz_data:
                await ctx.send(f"❌ Quiz with name '{quiz}' not found.")
                return
            
            # Get round details
            round_data = await self.db.get_round_by_name(quiz_data['quiz_id'], round_name)
            
            if not round_data:
                await ctx.send(f"❌ Round with name '{round_name}' not found in quiz '{quiz}'.")
                return
            
            # Parse options (comma-separated list)
            option_list = [opt.strip() for opt in options.split(',')]
            
            # Validate option count
            if len(option_list) < 2:
                await ctx.send("❌ At least 2 options are required.")
                return
                
            # Validate correct index
            if correct_index < 0 or correct_index >= len(option_list):
                await ctx.send(f"❌ Correct index must be between 0 and {len(option_list) - 1}.")
                return
            
            # Validate points
            if points < 1:
                await ctx.send("❌ Points must be at least 1.")
                return
            
            # Add question
            question_id = await self.db.add_question(
                round_data['round_id'], 
                question, 
                option_list, 
                correct_index, 
                points
            )
            
            if not question_id:
                await ctx.send("❌ Failed to add question. Please try again.")
                return
            
            # Create preview embed
            embed = discord.Embed(
                title=f"✅ Question Added",
                description=f"Added to quiz '{quiz}', round '{round_name}'",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Question", value=question, inline=False)
            
            options_text = ""
            for i, opt in enumerate(option_list):
                marker = "✓" if i == correct_index else ""
                options_text += f"{OPTION_LETTERS[i]} {opt} {marker}\n"
                
            embed.add_field(name="Options", value=options_text, inline=False)
            embed.add_field(name="Points", value=str(points), inline=True)
            
            await ctx.send(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error adding question: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to add the question.")
    
    @command_help("mod", "Start a quiz", "start_quiz <quiz> [round]")
    @mod_only()
    @commands.hybrid_command(name="start_quiz", description="Start a quiz")
    @commands.guild_only()
    async def start_quiz(self, ctx, quiz: str, round_name: Optional[str] = None):
        """Start a quiz, optionally specifying a round to start from"""
        await ctx.defer()
        
        try:
            # Get quiz details
            quiz_data = await self.db.get_quiz_by_name(ctx.guild.id, quiz)
            
            if not quiz_data:
                await ctx.send(f"❌ Quiz with name '{quiz}' not found.")
                return
            
            # Check if quiz is already running
            if quiz_data['quiz_id'] in self.active_quizzes:
                await ctx.send(f"❌ Quiz '{quiz}' is already running.")
                return
            
            # Get rounds
            rounds = await self.db.get_rounds_for_quiz(quiz_data['quiz_id'])
            
            if not rounds:
                await ctx.send(f"❌ Quiz '{quiz}' has no rounds. Add some rounds first.")
                return
            
            # Initialize starting round
            start_round = 0
            
            # If round was specified, find its index
            if round_name:
                for i, r in enumerate(rounds):
                    if r['name'].lower() == round_name.lower():
                        start_round = i
                        break
                else:
                    await ctx.send(f"❌ Round '{round_name}' not found in quiz '{quiz}'.")
                    return
            
            # Mark quiz as active
            await self.db.set_quiz_active(quiz_data['quiz_id'], True)
            
            # Get the text channel for the quiz
            if quiz_data['category_id']:
                category = ctx.guild.get_channel(quiz_data['category_id'])
                text_channel = None
                
                if category:
                    for channel in category.text_channels:
                        if "quiz" in channel.name.lower():
                            text_channel = channel
                            break
                
                if not text_channel:
                    text_channel = ctx.channel
            else:
                text_channel = ctx.channel
            
            # Create leaderboard message
            leaderboard_embed = discord.Embed(
                title=f"🏆 {quiz} Leaderboard",
                description="The quiz is about to begin. Leaderboard will update after each answer.",
                color=discord.Color.gold()
            )
            
            leaderboard_msg = await text_channel.send(embed=leaderboard_embed)
            
            # Setup active quiz data
            self.active_quizzes[quiz_data['quiz_id']] = {
                'guild_id': ctx.guild.id,
                'name': quiz,
                'current_round': start_round,
                'rounds': rounds,
                'text_channel': text_channel,
                'leaderboard_msg': leaderboard_msg,
                'leaderboard_task': None,
            }
            
            # Start leaderboard update task
            self.active_quizzes[quiz_data['quiz_id']]['leaderboard_task'] = self.bot.loop.create_task(
                self._update_leaderboard_task(quiz_data['quiz_id'])
            )
            
            # Announce quiz start
            start_embed = discord.Embed(
                title=f"🎮 Quiz '{quiz}' Starting!",
                description=f"Get ready for the questions! Make sure you've registered with `/register_quiz {quiz}`",
                color=discord.Color.blue()
            )
            
            await text_channel.send(embed=start_embed)
            
            # Wait a moment before starting
            await asyncio.sleep(5)
            
            # Start the quiz
            self.bot.loop.create_task(self._run_quiz(quiz_data['quiz_id']))
            
            # Confirm to command user
            if ctx.channel != text_channel:
                await ctx.send(f"✅ Quiz '{quiz}' started in {text_channel.mention}.")
                
        except Exception as e:
            self.logger.error(f"Error starting quiz: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to start the quiz.")
    
    @command_help("mod", "Stop a running quiz", "stop_quiz <quiz>")
    @mod_only()
    @commands.hybrid_command(name="stop_quiz", description="Stop a running quiz")
    @commands.guild_only()
    async def stop_quiz(self, ctx, quiz: str):
        """Stop an active quiz"""
        await ctx.defer()
        
        try:
            # Get quiz details
            quiz_data = await self.db.get_quiz_by_name(ctx.guild.id, quiz)
            
            if not quiz_data:
                await ctx.send(f"❌ Quiz with name '{quiz}' not found.")
                return
            
            # Check if quiz is running
            if quiz_data['quiz_id'] not in self.active_quizzes:
                await ctx.send(f"❌ Quiz '{quiz}' is not currently running.")
                return
            
            # Stop the quiz
            await self._stop_quiz(quiz_data['quiz_id'])
            
            await ctx.send(f"✅ Quiz '{quiz}' has been stopped.")
                
        except Exception as e:
            self.logger.error(f"Error stopping quiz: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to stop the quiz.")
    
    # === User Commands ===
    
    @command_help("general", "View your rank in a quiz", "myrank <quiz>")
    @commands.hybrid_command(name="myrank", description="View your rank in a quiz")
    @commands.guild_only()
    async def myrank(self, ctx, quiz: str):
        """Show a user's rank and score for a quiz"""
        await ctx.defer(ephemeral=True)
        
        try:
            # Get quiz details
            quiz_data = await self.db.get_quiz_by_name(ctx.guild.id, quiz)
            
            if not quiz_data:
                await ctx.send(f"❌ Quiz with name '{quiz}' not found.", ephemeral=True)
                return
            
            # Check if user is registered
            if not await self.db.is_user_registered(quiz_data['quiz_id'], ctx.author.id):
                await ctx.send(f"❌ You are not registered for quiz '{quiz}'. Use `/register_quiz {quiz}` to register.", ephemeral=True)
                return
            
            # Get user's rank
            rank_data = await self.db.get_user_rank(quiz_data['quiz_id'], ctx.author.id)
            
            if not rank_data or rank_data.get('total_points') is None:
                await ctx.send(f"You haven't answered any questions in quiz '{quiz}' yet.", ephemeral=True)
                return
            
            # Create rank embed
            embed = discord.Embed(
                title=f"Your Rank in '{quiz}'",
                color=discord.Color.blue()
            )
            
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            
            embed.add_field(name="Rank", value=f"#{rank_data['rank']}", inline=True)
            embed.add_field(name="Total Points", value=str(rank_data['total_points']), inline=True)
            embed.add_field(name="Correct Answers", value=f"{rank_data['correct_answers']}/{rank_data['total_answers']}", inline=True)
            
            accuracy = (rank_data['correct_answers'] / rank_data['total_answers'] * 100) if rank_data['total_answers'] > 0 else 0
            embed.add_field(name="Accuracy", value=f"{accuracy:.1f}%", inline=True)
            
            await ctx.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error getting rank: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to get your rank.", ephemeral=True)
    
    # === Helper Methods ===

    async def wait_for_message_with_exit(bot, ctx, prompt, cleanup_func=None):
        """Helper function to wait for message with exit capability"""
        message = await ctx.send(prompt + "\n\n*Type 'exit', 'cancel', or 'quit' to stop the quiz creation.*")

        try:
            response = await bot.wait_for(
                'message', 
                check=lambda msg: msg.author == ctx.author and msg.channel == ctx.channel,
                timeout=300.0  # 5 minute timeout
            )

            await message.delete()
            await response.delete()

            # Check for exit keywords
            content = response.content.strip().lower()
            if content in ['exit', 'cancel', 'quit', 'stop']:
                if cleanup_func:
                    await cleanup_func()
                raise commands.UserInputError("Quiz creation cancelled by user.")

            return response.content.strip()

        except asyncio.TimeoutError:
            await message.delete()
            if cleanup_func:
                await cleanup_func()
            raise commands.UserInputError("Quiz creation timed out.")
    
    async def _create_quiz_channels(self, guild, quiz_name):
        """Create channels and role for a quiz"""
        try:
            # Create role first
            role = await guild.create_role(
                name=f"Quiz: {quiz_name}",
                color=discord.Color.blue(),
                reason=f"Created for quiz: {quiz_name}"
            )
            
            # Channel name (make it URL-friendly)
            channel_name = quiz_name.lower().replace(" ", "-")
            
            # Create category with permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            
            category = await guild.create_category(
                name=f"Quiz: {quiz_name}",
                overwrites=overwrites,
                reason=f"Created for quiz: {quiz_name}"
            )
            
            # Create text channel
            text_channel = await category.create_text_channel(
                name=f"quiz-{channel_name}",
                topic=f"Quiz channel for {quiz_name}",
                reason=f"Created for quiz: {quiz_name}"
            )
            
            # Create voice channel
            voice_channel = await category.create_voice_channel(
                name=f"Quiz Voice: {quiz_name}",
                reason=f"Created for quiz: {quiz_name}"
            )
            
            return category, text_channel, voice_channel, role
            
        except Exception as e:
            self.logger.error(f"Error creating quiz channels: {str(e)}\n{traceback.format_exc()}")
            return None, None, None, None
    
    async def update_leaderboard(self, quiz_id):
        """Update the leaderboard message for an active quiz"""
        if quiz_id not in self.active_quizzes:
            return
            
        quiz_data = self.active_quizzes[quiz_id]
        
        try:
            # Get leaderboard data
            leaderboard = await self.db.get_leaderboard(quiz_id, 10)
            
            if not leaderboard:
                return
                
            # Create leaderboard embed
            embed = discord.Embed(
                title=f"🏆 {quiz_data['name']} Leaderboard",
                description="Top players in this quiz:",
                color=discord.Color.gold()
            )
            
            # Format leaderboard entries
            leaderboard_text = ""
            
            for i, entry in enumerate(leaderboard, start=1):
                # Get username
                user = self.bot.get_user(entry['user_id'])
                
                if user:
                    username = user.name
                else:
                    # Try to get member from guild
                    guild = self.bot.get_guild(quiz_data['guild_id'])
                    member = guild.get_member(entry['user_id']) if guild else None
                    
                    if member:
                        username = member.display_name
                    else:
                        username = f"User {entry['user_id']}"
                
                # Format rank emojis for top 3
                if i == 1:
                    rank_emoji = "🥇"
                elif i == 2:
                    rank_emoji = "🥈"
                elif i == 3:
                    rank_emoji = "🥉"
                else:
                    rank_emoji = f"{i}."
                
                # Create entry with accuracy
                accuracy = (entry['correct_answers'] / entry['total_answers'] * 100) if entry['total_answers'] > 0 else 0
                leaderboard_text += f"{rank_emoji} **{username}** - {entry['total_points']} points ({entry['correct_answers']}/{entry['total_answers']} correct, {accuracy:.1f}%)\n"
            
            embed.add_field(name="Rankings", value=leaderboard_text, inline=False)
            
            # Update timestamp
            embed.set_footer(text=f"Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}")
            
            # Edit the message
            await quiz_data['leaderboard_msg'].edit(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error updating leaderboard: {str(e)}\n{traceback.format_exc()}")
    
    async def _update_leaderboard_task(self, quiz_id):
        """Background task to periodically update the leaderboard"""
        try:
            while quiz_id in self.active_quizzes:
                await self.update_leaderboard(quiz_id)
                await asyncio.sleep(10)  # Update every 10 seconds
                
        except asyncio.CancelledError:
            # Task was cancelled, exit cleanly
            pass
        except Exception as e:
            self.logger.error(f"Error in leaderboard task: {str(e)}\n{traceback.format_exc()}")
    
    async def _run_quiz(self, quiz_id):
        """Run a quiz from start to finish"""
        if quiz_id not in self.active_quizzes:
            return
            
        quiz_data = self.active_quizzes[quiz_id]
        
        try:
            # Get rounds
            rounds = quiz_data['rounds']
            
            # Start from current round
            for round_idx in range(quiz_data['current_round'], len(rounds)):
                round_data = rounds[round_idx]
                
                # Update current round
                quiz_data['current_round'] = round_idx
                
                # Get questions for this round
                questions = await self.db.get_questions_for_round(round_data['round_id'])
                
                if not questions:
                    continue
                
                # Announce round
                round_embed = discord.Embed(
                    title=f"🔄 Round {round_idx + 1}: {round_data['name']}",
                    description=f"Get ready for {len(questions)} questions!",
                    color=discord.Color.orange()
                )
                
                await quiz_data['text_channel'].send(embed=round_embed)
                
                # Wait before first question
                await asyncio.sleep(5)
                
                # Go through questions
                for q_idx, question in enumerate(questions):
                    # Check if quiz was stopped
                    if quiz_id not in self.active_quizzes:
                        return
                        
                    # Create question embed
                    q_embed = discord.Embed(
                        title=f"Question {q_idx + 1} of {len(questions)}",
                        description=question['question_text'],
                        color=discord.Color.blue()
                    )
                    
                    q_embed.add_field(
                        name="Round", 
                        value=f"{round_data['name']} ({round_idx + 1}/{len(rounds)})",
                        inline=False
                    )
                    
                    q_embed.add_field(
                        name="Points",
                        value=f"{question['points']} (plus speed bonus)",
                        inline=False
                    )
                    
                    q_embed.set_footer(text="Click a button below to answer")
                    
                    # Create question view with buttons
                    view = QuestionView(self, quiz_id, question, timeout=10.0)
                    
                    # Send question
                    question_msg = await quiz_data['text_channel'].send(embed=q_embed, view=view)
                    
                    # Wait for the view to timeout
                    await asyncio.sleep(view.timeout)
                    
                    # Show correct answer
                    correct_option = question['options'][question['correct_index']]
                    correct_letter = OPTION_LETTERS[question['correct_index']]
                    
                    answer_embed = discord.Embed(
                        title="⏱ Time's Up!",
                        description=f"",
                        color=discord.Color.green()
                    )
                    
                    # Display who got it right
                    correct_users = []
                    for user_id, response in view.responses.items():
                        if response['option_index'] == question['correct_index']:
                            user = self.bot.get_user(user_id)
                            if user:
                                correct_users.append(user.mention)
                    
                    if correct_users:
                        answer_embed.add_field(
                            name="Correct Answers",
                            value=", ".join(correct_users),
                            inline=False
                        )
                    else:
                        answer_embed.add_field(
                            name="Correct Answers",
                            value="Nobody got it right!",
                            inline=False
                        )
                    
                    await quiz_data['text_channel'].send(embed=answer_embed)
                    
                    # Update leaderboard
                    await self.update_leaderboard(quiz_id)
                    
                    # Wait between questions
                    await asyncio.sleep(5)
                
                # End of round message
                end_round_embed = discord.Embed(
                    title=f"🏁 Round {round_idx + 1} Complete!",
                    description=f"Round '{round_data['name']}' is now complete.",
                    color=discord.Color.green()
                )
                
                await quiz_data['text_channel'].send(embed=end_round_embed)
                
                # Wait between rounds
                await asyncio.sleep(10)
            
            # All rounds complete
            await self._end_quiz(quiz_id)
                
        except Exception as e:
            self.logger.error(f"Error running quiz: {str(e)}\n{traceback.format_exc()}")
            
            # Try to notify about the error
            if quiz_id in self.active_quizzes:
                try:
                    await quiz_data['text_channel'].send("❌ An error occurred while running the quiz. The quiz has been stopped.")
                except:
                    pass
                    
                # Stop the quiz due to error
                await self._stop_quiz(quiz_id)
    
    async def _end_quiz(self, quiz_id):
        """End a quiz normally, showing final results"""
        if quiz_id not in self.active_quizzes:
            return
            
        quiz_data = self.active_quizzes[quiz_id]
        
        try:
            # Get final leaderboard
            leaderboard = await self.db.get_leaderboard(quiz_id, 10)
            
            # Create final results embed
            final_embed = discord.Embed(
                title=f"🎉 Quiz '{quiz_data['name']}' Complete!",
                description="Here are the final results:",
                color=discord.Color.gold()
            )
            
            if leaderboard and leaderboard[0]['total_points'] > 0:
                # Get winner
                winner_id = leaderboard[0]['user_id']
                winner = self.bot.get_user(winner_id)
                
                if winner:
                    final_embed.add_field(
                        name="🏆 Winner",
                        value=f"Congratulations to {winner.mention} with {leaderboard[0]['total_points']} points!",
                        inline=False
                    )
                
                # Format final leaderboard
                leaderboard_text = ""
                
                for i, entry in enumerate(leaderboard, start=1):
                    # Get username
                    user = self.bot.get_user(entry['user_id'])
                    
                    if user:
                        username = user.name
                    else:
                        username = f"User {entry['user_id']}"
                    
                    # Format rank emojis
                    if i == 1:
                        rank_emoji = "🥇"
                    elif i == 2:
                        rank_emoji = "🥈"
                    elif i == 3:
                        rank_emoji = "🥉"
                    else:
                        rank_emoji = f"{i}."
                    
                    # Calculate accuracy
                    accuracy = (entry['correct_answers'] / entry['total_answers'] * 100) if entry['total_answers'] > 0 else 0
                    
                    leaderboard_text += f"{rank_emoji} **{username}** - {entry['total_points']} points ({entry['correct_answers']}/{entry['total_answers']} correct, {accuracy:.1f}%)\n"
                
                final_embed.add_field(name="Final Standings", value=leaderboard_text, inline=False)
            else:
                final_embed.add_field(name="No Results", value="Nobody participated in this quiz.", inline=False)
            
            # Thank everyone
            final_embed.add_field(
                name="Thank You",
                value="Thanks to everyone who participated!",
                inline=False
            )
            
            await quiz_data['text_channel'].send(embed=final_embed)
            
            # Mark quiz as inactive
            await self.db.set_quiz_active(quiz_id, False)
            
            # Clean up
            await self._stop_quiz(quiz_id, announce=False)
                
        except Exception as e:
            self.logger.error(f"Error ending quiz: {str(e)}\n{traceback.format_exc()}")
            
            # Force stop
            await self._stop_quiz(quiz_id)
    
    async def _stop_quiz(self, quiz_id, announce=True):
        """Stop a quiz and clean up"""
        if quiz_id not in self.active_quizzes:
            return
            
        quiz_data = self.active_quizzes[quiz_id]
        
        try:
            # Announce if requested
            if announce:
                try:
                    await quiz_data['text_channel'].send("⚠️ The quiz has been stopped by an administrator.")
                except:
                    pass
            
            # Cancel leaderboard task
            if quiz_data.get('leaderboard_task'):
                quiz_data['leaderboard_task'].cancel()
            
            # Mark quiz as inactive
            await self.db.set_quiz_active(quiz_id, False)
            
            # Remove from active quizzes
            del self.active_quizzes[quiz_id]
                
        except Exception as e:
            self.logger.error(f"Error stopping quiz: {str(e)}\n{traceback.format_exc()}")


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Quiz(bot))