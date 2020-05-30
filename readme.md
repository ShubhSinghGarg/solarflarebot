## Solar Flare Bot
Solar Flare bot is a discord bot written in Python which hosts several party game adaptations to keep you at home during the pandemic.

### Available Games
Currently, two games are available:
* Monikers (accessed via prefix `\m`): http://www.monikersgame.com/
* Wavelength (accessed via prefix `\w`): https://www.wavelength.zone/

Currently, the implementation of Monikers requires participating players to contribute to the character pool manually instead of having a fixed pool. In the case of wavelength, questions/prompts are stored in a json file in the `data` folder.

*Monikers is designed by Alex Hague and Justin Vickers. Wavelength is designed by Wolfgang Warsch, Alex Hague, and Justin Vickers. All rights are reserved by the respective designers/owners. Please support them and purchase the physical copy if you like the games!*

### Files and Folders
`src`: Contains the source code for the bot (`solarflarebot.py`) and the /env file needed to run the bot.

`data`: Contains files for game questions and narration.

## How-tos  
Currently Solar Flare bot is not publicly hosted anywhere. To use the bot and play with your friends, you need to host it by yourself.

### Dependency
Solar Flare bot is implemented using the `discord.py` library and thus installation of the package is required to run the bot. Refer [here](https://discordpy.readthedocs.io/en/latest/intro.html) for instructions on how-to-install.

### Running The Bot
* You first need to create your own discord bot and invite it to your server. Refer [here](https://discordpy.readthedocs.io/en/latest/discord.html) for instructions on creating your own bot.
* Clone this repository and rename `src/sampleenv` to `src/.env`. This is the environment file that will be read by the script.
* Replace the corresponding field in `src/.env` with the Token and your server name you acquired from the previous steps.
* Run the bot locally by using the `python` command and you should be able to interact with the bot through your server!

## Updates
### Future Updates
### Changelog
