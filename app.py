import discord
from discord.ext import commands
from thefuzz import fuzz
import argparse
import shlex
import asyncio
import os

def parse_range(range_str, is_float=False):
    if '-' in range_str:
        start, end = range_str.split('-')
        if is_float:
            return float(start), float(end)
        return int(start), int(end)
    if is_float:
        return float(range_str), float(range_str)
    return int(range_str), int(range_str)

def parse_duration(duration_str):
    hours, minutes = 0, 0
    if 'h' in duration_str:
        hours, remainder = duration_str.split('h')
        hours = int(hours.strip())
        if 'm' in remainder:
            minutes = int(remainder.split('m')[0].strip())
    elif 'm' in duration_str:
        minutes = int(duration_str.split('m')[0].strip())
    return hours * 60 + minutes

def parse_votes(votes_str):
    votes_str = votes_str.upper().replace('M', '000000').replace('K', '000')
    if '.' in votes_str:
        parts = votes_str.split('.')
        whole, fractional = parts[0], parts[1]
        multiplier = 10 ** (6 - len(fractional))
        return int(whole + fractional) * multiplier
    return int(votes_str)

def parse_actors(actor_str):
    actors = actor_str.split(" in ")[0]
    return [actor.strip() for actor in actors.replace(' and ', ', ').split(', ')]

def filter_movies(movies, args):
    filtered_movies = []
    for movie in movies:
        if args.year and not (parse_range(args.year)[0] <= int(movie['year']) <= parse_range(args.year)[1]):
            continue
        if args.duration:
            duration_range = parse_range(args.duration)
            movie_duration = parse_duration(movie['duration'])
            if not (duration_range[0] <= movie_duration <= duration_range[1]):
                continue
        if args.rating and not (parse_range(args.rating, True)[0] <= float(movie['rating']) <= parse_range(args.rating, True)[1]):
            continue
        if args.votes:
            votes_range = parse_range(args.votes.upper().replace('M', '000000').replace('K', '000'))
            movie_votes = parse_votes(movie['votes'])
            if not (votes_range[0] <= movie_votes <= votes_range[1]):
                continue
        filtered_movies.append(movie)
    return filtered_movies

def parse_query(query):
    args = argparse.Namespace(title=None, actor=None, year=None, duration=None, rating=None, votes=None)
    for param in shlex.split(query):
        if ':' in param:
            key, value = param.split(':', 1)
            if key.lower() == 'title':
                args.title = value
            elif key.lower() == 'actor':
                args.actor = value
            elif key.lower() == 'year':
                args.year = value
            elif key.lower() == 'duration':
                args.duration = value
            elif key.lower() == 'rating':
                args.rating = value
            elif key.lower() == 'votes':
                args.votes = value
        else:
            print(f"Invalid parameter format: {param}")
    return args

async def search_movies(ctx, args, database_path='movies_database.txt'):
    with open(database_path, 'r', encoding='utf-8') as file:
        movies = [line.strip().split('", "') for line in file]
        movies = [{
            'title': parts[0].strip('"'),
            'link': parts[1],
            'year': parts[2],
            'duration': parts[3],
            'ageRequirement': parts[4],
            'rating': parts[5],
            'votes': parts[6],
            'metascore': parts[7],
            'plot': parts[8],
            'imageUrl': parts[9],
            'actors': parts[10].strip('"')
        } for parts in movies if len(parts) == 11]
    
    filtered_movies = filter_movies(movies, args)
    
    # Detected query string
    detected_args = []
    if args.title:
        detected_args.append(f"title:{args.title}")
    if args.actor:
        detected_args.append(f"actor:{args.actor}")
    if args.year:
        detected_args.append(f"year:{args.year}")
    if args.duration:
        detected_args.append(f"duration:{args.duration}")
    if args.rating:
        detected_args.append(f"rating:{args.rating}")
    if args.votes:
        detected_args.append(f"votes:{args.votes}")
    detected_args_str = ' '.join(detected_args)
    detected_query_msg = f"```!search {detected_args_str}```\n" if detected_args else ""

    # Original criteria message
    criteria_parts = []
    if args.year:
        criteria_parts.append(f"made in the year {args.year}")
    if args.duration:
        criteria_parts.append(f"lasting between {args.duration} minutes")
    if args.rating:
        criteria_parts.append(f"with a rating of {args.rating}")
    if args.votes:
        criteria_parts.append(f"having between {args.votes} votes")
    criteria_msg = ", ".join(criteria_parts)
    if criteria_msg:
        criteria_msg = f" {criteria_msg}"
    title_actor_msg = ""
    if args.title or args.actor:
        title_actor_msg = f"Returning the closest matches for {args.title if args.title else ''}{' and ' if args.title and args.actor else ''}{args.actor if args.actor else ''}"
    else:
        title_actor_msg = "Returning the first five matches"

    response = detected_query_msg + f"{title_actor_msg} in the set of movies{criteria_msg}\n"

    if args.title:
        filtered_movies = sorted(filtered_movies, key=lambda m: fuzz.ratio(args.title.lower(), m['title'].lower()), reverse=True)[:5]
    elif args.actor:
        filtered_movies = sorted(filtered_movies, key=lambda m: max(fuzz.ratio(args.actor.lower(), actor.lower()) for actor in parse_actors(m['actors'])), reverse=True)[:5]
    else:
        filtered_movies = filtered_movies[:5]

    for i, movie in enumerate(filtered_movies):
        response += f"{i+1}. {movie['title']} [more info]({movie['link']})\n"
    response += "Use !usage for search specifics and make a ticket to request a movie"

    await ctx.send(response)




intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to requests!')

    # Replace 'your_channel_id' with the actual channel ID
    channel = bot.get_channel(1188603066535129129)
    if channel:
        async for message in channel.history(limit=200):  # Adjust limit as needed
            if message.author != bot.user:
                await message.delete()



@bot.command(name='search')
async def search(ctx, *, query: str):
    if ctx.channel.id != 1188603066535129129:
        return
    args = parse_query(query)
    await search_movies(ctx, args)
    await ctx.message.delete()

@bot.event
async def on_message(message):
    # Check if the message is in the designated channel
    if message.channel.id == 1188603066535129129:
        # Check if it's a valid !search command or !usage
        if message.content.startswith('!search '):
            args = parse_query(message.content[len('!search '):])
            # If args is not None, it means it's a valid search query
            if any(vars(args).values()):
                await bot.process_commands(message)
                return
        elif message.content.strip() == '!usage':
            await bot.process_commands(message)
            return

        # If it's not from the bot and not a valid command, delete it
        if message.author != bot.user:
            await message.delete()

    # If the message is outside the designated channel, process it normally
    else:
        await bot.process_commands(message)





@bot.command(name='usage')
async def usage_command(ctx):
    if ctx.channel.id != 1188603066535129129:
        return
    help_message = (
        "**Search Command**\n"
        "Usage: `!search <query>`\n"
        "Search for movies based on various criteria. You can include any combination of the following parameters, "
        "but not `title` and `actor` at the same time:\n"
        "- `title`: Search by movie title (e.g. `title:Inception`). Accounts for minor spelling mistakes.\n"
        "- `actor`: Search by actor name (e.g. `actor:Leonardo DiCaprio`). Accounts for minor spelling errors.\n"
        "- `year`: Filter by release year or range (e.g. `year:2010` or `year:2000-2010`).\n"
        "- `duration`: Filter by movie duration in minutes (e.g. `duration:90-120`).\n"
        "- `rating`: Filter by movie rating (e.g. `rating:8.5` or `rating:7.5-9.0`).\n"
        "- `votes`: Filter by the number of votes (e.g. `votes:100K-1M`).\n\n"
        "When a soft condition such as `title` or `actor` is included, the top 5 closest matches within the set of met hard conditions "
        "(year, duration, rating, votes) will be returned. If only hard conditions are supplied, then the five movies with the highest votes that meet these conditions will be returned.\n\n"
        "Example: `!search year:2010 duration:90-120 rating:8.5-9.0`\n"
        "This command will list the top 5 highest voted movies released in 2010, lasting between 90 to 120 minutes, and having a rating between 8.5 to 9.0.\n\n"
        "This message will delete itself in 10 seconds."
    )
    response = await ctx.send(help_message)
    await ctx.message.delete()
    await asyncio.sleep(10)
    await response.delete()
# Run the bot
bot.run(os.environ["DISCORD_TOKEN"])
