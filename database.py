import aiosqlite
import datetime
import json

DB_NAME = "bot_database.db"

# One-time bonus credited automatically when a new user joins/starts the bot
JOIN_BONUS_COINS = 5

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Users Table - Added coins and last_earn_time
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TEXT,
            last_active TEXT,
            commands_count INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            daily_limit INTEGER DEFAULT 10,
            used_today INTEGER DEFAULT 0,
            last_reset TEXT,
            coins INTEGER DEFAULT 0,
            last_earn_time TEXT
        )''')
        
        # Likes Table
        await db.execute('''CREATE TABLE IF NOT EXISTS likes (
            user_id INTEGER,
            uid TEXT,
            region TEXT,
            timestamp TEXT
        )''')
        
        # Protected Numbers Table
        await db.execute('''CREATE TABLE IF NOT EXISTS protected_numbers (
            number TEXT PRIMARY KEY,
            admin_id INTEGER
        )''')

        # Link Whitelist Table
        await db.execute('''CREATE TABLE IF NOT EXISTS link_whitelist (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TEXT
        )''')

        # Redeem Codes Table
        await db.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
            code TEXT PRIMARY KEY,
            coins INTEGER NOT NULL,
            max_uses INTEGER NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TEXT
        )''')
        
        # Redeem Usage Table
        await db.execute('''CREATE TABLE IF NOT EXISTS redeem_usage (
            code TEXT,
            user_id INTEGER,
            PRIMARY KEY (code, user_id)
        )''')
        await db.commit()

# --- Coin Management System ---

