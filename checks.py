def check_sub(uid, bot, db_query):
    chans = db_query("SELECT channel FROM sponsors", fetchall=True)

    if not chans:
        return True, None

    for (ch,) in chans:
        original = ch

        try:
            if ch.startswith("http"):
                ch = ch.rstrip("/").split("/")[-1]
            if ch.startswith("t.me/"):
                ch = ch.split("/", 1)[1]
            if not ch.startswith("@"):
                ch = "@" + ch

            member = bot.get_chat_member(ch, uid)

            if member.status in ("left", "kicked"):
                return False, original

        except Exception:
            return False, original

    return True, None
