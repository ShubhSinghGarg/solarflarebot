import os
import re
import copy
import random
import asyncio
import json
from dotenv import load_dotenv
from string import Template

import discord
from discord import ChannelType as ctype
from discord.ext import commands

#### BOT LEVEL VARIABLES ####
# Environments
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
PREFIX = os.getenv('BOT_PREFIX')

# Initialize client
bot = commands.Bot(command_prefix=PREFIX)

#### COMMONS ####

### GLOBAL GAME VARIABLES ###
session_default = {
    'game_type': 'X',
    'game_state': 0, # 1: Initialization + Name Gathering | 2-3-4: Round 1-2-3 | 0: Game inactive
    'current_team': 'B',
    'scores': {'A': 0, 'B': 0},
    'can_answer': False,
    'current_player': None,  

    # Teams
    'player_list': set([]) # List of (user id, username, team, turn)
}

game_name = {
    'M': 'Monikers',
    'W': 'Wavelength'
}

session = copy.deepcopy(session_default)

### HELPER FUNCTIONS ###
async def GetSession():
    serializableSession = {}
    for key, value in session.items():
        if isinstance(value, set):
            serializableSession[key] = list(value)
        else:
            serializableSession[key] = value

    return serializableSession

async def ResetGlobal():
    global session
    session = copy.deepcopy(session_default)

## MESSAGING ##
async def PaddedSend(ctx, message, front=0, back=0):
    await asyncio.sleep(front)
    await ctx.send(message)
    await asyncio.sleep(back)

async def DoubleSend(ctx, message, front=0, back=0):
    await asyncio.sleep(front)
    await bot.get_user(session['current_player']).send(message)
    await ctx.send(message)
    await asyncio.sleep(back)

## PLAYER STUFF ##

# Join game, return a boolean for success flag
async def JoinGame(ctx):
    if (ctx.author.id, ctx.author.name, None, False) in session['player_list']:
        await PaddedSend(ctx, f'''Player {ctx.author.name} has already joined though?''')
        return False
    else:
        session['player_list'].add((ctx.author.id, ctx.author.name, None, False))
        await PaddedSend(ctx, f'''Player {ctx.author.name} joined the {game_name[session['game_type']]} session!''')
        return True

# Leave game, return a boolean for success flag
async def LeaveGame(ctx):
    if (ctx.author.id, ctx.author.name, None, False) in session['player_list']:
        session['player_list'].remove((ctx.author.id, ctx.author.name, None, False))
        await PaddedSend(ctx, f'''You're leaving {ctx.author.name}? Well then...''')
        return True
    else:
        await PaddedSend(ctx, f'''You haven't joined yet though, {ctx.author.name}?''')
        return False

