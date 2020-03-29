from loguru import logger
import sys
import os
import discord
from discord import Guild, CategoryChannel, VoiceChannel
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands import Bot
from threading import Timer
import time
import asyncio

TOKEN_FILE = 'TOKEN'
PREFIX = '/'
KEEP_ALIVE_TIME = 5


class ChannelCreator(Bot):
	def __init__(self, prefix='/', file_path='./', log_path='./', **options):
		super().__init__(command_prefix=prefix, **options)
		log_format = '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> <level>{level}: {message}</level>'
		logger.remove()
		logger.add(sys.stdout, format=log_format, colorize=True)
		log_file_name = 'log_{time:YYYY-MM-DD}.log'
		log_file = os.path.join(log_path, log_file_name)
		logger.add(log_file, format=log_format, rotation='00:00', compression='zip', colorize=True)
		self.logger = logger
		self.logger.info('Starting bot...')
		self.file_path = file_path
		self.token = self.get_token()
		self.command_prefix = prefix
		self.created_channels = dict()  # channel_id: check_time

	@logger.catch
	def get_token(self):
		token_file_path = os.path.join(self.file_path, TOKEN_FILE)
		self.logger.debug(f'Reading token file ({token_file_path})...')

		token = None
		with open(token_file_path, 'r') as token_file:
			token = token_file.readline().strip()

		assert token is not None and len(token) == 59
		self.logger.debug(f'Token: {token}')
		return token

	@logger.catch
	async def delete_channel_if_empty(self, channel: VoiceChannel) -> bool:
		await asyncio.sleep(KEEP_ALIVE_TIME)
		if not time.time() >= self.created_channels[channel.id]:
			return False
		self.logger.debug(f'Checking if channel "{channel.name}" has to be removed in "{channel.guild.name}"')
		connected_users = len(channel.members)
		if connected_users == 0:
			self.logger.debug(f'Channel empty, deleting it...')
			await channel.delete()
			self.logger.debug(f'Channel "{channel.name}" deleted')
			if channel.category is not None:
				time.sleep(1)
				await self.delete_category_if_empty(channel.category)
			return True
		else:
			self.logger.debug(f'Channel "{channel.name}" is not empty')
			self.schedule_channel_check(channel)
			return False

	@logger.catch
	async def delete_category_if_empty(self, category: CategoryChannel):
		self.logger.debug(f'Checking if category "{category.name}" has to be removed in "{category.guild.name}"')
		channels_count = len(category.channels)
		if channels_count == 0:
			self.logger.debug(f'Category empty, deleting it...')
			await category.delete()
			self.logger.debug(f'Category "{category.name}" deleted')
		else:
			self.logger.debug(f'Category "{category.name}" is not empty')

	@logger.catch
	async def create_category(self, guild: Guild, name: str):
		self.logger.debug(f'Creating category "{name}"...')
		assert guild is not None
		assert name is not None
		categories_names = [category.name for category in guild.categories]
		if name not in categories_names:
			new_category = await guild.create_category(name)
			self.logger.debug(f'Created "{name}" category in "{guild.name}"')
			return new_category
		else:
			self.logger.warning(f'"{name}" category already exists in "{guild.name}"')
			for category in guild.categories:
				if category.name == name:
					return category

	@logger.catch
	def schedule_channel_check(self, channel: VoiceChannel):
		self.logger.debug(f'Scheduling "{channel.name}" channel check...')
		asyncio.run_coroutine_threadsafe(self.delete_channel_if_empty(channel), self.loop)
		self.logger.debug(f'"{channel.name}" channel check scheduled')

	@logger.catch
	async def create_voice_channel(self, guild: Guild, name: str, category_name: str = None):
		assert guild is not None
		assert name is not None
		if category_name is not None:
			self.logger.debug(f'Creating "{name}" voice channel in "{guild.name}" under category "{category_name}"')
			categories_names = [category.name for category in guild.categories]
			category = await self.create_category(guild, category_name)
			category_channels_names = [channel.name for channel in category.channels]
			# TODO: check if channel already exists
			voice_channel = await guild.create_voice_channel(name, category=category)
		else:
			self.logger.debug(f'Creating "{name}" voice channel in "{guild.name}"')
			voice_channel = await guild.create_voice_channel(name)
		self.created_channels[voice_channel.id] = time.time() + KEEP_ALIVE_TIME
		self.schedule_channel_check(voice_channel)
		return voice_channel


bot = ChannelCreator()


@bot.event
async def on_ready():
	bot.logger.info(f'Bot ready:   '
					 f'Client: {bot.user}   '
					 f'Prefix: "{PREFIX}"')


@bot.command(pass_context=True)
async def new_ch(ctx: Context, ch_name: str, *args):
	guild = ctx.guild
	author = ctx.author
	category = None
	if len(args) > 0:
		category = args[0]
	bot.logger.debug(f'"new_ch {ch_name}" from "{author}" in "{guild}"')
	bot.logger.debug(f'Creating "{ch_name}" voice channel...')
	await bot.create_voice_channel(guild, ch_name, category)

bot.run(bot.token)
