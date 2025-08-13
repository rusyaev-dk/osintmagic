
from __future__ import annotations
import asyncio, aiosqlite, time, json, os, base64

class TTLCache:
    def __init__(self, path: str = "data/cache.sqlite", ttl_sec: int = 86400):
        self.path = path
        self.ttl = ttl_sec
        os.makedirs(os.path.dirname(path), exist_ok=True)

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS cache (
                k TEXT PRIMARY KEY,
                v BLOB NOT NULL,
                ts REAL NOT NULL
            )""")
            await db.commit()

    async def get(self, key: str):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT v, ts FROM cache WHERE k=?", (key,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                v, ts = row
                if time.time() - ts > self.ttl:
                    return None
                return json.loads(v)

    async def set(self, key: str, value):
        data = json.dumps(value, ensure_ascii=False)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("REPLACE INTO cache(k,v,ts) VALUES(?,?,?)", (key, data, time.time()))
            await db.commit()