async def get_coins(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def add_coin(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def deduct_coin(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = MAX(0, coins - ?) WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def set_earn_timestamp(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("UPDATE users SET last_earn_time = ? WHERE user_id = ?", (now, user_id))
        await db.commit()

async def get_last_earn_time(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT last_earn_time FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def clear_earn_timestamp(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET last_earn_time = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

# --- User Tracking & Limits ---

async def add_or_update_user(user_id, username, first_name, last_name):
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        
        if user:
            await db.execute(
                "UPDATE users SET username=?, first_name=?, last_name=?, last_active=? WHERE user_id=?",
                (username, first_name, last_name, now, user_id)
            )
            await db.commit()
            return False
        else:
            # New user -> grant a one-time join bonus of 5 coins
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, last_name, join_date, last_active, coins) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, now, now, JOIN_BONUS_COINS)
            )
            await db.commit()
            return True

async def is_banned(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return bool(row[0]) if row else False

async def check_daily_limit(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        today = datetime.date.today().isoformat()
        cursor = await db.execute("SELECT used_today, last_reset, daily_limit FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row: return True, 0, 10
        used, last_reset, limit = row
        if last_reset != today:
            await db.execute("UPDATE users SET used_today = 0, last_reset = ? WHERE user_id = ?", (today, user_id))
            await db.commit()
            return True, 0, limit
        return used < limit, used, limit

async def log_activity(user_id, cmd, target=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET commands_count = commands_count + 1, used_today = used_today + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

# --- Likes System ---

async def can_user_like(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        last_24h = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()
        cursor = await db.execute("SELECT timestamp FROM likes WHERE user_id = ? AND timestamp > ? ORDER BY timestamp DESC LIMIT 1", (user_id, last_24h))
        row = await cursor.fetchone()
        return (True, None) if not row else (False, row[0])

async def record_user_like(user_id, uid, region):
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("INSERT INTO likes (user_id, uid, region, timestamp) VALUES (?, ?, ?, ?)", (user_id, uid, region, now))
        await db.commit()
        return True

async def get_cooldown_time(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT timestamp FROM likes WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
        row = await cursor.fetchone()
        if not row: return "0s"
        last_time = datetime.datetime.fromisoformat(row[0])
        remaining = (last_time + datetime.timedelta(hours=24)) - datetime.datetime.now()
        hours, remainder = divmod(int(remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"

async def reset_likes_cooldown():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM likes")
        await db.commit()

# --- Admin Functions ---

async def is_protected(number):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT count(*) FROM protected_numbers WHERE number = ?", (str(number),))
        row = await cursor.fetchone()
        return row[0] > 0

async def protect_number(number, admin_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO protected_numbers (number, admin_id) VALUES (?, ?)", (str(number), admin_id))
        await db.commit()

async def unprotect_number(number):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM protected_numbers WHERE number = ?", (str(number),))
        await db.commit()

async def add_link_whitelist(user_id, added_by):
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute(
            "INSERT OR REPLACE INTO link_whitelist (user_id, added_by, added_at) VALUES (?, ?, ?)",
            (int(user_id), int(added_by), now)
        )
        await db.commit()

async def remove_link_whitelist(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("DELETE FROM link_whitelist WHERE user_id = ?", (int(user_id),))
        await db.commit()
        return cur.rowcount > 0

async def is_link_whitelisted(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT count(*) FROM link_whitelist WHERE user_id = ?", (int(user_id),))
        row = await cursor.fetchone()
        return row[0] > 0

async def get_link_whitelist():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, added_by, added_at FROM link_whitelist ORDER BY added_at DESC")
        return await cursor.fetchall()

async def create_redeem_code(code, coins, max_uses, created_by):
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute(
            "INSERT OR REPLACE INTO redeem_codes (code, coins, max_uses, used_count, created_by, created_at) "
            "VALUES (?, ?, ?, COALESCE((SELECT used_count FROM redeem_codes WHERE code = ?), 0), ?, ?)",
            (code, int(coins), int(max_uses), code, int(created_by), now),
        )
        await db.commit()

async def get_redeem_code(code):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT code, coins, max_uses, used_count, created_by, created_at FROM redeem_codes WHERE code = ?",
            (code,),
        )
        return await cursor.fetchone()

async def increment_redeem_use(code):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE redeem_codes SET used_count = used_count + 1 WHERE code = ?",
            (code,),
        )
        await db.commit()

async def has_user_redeemed(code, user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT 1 FROM redeem_usage WHERE code = ? AND user_id = ?", (code, user_id))
        return await cursor.fetchone() is not None

async def mark_code_redeemed(code, user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO redeem_usage (code, user_id) VALUES (?, ?)", (code, user_id))
        await db.commit()

async def delete_redeem_code(code):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
        await db.execute("DELETE FROM redeem_usage WHERE code = ?", (code,))
        await db.commit()

async def ban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def unban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        return [row[0] for row in await cursor.fetchall()]

async def set_user_limit(user_id, limit):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET daily_limit = ? WHERE user_id = ?", (limit, user_id))
        await db.commit()

async def get_user_info(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row: return None
        
        c2 = await db.execute("SELECT count(*) FROM likes WHERE user_id = ?", (user_id,))
        likes_count = (await c2.fetchone())[0]
        
        keys = ["user_id", "username", "first_name", "last_name", "join_date", "last_active", "commands_count", "is_banned", "daily_limit", "used_today", "last_reset", "coins", "last_earn_time"]
        data = dict(zip(keys, row))
        data['likes_count'] = likes_count
        return data

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        stats = {}
        c = await db.execute("SELECT count(*) FROM users")
        stats['total_users'] = (await c.fetchone())[0]
        
        today = datetime.date.today().isoformat()
        c = await db.execute("SELECT count(*) FROM users WHERE join_date > ?", (today,))
        stats['new_users_today'] = (await c.fetchone())[0]
        
        c = await db.execute("SELECT count(*) FROM users WHERE last_active > ?", (today,))
        stats['active_today'] = (await c.fetchone())[0]
        
        # Mocking top commands for stats panel since we only track total count per user currently
        stats['top_commands'] = [("/ffinfo", "N/A"), ("/like", "N/A"), ("/visits", "N/A")]
        
        c = await db.execute("SELECT count(*) FROM likes")
        total_likes = (await c.fetchone())[0]
        stats['bot_stats'] = [("Total Likes Delivered", total_likes)]
        
        return stats

async def get_top_users_by_coins(limit=10):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, first_name, username, coins FROM users ORDER BY coins DESC LIMIT ?", (limit,))
        return await cursor.fetchall()

async def reset_all_coins():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = 0")
        await db.commit()