# Randomly assign teams to player and set all turn to False
async def AssignTeams():
    shuffledlist = random.sample(list(session['player_list']), len(session['player_list']))
    session['player_list'] = set([(player[0], player[1], ('A' if len(shuffledlist) // 2 <= idx else 'B'), False) for idx, player in enumerate(shuffledlist)])

# Display playerlist
async def DisplayPlayers(ctx, readycondition):
    list_message = '''
        The people who's currently playing are: \n {}
    '''.format('\n'.join(
        [f'''{idx+1}. {name[1]}{': Ready' if(readycondition(name)) else ''}''' for idx, name in enumerate(list(session['player_list']))]))
    await PaddedSend(ctx, list_message)

# Send teams
async def DisplayTeams(ctx):
    team_a = [player for player in session['player_list'] if player[2] == 'A']
    team_b = [player for player in session['player_list'] if player[2] == 'B']

    copy_a = '''Team A: \n {}'''.format('\n'.join([f'{idx+1}. {player[1]}' for idx, player in enumerate(team_a)]))
    copy_b = '''Team B: \n {}'''.format('\n'.join([f'{idx+1}. {player[1]}' for idx, player in enumerate(team_b)]))

    await PaddedSend(ctx, copy_a + '\n' + copy_b)

# Get the next player without turn
async def PlayerCandidates():
    return [p for p in session['player_list'] if ((p[3] == False) and (p[2] == session['current_team']))]

# Change current player, return name
async def ChangeCurrentPlayer(ctx):
    candidates = await PlayerCandidates()
    
    # Check if all answered, if so then reset
    if len(candidates) == 0: 
        session['player_list'] = set([(p[0], p[1], p[2], False) for p in session['player_list']])
        candidates = await PlayerCandidates()

    # Change next player
    next_player = sorted(candidates)[0]
    session['current_player'] = next_player[0]
    
    # Mark turn
    session['player_list'].remove(next_player)
    session['player_list'].add((next_player[0], next_player[1], next_player[2], True))

    return next_player

### CHECKS ###
def CheckChannel(channeltype, exclusion=False):
    def predicate(ctx):
        return (not exclusion) == (ctx.channel.type in channeltype)
    return commands.check(predicate)

def CheckState(game_type, game_state, exclusion=False):
    def predicate(ctx):
        return (session['game_type'] == game_type) and ((not exclusion) == (session['game_state'] in game_state))
    return commands.check(predicate)    

def CheckPlayer(team=False):
    def predicate(ctx):
        player_ids = []

        if not team: # Just check player currently joining
            player_ids = [player[0] for player in session['player_list']]
        else: # Check currently playing team
            player_ids = [player[0] for player in session['player_list'] if player[2] == session['current_team']]
        

        return (ctx.author.id in player_ids)
    return commands.check(predicate)    

#### MONIKERS ####

### GLOBAL GAME VARIABLES ###
#mon_qs = json.load(open(os.path.dirname(__file__) + "/../data/monQuestions.json"))
mon_copies = json.load(open(os.path.dirname(__file__) + "/../data/monCopy.json"))

mon_default = {
     # Configurables
    'game_type': 0, # 0: No description | 1: With description 
    'name_quota': 5, # 3 is the bare minimum man
    'round_length': 75,
    'round_multiplier': 2,
    'streak_multiplier': 0.25,
    'max_streak': 5,
    'current_streak': 0,

    # Questions
    'current_name': None,
    'name_list': set([]), # List of tuple (name:string, user id, status:bool)
}

mon_session = copy.deepcopy(mon_default)

### COPIES ###
mon_round_instruction = mon_copies['round_instructions']
mon_streak_messages = mon_copies['streak_messages']
mon_rules = Template("\n".join(mon_copies['rules'])).substitute(rlength=mon_session['round_length'])
mon_init_message = Template("\n".join(mon_copies['init'])).substitute(prefix=PREFIX)
mon_join_message = Template("\n".join(mon_copies['join'])).substitute(prefix=PREFIX, quota=mon_session['name_quota'])

### HELPER FUNCTIONS ###
async def ResetMoniker():
    await ResetGlobal()
    global mon_session
    mon_session = copy.deepcopy(mon_default)

# Convert all sets to list so they can be dumped as JSON
async def GetMonSession():
    serializableSession = {
        'global': {},
        'moniker': {}
    }
    serializableSession['global'] = await GetSession()

    for key, value in mon_session.items():
        if isinstance(value, set):
            serializableSession['moniker'][key] = list(value)
        else:
            serializableSession['moniker'][key] = value

    return serializableSession

# Change currently guessed name and inform currently explaining player
async def ChangeName(new_name):
    mon_session['current_name'] = new_name
    current_player = bot.get_user(session['current_player'])
    await current_player.send(f'''Your next word is: {new_name[0]}''')

# Get one names that hasn't been answered yet
async def GetUnansweredName():
    unanswereds = [(name[0], name[1]) for name in mon_session['name_list'] if name[2] == False]
    
    # Check if all answered
    if len(unanswereds) > 1:
        next_name = random.choice([name for name in unanswereds if name != mon_session['current_name']])
        return next_name
    elif len(unanswereds) == 1:
        return unanswereds[0]
    else:
        return None

# Scoring Logic
async def MonikerScore():
    current_round = session['game_state'] - 1
    basic_score = 1000 * (1 + (current_round * mon_session['round_multiplier']))    
    
    streak_score = 0
    
    # Start streak if behind or streak has already started
    if min(session['scores'].values()) == session['scores'][session['current_team']] or mon_session['current_streak'] > 0:
        streak_score = basic_score * mon_session['current_streak'] * mon_session['streak_multiplier']
        mon_session['current_streak'] = min(mon_session['max_streak'], mon_session['current_streak'] + 1)
    
    session['scores'][session['current_team']] = session['scores'][session['current_team']] + basic_score + streak_score

    return basic_score + streak_score

# Advance the game to next round if any
async def AdvanceRound(ctx):
    session['game_state'] = session['game_state'] + 1

    if  session['game_state'] <= 4:
            # Reset round states and remove 1 name per player
            mon_session['name_list'] = set([(np[0], np[1], False) for np in mon_session['name_list']])
            mon_session['name_list'] = set(random.sample([np for np in mon_session['name_list']], len(mon_session['name_list']) - len(session['player_list'])))

            await PaddedSend(ctx, f'''Type "{PREFIX}m go" to begin the next round.''')
    else:
        if session['scores']['A'] > session['scores']['B']:
            await PaddedSend(ctx, '''Team A wins! I guess I misjudged you guys.''')
        elif session['scores']['B'] > session['scores']['A']:
            await PaddedSend(ctx, '''Team B wins! That was a close game.''')
        else:
            await PaddedSend(ctx, '''It's a draw?''')

        await ResetMoniker()
         
### BOT COMMANDS ###
@bot.group(name='monikers')
async def _monikers(ctx):
    # Basic sanity checks
    if ctx.invoked_subcommand is None:
        await PaddedSend(ctx, 
f'''You must have mistyped your command.''')

# Aliases
@bot.command(name='mon')
async def m_mon(ctx):
    await _monikers.invoke(ctx)

@bot.command(name='m')
async def m_m(ctx):
    await _monikers.invoke(ctx)

# Priority commands, available in all game state
# 1. Debug
# 2. Help
# 3. Abort the game
# 4. List players
@_monikers.command(name='debug')
async def m_debug(ctx, *args):
    print(ctx, json.dumps(await GetMonSession(), sort_keys=True))

@_monikers.command(name='help')
async def m_help(ctx, *args):
    await ctx.send_help()

@_monikers.command(name='abort')
@CheckState('M', [0], exclusion=True)
@CheckChannel([ctype.text])
async def m_abort(ctx, *args):
    await ResetMoniker()
    await PaddedSend(ctx, 'You want to end it? ... well if you say so. Tell me if you changed your mind.')

@_monikers.command(name='playerlist')
@CheckState('M', [0], exclusion=True)
async def m_playerlist(ctx, *args):
    await DisplayPlayers(ctx, lambda x: len([np for np in mon_session['name_list'] if np[1] == x[0]]) >= mon_session['name_quota'])
    
# Pre-game - possible actions:
@_monikers.command(name='init')
@CheckState('X', [0])
@CheckChannel([ctype.text])
async def m_init(ctx, *args):
    await ResetMoniker()
    session['game_type'] = 'M'
    session['game_state'] = 1
    await PaddedSend(ctx, mon_init_message)

# Initialization state - possible actions:
# 1. Add yourself to the list of players
# 2. Remove yourself from the list of players
# 3. Add name to the pool
# 4. Remove name to the pool
# 5. List all the names you've inputted to the pool
# 6. Start the game IF AT LEAST THERE'S 4 PLAYERS AND ALL PLAYERS HAVE INPUTTED 5 NAMES
@_monikers.command(name='rules')
@CheckState('M', [1])
@CheckChannel([ctype.text, ctype.private])
async def m_rules(ctx):
    await PaddedSend(ctx.author, mon_rules)

@_monikers.command(name='join')
@CheckState('M', [1])
@CheckChannel([ctype.text])
async def m_join(ctx, *args):
    if await JoinGame(ctx):
        await PaddedSend(ctx.author, mon_join_message)

@_monikers.command(name='leave')
@CheckState('M', [1])
@CheckChannel([ctype.text])
async def m_leave(ctx, *args):
    if await LeaveGame(ctx):
        mon_session['name_list'] = set([np for np in mon_session['name_list'] if np[1] != ctx.author.id])

@_monikers.command(name='add')
@CheckState('M', [1])
@CheckPlayer()
@CheckChannel([ctype.private])
async def m_add(ctx, *, arg):
    # Check if already more than enough names
    if(len([np for np in mon_session['name_list'] if np[1] == ctx.author.id]) >= mon_session['name_quota']):
        await PaddedSend(ctx, f'''You've given me more than enough. Do you want me to remove some you've already mentioned?''')
        return

    # Fuckin preprocess omegalul
    name = arg.lower()
    name = re.sub(r'([^\s\w]|_)+', '', name)
    
    # Add to list of names if not exist yet
    if (name, ctx.author.id, False) not in mon_session['name_list']:
        mon_session['name_list'].add((name, ctx.author.id, False))
        await PaddedSend(ctx, f'''Very well, I added {name} to your list of names.''')
    else:
        await PaddedSend(ctx, f'''I already see {name} in your list, you might want to choose other names.''')

@_monikers.command(name='remove')
@CheckState('M', [1])
@CheckPlayer()
@CheckChannel([ctype.private])
async def m_remove(ctx, *, arg):
    # Add to list of names if not exist yet
    name = arg.lower()
    
    if (name, ctx.author.id, False) in mon_session['name_list']:
        mon_session['name_list'].remove((name, ctx.author.id, False))
        await PaddedSend(ctx, f'''So you changed your mind? I'll remove {name} from your list then.''')
    else:
        PaddedSend(ctx, f'''I don't see {name} here... you might want to add it instead.''')

@_monikers.command(name='listnames')
@CheckState('M', [1])
@CheckPlayer()
@CheckChannel([ctype.private])
async def m_listnames(ctx):
    list_names = [np[0] for np in mon_session['name_list'] if np[1] == ctx.author.id]
    list_message = '''
        Here's what you have so far: \n {}
    '''.format('\n'.join([f'{idx+1}. {np}' for idx, np in enumerate(list_names)]))
    await PaddedSend(ctx, list_message)

@_monikers.command(name='start')
@CheckState('M', [1])
@CheckPlayer()
@CheckChannel([ctype.text])
async def m_start(ctx, *args):
    player_count = len(session['player_list'])

    if (player_count >= 4) and (len(mon_session['name_list']) >= (player_count * mon_session['name_quota'])):
    # DEBUG: if (player_count >= 1) and (len(mon_session['name_list']) >= (player_count * mon_session['name_quota'])):    
        session['game_state'] = 2
        await AssignTeams()
        await DisplayTeams(ctx)
        await PaddedSend(ctx, f'Type "{PREFIX}m go" if you want me to start.')
    elif len(session['player_list']) < 1:
        await PaddedSend(ctx, '''I'm afraid we don't have enough people here...''')
    else:
        await PaddedSend(ctx, '''Wait... somebody hasn't given me enough names yet!''')

# MAIN GAME LOOP - possible actions:
# 1. Start the round
# 2. GUESSER: guess
# 3. EXPLAINER: skip                                                                               
@_monikers.command(name='go')
@commands.max_concurrency(1)
@CheckState('M', [2, 3, 4])
@CheckPlayer()
@CheckChannel([ctype.text])
async def m_go(ctx, *args):   
    # Change turn
    session['current_team'] = {'A':'B', 'B':'A'}[session['current_team']]
    await PaddedSend(ctx, 
f'''Round {session['game_state'] - 1}: Team {session['current_team']}
{random.choice(mon_round_instruction[str(session['game_state']-1)])}
Type "{PREFIX}m ? [answer]" to answer.''')
    
    # Get player and name
    next_player = await ChangeCurrentPlayer(ctx)
    await PaddedSend(ctx, f'The next player to explain is {next_player[1]}!')

    # Countdown
    await PaddedSend(ctx, 'Get ready. 3...', front=3)
    await PaddedSend(ctx, '2...', front=1)
    await PaddedSend(ctx, '1...', front=1)
    await PaddedSend(ctx, 'Go.', front=1)

    # Get name
    next_name = await GetUnansweredName()
    await ChangeName(next_name)

    # Countdown logic
    time_left = mon_session['round_length']
    session['can_answer'] = True
    mon_session['current_streak'] = 0

    for reminder in [30, 10, 5]:
        if time_left > reminder: 
            await DoubleSend(ctx, f'{reminder} more seconds!', front=time_left - reminder)
            time_left = reminder
    
    await(DoubleSend(ctx, '''And that's the end of the round. I ask you all to stop guessing now.''', front=time_left))   
    
    session['can_answer'] = False
    mon_session['current_name'] = None
    
    await PaddedSend(ctx, 
f'''CURRENT SCORE
# Team A: {session['scores']['A']} points
# Team B: {session['scores']['B']} points''')
    await PaddedSend(ctx, f'''Words left: {len([np for np in mon_session['name_list'] if np[2] == False])}''')
    
    # Check round end
    if await GetUnansweredName() == None:
        await AdvanceRound(ctx)
    else:
        await PaddedSend(ctx, 
'''Next is Team {}'s turn.
Are you ready? Type "{}m go" to start.'''.format({'A':'B', 'B':'A'}[session['current_team']], PREFIX))       

@_monikers.command(name='?')
@commands.max_concurrency(1, wait=True)
@CheckState('M', [2, 3, 4])
@CheckPlayer(team=True)
@CheckChannel([ctype.text])
async def m_guess(ctx, *, args):
    if session['can_answer'] and ctx.author.id != session['current_player']:
    # DEBUG: if session['can_answer']:
        # Send guess to explainer
        await bot.get_user(session['current_player']).send(f'Your team guessed {args}.')

        if args.lower() == mon_session['current_name'][0]:

            # Send message
            score = await MonikerScore()
            await PaddedSend(ctx, f'{args} is correct! {score} points!')            
            await bot.get_user(session['current_player']).send('''And that is correct.''')            


            if mon_session['current_streak'] > 0: await PaddedSend(ctx, mon_streak_messages[str(mon_session['current_streak'])])

            # Update status
            mon_session['name_list'].remove((mon_session['current_name'][0], mon_session['current_name'][1], False))
            mon_session['name_list'].add((mon_session['current_name'][0], mon_session['current_name'][1], True))

            # Go to next name
            next_name = await GetUnansweredName()
            if next_name == None:
                await PaddedSend(ctx, '''You've guessed all of the names. I will give you time to celebrate until the end of this round.''')
                session['can_answer'] = False
            else:
                await ChangeName(next_name)

@_monikers.command(name='skip')
@commands.max_concurrency(1, wait=True)
@commands.cooldown(1, 1)
@CheckState('M', [2, 3, 4])
@CheckPlayer(team=True)
@CheckChannel([ctype.private])
async def m_skip(ctx):
    # Go to next name
    if session['can_answer'] and ctx.author.id == session['current_player']:
        await PaddedSend(ctx, 'You skipped.')
        mon_session['current_streak'] = 0 # reset streak
        
        next_name = await GetUnansweredName()
        await ChangeName(next_name)

#### WAVELENGTH ####

### GLOBAL GAME VARIABLES ###
wav_qs = json.load(open(os.path.dirname(__file__) + "/../data/wavQuestions.json"))
wav_copies = json.load(open(os.path.dirname(__file__) + "/../data/wavCopy.json"))

wav_default = {
     # Configurables
    'target_score': 10,

    # Question
    'current_clue': 'PINEAPPLE PIZZA',
    'current_prompts': ('ETHICAL FOOD OR BEVERAGES', 'UNETHICAL FOOD OR BEVERAGES'),
    'current_target': 1,
    'current_position': 18,
    'question_list': set([(x[0], x[1]) for x in wav_qs]), # List of tuple (name:string, user id, status:bool)
}

wav_session = copy.deepcopy(wav_default)

### COPIES ###
wav_rules = "\n".join(wav_copies['rules'])

wav_init_message = Template("\n".join(wav_copies['init'])).substitute(prefix=PREFIX)
wav_score_message = wav_copies['score_message']

### HELPER FUNCTIONS ###
async def ResetWavelength():
    await ResetGlobal()
    global wav_session
    wav_session = copy.deepcopy(wav_default)

# Convert all sets to list so they can be dumped as JSON
async def GetWavSession():
    serializableSession = {
        'global': {},
        'wavelength': {}
    }
    serializableSession['global'] = await GetSession()

    for key, value in mon_session.items():
        if isinstance(value, set):
            serializableSession['wavelength'][key] = list(value)
        else:
            serializableSession['wavelength'][key] = value

    return serializableSession

## DRAWING ##
# Process sentence into array of acceptable words
async def ProcessSentence(width, sentence):
    pWords = []

    for word in sentence.split(' '):
        if len(word) <= (width - 4):
            pWords.append(word)
        else:
            x = word
            while len(x) > (width - 4):
                pWords.append(x[:width - 4])
                x = x[width - 4:] 
            pWords.append(x)

    return pWords
    
# Return a nice, boxed sentence
async def BoxedSentence(width, sentence):
    words = await ProcessSentence(width, sentence)

    arrays = [
        f''' {'_' * (width - 2)} ''',
        f'''|{' ' * (width - 2)}|'''
    ]
    cRow = ''
    for word in words:
        if len(cRow) + len(word) + 1 <= (width - 4):
            cRow = f'''{cRow} {word}'''.lstrip(' ')
        else:
            arrays.append(f'''| {cRow}{' ' * (width - 4 - len(cRow))} |''')
            cRow = word
    
    arrays.append(f'''| {cRow}{' ' * (width - 4 - len(cRow))} |''')
    arrays.append(f'''|{'_' * (width - 2)}|''')
    
    return arrays

# Return the 3 x 35 meter; [1-35]
async def Meter(arrow, answer, closed=True):
    meter = []

    meter.append(f''' {' ' * (arrow-1)}|{' ' * (35-arrow)} ''')
    meter.append(f''' {' ' * (arrow-1)}▼{' ' * (35-arrow)} ''')
    meter.append(f'''<{'.' * 10}{'o' * 5}{'●' * 2}{'▲' * 1}{'●' * 2}{'o' * 5}{'.' * 10}>''')

    if closed:
        meter.append(f'''<{'■' * 35}>''')
    else:
        row4 = [' '] * 35     
        row4[max(0,answer-2)] = '-'
        row4[min(34,answer)] = '-'
        row4[answer-1] = 'X'

        row4 = f''' {''.join(row4)} '''
        meter.append(row4)
    
    meter.append(f'''<.........[THE TRUTH METER].........>''')
    
    return meter

# Combine box and meter
async def FullDisplay(box1, box2, meter, boxprompt=[]):
    height = max(len(box1), len(box2), len(meter))

    display = []
    # Add answer if any
    for line in boxprompt:
        display.append(f'''{' ' * (len(box1[0])+1)}{line}''')

    # Pad stuff
    box1 = [(' ' * len(box1[0]))] * (height - len(box1)) + box1
    box2 = [(' ' * len(box2[0]))] * (height - len(box2)) + box2
    meter = [(' ' * len(meter[0]))] * (height - len(meter)) + meter
    display = display + [box1[i] + meter[i] + box2[i] for i in range(height)]

    return display

# Print the display
async def PrintDisplay(ctx, closed=True):    
    box1 = await BoxedSentence(15, wav_session['current_prompts'][0])
    box2 = await BoxedSentence(15, wav_session['current_prompts'][1])
    meter = await Meter(wav_session['current_position'], wav_session['current_target'], closed=closed)
    
    if wav_session['current_clue'] == None:
        boxprompt = []
    else:
        boxprompt = await BoxedSentence(35, wav_session['current_clue'])

    full = '\n'.join(await FullDisplay(box1, box2, meter, boxprompt=boxprompt))

    await PaddedSend(ctx, f'''```{full}```''')    

# Entire round initialization logic
async def QuestionPhase(ctx):
    session['game_state'] = 3
    session['current_team'] = {'A':'B', 'B':'A'}[session['current_team']]
    await PaddedSend(ctx, f'''Team {session['current_team']} turn!''')

    # Get player and name
    next_player = await ChangeCurrentPlayer(ctx)
    await PaddedSend(ctx, f'''{next_player[1]} is playing next; go check your direct message.''')

    # Get question, and target
    wav_session['current_prompts'] = random.choice(list(wav_session['question_list']))
    wav_session['current_target'] = random.randint(1, 35)
    wav_session['current_position'] = 18
    wav_session['current_clue'] = None  

    player = bot.get_user(next_player[0])
    await player.send('''Here is your question and the target position:''')
    await PrintDisplay(player, closed=False)

    # Get prompt from current player
    answered = False
    while not answered:
        await player.send('What prompt do you want to give for the question?')
        
        def check(m):
            return (m.author == player and m.channel.type == ctype.private)
        def checkYes(m):
            return check(m) and m.content.lower() in ('y', 'n')

        prompt = await bot.wait_for('message', check=check)
        await player.send(f'Is "{prompt.content}" okay? (Y/N)')
        msg = await bot.wait_for('message', check=checkYes)

        if msg.content.lower() == 'y':
            await player.send(f'Got it.')
            wav_session['current_clue'] = prompt.content.upper()
            answered = True
        else:
            await player.send(f'''You're going to revise your prompt then?''')
    
    # Print completed display to all
    await PaddedSend(ctx, '''Okay, here's the question: ''')
    await PrintDisplay(ctx, closed=True)
    await PaddedSend(ctx, 
f'''Adjust the meter by "{PREFIX}w +" and "{PREFIX}w -".
If you're happy with your answer, lock it in by using "{PREFIX}w lock"!''')

# Scoring phase
async def ScoringPhase(ctx):
    score = max(0, 5 - abs(wav_session['current_target'] - wav_session['current_position']))
    await PaddedSend(ctx, wav_score_message[str(score)])
    session['scores'][session['current_team']] = session['scores'][session['current_team']] + score

    # Print score
    await PaddedSend(ctx, 
f'''CURRENT SCORE
# Team A: {session['scores']['A']} points
# Team B: {session['scores']['B']} points''')

    # Check for end condition
    if session['scores'][session['current_team']] >= wav_session['target_score']:
        await PaddedSend(ctx,
f'''And that's the game! Congratulations team {session['current_team']}!
To play another session, type {PREFIX}w init.''')
        await ResetWavelength()
    else:
        await PaddedSend(ctx, f'''Game's not over, type {PREFIX}w go to continue.''')
        session['game_state'] = 2

### BOT COMMANDS ###
@bot.group(name='wavelength')
async def _wavelength(ctx):
    # Basic sanity checks
    if ctx.invoked_subcommand is None:
        await PaddedSend(ctx, 
f'''You must have mistyped your command.''')

# Aliases
@bot.command(name='wav')
async def w_wav(ctx):
    await _wavelength.invoke(ctx)

@bot.command(name='w')
async def w_w(ctx):
    await _wavelength.invoke(ctx)

# Priority commands, available in all game state
# 1. Debug
# 2. Help
# 3. Abort the game
# 4. List players
@_wavelength.command(name='debug')
async def w_debug(ctx, *args):
    print(ctx, json.dumps(await GetWavSession(), sort_keys=True))

@_wavelength.command(name='help')
async def w_help(ctx, *args):
    await ctx.send_help()

@_wavelength.command(name='abort')
@CheckState('W', [0], exclusion=True)
@CheckChannel([ctype.text])
async def w_abort(ctx, *args):
    await ResetWavelength()
    await PaddedSend(ctx, 'You want to end it? ... well if you say so. Tell me if you changed your mind.')

@_wavelength.command(name='playerlist')
@CheckState('W', [0], exclusion=True)
async def w_playerlist(ctx, *args):
    await DisplayPlayers(ctx, lambda x: True)
    
# Pre-game - possible actions:
@_wavelength.command(name='init')
@CheckState('X', [0])
@CheckChannel([ctype.text])
async def w_init(ctx, *args):
    await ResetWavelength()
    session['game_type'] = 'W'
    session['game_state'] = 1
    await PaddedSend(ctx, wav_init_message)

# Initialization state - possible actions:
# 1. Add yourself to the list of players
# 2. Remove yourself from the list of players
# 3. Start the game IF AT LEAST THERE'S 4 PLAYERS
@_wavelength.command(name='rules')
@CheckState('W', [1])
@CheckChannel([ctype.text, ctype.private])
async def w_rules(ctx):
    await PaddedSend(ctx.author, wav_rules)
    await PrintDisplay(ctx.author, closed=False)


@_wavelength.command(name='join')
@CheckState('W', [1])
@CheckChannel([ctype.text])
async def w_join(ctx, *args):
    await JoinGame(ctx)

@_wavelength.command(name='leave')
@CheckState('W', [1])
@CheckChannel([ctype.text])
async def w_leave(ctx, *args):
    await LeaveGame(ctx)

@_wavelength.command(name='start')
@CheckState('W', [1])
@CheckPlayer()
@CheckChannel([ctype.text])
async def w_start(ctx, *args):
    # DEBUG: if (len(session['player_list']) >= 4):
    if (len(session['player_list']) >= 1):    
        session['game_state'] = 2
        await AssignTeams()
        await DisplayTeams(ctx)
        
        # Start first round
        await w_go.invoke(ctx)
    else:
        await PaddedSend(ctx, '''I'm afraid we don't have enough people here...''')

## MAIN GAME LOOP ##
# 1. Start the round
# 2. GUESSER: +, -, lock                                                                               
@_wavelength.command(name='go')
@commands.max_concurrency(1)
@CheckState('W', [2])
@CheckPlayer()
@CheckChannel([ctype.text])
async def w_go(ctx, *args):   
    await QuestionPhase(ctx)


@_wavelength.command(name='+')
@commands.max_concurrency(1)
@CheckState('W', [3])
@CheckPlayer(team=True)
@CheckChannel([ctype.text])
async def w_plus(ctx, *, arg=1):
    if ctx.author.id != session['current_player']:
        wav_session['current_position'] = min(wav_session['current_position'] + int(arg), 35)
        await PrintDisplay(ctx)

@_wavelength.command(name='-')
@commands.max_concurrency(1)
@CheckState('W', [3])
@CheckPlayer(team=True)
@CheckChannel([ctype.text])
async def w_minus(ctx, *, arg=1):
    if ctx.author.id != session['current_player']:
        wav_session['current_position'] = max(wav_session['current_position'] - int(arg), 1)
        await PrintDisplay(ctx)

@_wavelength.command(name='lock')
@commands.max_concurrency(1)
@CheckState('W', [3])
@CheckPlayer(team=True)
@CheckChannel([ctype.text])
async def w_lock(ctx, *args):
    if ctx.author.id != session['current_player']:  
        def check(m):
            return (m.author == ctx.author and m.channel == ctx.channel)

        await PaddedSend(ctx, '''Are you 100% sure with your answer? (Y/N)''')
        msg = await bot.wait_for('message', check=check)

        if msg.content.lower() == 'y':
            await PaddedSend(ctx, 'Okay then, locking in!')
            await PaddedSend(ctx, '''Let's see if you've successful in guessing!''', back=2)
            await PaddedSend(ctx, '''*dramatic drumroll noises*''', back=2)
            await PrintDisplay(ctx, closed=False)
            
            await ScoringPhase(ctx)
        else:
            await PaddedSend(ctx, f'''Okay, but don't take too long!''')   

#### RUN BOT ####
bot.run(TOKEN)