
from __future__ import annotations
import re

BAD_WORDS = set(x.strip().lower() for x in [
    "admin","administrator","test","tester","qwerty","user","username","abc","abcd","abc123","qwe123",
    "root","system","sys","support","help","moderator","mod","guest","test1","test2","demo",
    "xxxx","xxxxx","xxxxxx","xxx","xXx","pro","user12345","anonymous","anon","null","undefined","na",
    "mail","email","contact","info"
] if x)

RE_ONLY_DIGITS = re.compile(r"^\d{3,}$")
RE_REPEAT = re.compile(r"^(.)\1{3,}$")  # aaaa, _____
RE_NON_WORDY = re.compile(r"^[^a-zA-Zа-яА-ЯёЁ0-9]+$")
RE_RANDOMISH = re.compile(r"^(?=.*[A-Za-zА-Яа-яЁё])(?=.*\d)[A-Za-zА-Яа-яЁё\d]{4,}$")  # letters+digits mash
RE_ONLY_LETTERS_SHORT = re.compile(r"^[a-zA-Z]{1,2}$")

def looks_bad(username: str) -> bool:
    u = username.strip().lower()
    if len(u) < 3: return True
    if RE_ONLY_LETTERS_SHORT.match(u): return True
    if u in BAD_WORDS: return True
    if RE_ONLY_DIGITS.match(u): return True
    if RE_REPEAT.match(u): return True
    if RE_NON_WORDY.match(u): return True
    # if seems random like ab12cd3
    if RE_RANDOMISH.match(u) and not any(ch in u for ch in "-_."):
        return True
    return False
