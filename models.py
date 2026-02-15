import sqlite3
import datetime

DB_NAME = "the_juken.db"

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # User Profile Table
    # Stores basic user info and aggregate stats
    c.execute('''CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT DEFAULT '受験生',
        target_school TEXT DEFAULT '未設定',
        total_study_time_minutes INTEGER DEFAULT 0
    )''')
    
    # Vocabulary Test Results Table
    # Stores history of vocabulary tests
    c.execute('''CREATE TABLE IF NOT EXISTS vocab_test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        score INTEGER,
        total_questions INTEGER,
        accuracy REAL
    )''')
    
    # Check if user exists, if not create default
    c.execute('SELECT count(*) FROM user_profile')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO user_profile (username, target_school, total_study_time_minutes) VALUES (?, ?, ?)', 
                  ("受験生", "東京大学", 0))
        
    conn.commit()
    conn.close()

def get_user_profile():
    """Get the current user's profile."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM user_profile LIMIT 1')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_target_school(new_school):
    """Update the target school."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE user_profile SET target_school = ? WHERE id = 1', (new_school,))
    conn.commit()
    conn.close()

def add_study_time(minutes):
    """Add to total study time."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE user_profile SET total_study_time_minutes = total_study_time_minutes + ? WHERE id = 1', (minutes,))
    conn.commit()
    conn.close()

def record_test_result(score, total):
    """Record a vocabulary test result."""
    accuracy = (score / total) * 100 if total > 0 else 0
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO vocab_test_results (score, total_questions, accuracy) 
                 VALUES (?, ?, ?)''', (score, total, accuracy))
    conn.commit()
    conn.close()

def get_avg_accuracy():
    """Get average accuracy from all tests."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT AVG(accuracy) FROM vocab_test_results')
    result = c.fetchone()[0]
    conn.close()
    return round(result, 1) if result is not None else 0.0

if __name__ == "__main__":
    init_db()
