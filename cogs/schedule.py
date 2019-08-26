import calendar
import datetime
from pprint import pprint

import pytz
import tzlocal
from discord.ext import commands, tasks

import persistence

TASKS_LOOP_FREQ = 60.0


class ScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.taskscheck.start()

    def cog_unload(self):
        self.taskscheck.cancel()

    @tasks.loop(seconds=TASKS_LOOP_FREQ)
    async def taskscheck(self):
        now = get_localized_now()
        await check_pings(self.bot, now)

    @commands.command(pass_context=True)
    async def timezone(self, context, timezone=''):
        try:
            pytz.timezone(timezone)
            persistence.set_config(
                persistence.ConfigName.PINGS, 'timezone', timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            await context.send(
                f'Sorry, the timezone {timezone} is not valid. Choose one from '
                f'https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568')

    @commands.command(pass_context=True)
    async def addschedule(self, context, weekdayname='', hour='', minute='', *, args=''):
        await create_ping(context, weekdayname, hour, minute, args, True)

    @commands.command(pass_context=True)
    async def addping(self, context, weekdayname='', hour='', minute='', *, args=''):
        await create_ping(context, weekdayname, hour, minute, args, False)

    @commands.command(pass_context=True)
    async def schedule(self, context, *args):
        message = context.message
        channel = message.channel
        await message.delete()
        if args:
            for named_day in expand_arguments(args):
                await schedule_day(channel, named_day)
        else:
            await schedule_weekend(channel)


# Module level functions
async def check_pings(bot, now):
    print('Checking pings')
    # TODO Restrict query to pings relative to current server only
    pprint(persistence.get_pings())
    for ping in persistence.get_pings():
        # TODO move below to coroutine to ensure pings of the next minute are never skipped
        print(f'checking ping #{ping.doc_id}')
        if now.weekday() == ping['weekday'] and now.hour == ping['hour'] and now.minute == ping['minute']:
            print(str(now) + f" triggering ping #{ping.doc_id}")
            # server = bot.get_guild(ping['server_id'])
            channel = bot.get_channel(ping['channel_id'])
            # TODO check why channel is None
            if ping['add_schedule'] is True:
                await schedule_weekend(channel)
            await channel.send(ping['message'])


async def create_ping(context, weekdayname, hour, minute, msg, add_schedule):
    message = context.message
    await message.delete()

    channel = message.channel

    if weekdayname == '' or hour == '' or minute == '':
        await channel.send(f"Oops! Weekday and hour are required arguments, please try again")
        return

    # Check weekeday
    try:
        weekdayname = weekdayname.capitalize()
    except:
        await channel.send(f"Oops! `{weekdayname}` doesn't look like a week day name, please try again")
        return
    if weekdayname in calendar.day_name[:]:
        weekday = calendar.day_name[:].index(weekdayname)
    elif weekdayname in calendar.day_abbr[:]:
        weekday = calendar.day_abbr[:].index(weekdayname)
    else:
        await channel.send(
            f"Oops! `{weekdayname}` is not a full week day name nor an abbreviated version, did you mispell it?")
        return

    # Check hour
    if not hour.isdigit() or int(hour) not in range(0, 24):
        await channel.send(f"Oops! `{hour}` is not a proper hour number in 24h format, please try again")
        return
    if not minute.isdigit() or int(minute) not in range(0, 60):
        await channel.send(f"Oops! `{minute}` is not a proper minute number, please try again")
        return

    persistence.create_ping(
        channel.id, channel.guild.id, weekday, hour, minute, msg, add_schedule)
    await channel.send(f"Setting a schedule check on `{calendar.day_name[weekday]}` at `{hour}:{minute}` with the "
                       f"following message:\n{msg}")


def get_localized_now():
    tz_name = tzlocal.get_localzone().zone
    local_tz = pytz.timezone(tz_name)
    local_time = local_tz.localize(datetime.datetime.now())

    config = persistence.get_config(persistence.ConfigName.PINGS)

    if config and config.timezone:
        wanted_tz = pytz.timezone(config.timezone)
        local_time = local_time.astimezone(wanted_tz)
    return local_time


async def schedule_weekend(channel):
    await schedule_day(channel, calendar.day_name[4], 12)
    for day in range(5, 7):
        await schedule_day(channel, calendar.day_name[day], 9)


async def schedule_day(channel, day, start=0):
    await channel.send(f'```\n{day}\n```')

    times = [t for t in range(start, 21, 3)]

    for time in times:
        full_time = (
            f"{t_add(time, 0)} - {t_add(time, 3)} EST"
            f" | {t_add(time, 5)} - {t_add(time, 8)} UK"
            f" | {t_add(time, 6)} - {t_add(time, 9)} EU"
            f" | {t_add(time, 15)} - {t_add(time, 18)} JAP"
        )
        message = await channel.send(full_time)
        await message.add_reaction('\N{THUMBS UP SIGN}')
        await message.add_reaction('\N{THUMBS DOWN SIGN}')


def expand_arguments(args):
    args_expanded = []
    for arg in args:
        if arg == 'weekend':
            args_expanded.append(calendar.day_name[5])
            args_expanded.append(calendar.day_name[6])
            args_expanded.append(calendar.day_name[7])
        else:
            args_expanded.append(arg)
    return args_expanded


def t_add(time, to_add):
    result = (time + to_add) % 24
    return f"{result:02d}:00"


def setup(bot):
    bot.add_cog(ScheduleCog(bot))
