import sqlite3
import os

DB_NAME = "podcast.db"

def init_db():
    """データベースとテーブルを初期化する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_name TEXT NOT NULL,
            level TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

def add_topic(topic_name, level, status='pending'):
    """トピックを追加する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO topics (topic_name, level, status) VALUES (?, ?, ?)', (topic_name, level, status))
    conn.commit()
    conn.close()
    print(f"トピックを追加しました: {topic_name} ({level})")

def get_pending_topic():
    """未処理(pending)のトピックを1つ取得する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, topic_name, level FROM topics WHERE status = "pending" LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "topic": row[1], "level": row[2]}
    return None

def update_topic_status(topic_id, status):
    """トピックのステータスを更新する"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE topics SET status = ? WHERE id = ?', (status, topic_id))
    conn.commit()
    conn.close()
    print(f"トピックID {topic_id} のステータスを '{status}' に更新しました。")

if __name__ == "__main__":
    # テスト用: 直接実行された場合は初期化とサンプルデータ追加を行う
    init_db()
    # サンプルデータが存在しない場合のみ追加
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT count(*) FROM topics')
    count = cursor.fetchone()[0]
    conn.close()
    
    if count == 0:
        add_topic("Impact of AI on Education", "Intermediate")
        add_topic("History of the Internet", "Beginner")
        add_topic("Climate Change Solutions", "Advanced")
        print("サンプルデータを追加しました。")
    else:
        print(f"既存のデータ件数: {count}")
