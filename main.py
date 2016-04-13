import libtcodpy as libtcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 45

def handle_keys():
	global playerx, playery
	
	#key = libtcod.console_check_for_keypress()  #real-time
	key = libtcod.console_wait_for_keypress(True)  #turn-based

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
	elif key.vk == libtcod.KEY_ESCAPE:
		return True  #exit game
	
	#movement keys
	if libtcod.console_is_key_pressed(libtcod.KEY_UP):
		player.move(0, -1)

	elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
		player.move(0, 1)
 
	elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
		player.move(-1, 0)

	elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
		player.move(1, 0)

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, color):
		self.x = x
		self.y = y
		self.char = char
		self.color = color
 
	def move(self, dx, dy):
		#move by the given amount
		if not(map[self.x + dx][self.y + dy].blocked):
			self.x += dx
			self.y += dy
 
	def draw(self):
		#set the color and then draw the character that represents this object at its position
		libtcod.console_set_default_foreground(con, self.color)
		libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
 
	def clear(self):
		#erase the character that represents this object
		if not(old_map_style):
			libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
		#else:
		#	if map[self.x][self.y].block_sight:
		#		libtcod.console_put_char_ex(con, self.x, self.y, '.', libtcod.white, black.black)
		
class Tile:
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None:
			block_sight = blocked
		self.block_sight = block_sight
		
def make_map():
	global map
	
	#fill map with "unblocked" tiles
	map = [[Tile(False)
		for y in range(MAP_HEIGHT)]
			for i in range(MAP_WIDTH)]
	map[30][22].blocked = True
	map[30][22].block_sight = True
	map[50][22].blocked = True
	map[50][22].block_sight = True
	
def render_all():
	global color_light_wall
	global color_light_ground
	
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			wall = map[x][y].block_sight
			if wall:
				if not(old_map_style):
					libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET )
				else:
					libtcod.console_put_char_ex(con, x, y, '#', libtcod.white, libtcod.black)
			else:
				if not(old_map_style):
					libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET )
				else:
					libtcod.console_put_char_ex(con, x, y, '.', libtcod.white, libtcod.black)
	#draw all objects in the list
	for object in objects:
		object.draw()
	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
		
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)

con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

#For a real-time roguelike, you wanna limit the speed of the game (frames-per-second or FPS). If you want it to be turn-based, ignore this line. (This line will simply have no effect if your game is turn-based.) 
libtcod.sys_set_fps(LIMIT_FPS)

playerx = SCREEN_WIDTH/2
playery = SCREEN_HEIGHT/2

player = Object(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, '@', libtcod.white)
npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, '@', libtcod.yellow)
objects = [npc, player]

color_dark_wall = libtcod.Color(0, 0, 100)
color_dark_ground = libtcod.Color(50, 50, 150)

# TODO: make choice
global old_map_style
old_map_style = False

make_map()

while not libtcod.console_is_window_closed():	
	
	render_all()
	
	libtcod.console_flush()
	
	for object in objects:
		object.clear()
		
	#handle keys and exit game if needed
	exit = handle_keys()
	if exit:
		break