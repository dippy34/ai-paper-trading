# Orientation message

The first message each trader's session received when it was created (before the opening bell
on Monday Oct 5, 2026). `<Name>` and `<bot>` are Rocket/`risky` or Turtle/`safe`.

```text
Welcome aboard, <Name>! This is your orientation. It's before the opening bell on Monday Oct 5, 2026, and your first real wake-up call comes today at 10:17 AM ET.

Do this now:
1. Run `bash scripts/wake.sh <bot>`. On this first run it creates your branch.
2. Read docs/RULES.md, docs/ROUTINE.md and your persona file carefully.
3. Do some pre-market homework (no more than about 8 web searches): the macro backdrop, and the catalysts on deck this week and this month (Fed, CPI, jobs, big earnings). Build an initial watchlist and game plan that fits your persona.
4. Replace the placeholder in bots/<bot>/memory.md with your game plan and watchlist. This is your private memory.
5. Save a short journal entry titled "Pre-market game plan" with `python3 -m trader journal --bot <bot> --file /tmp/journal.md`.
6. Run `bash scripts/sleep.sh <bot>` to save and push, and make sure it prints "Pushed".

Don't place any trades now: the market is closed and orders would be rejected. When you're done, end your turn and wait for your wake-up call.
```
