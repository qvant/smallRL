import libtcodpy as libtcod
import math
import textwrap 

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 43

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

MAX_ROOM_MONSTERS = 3

MAX_ROOM_ITEMS = 2

INVENTORY_WIDTH = 50 

#sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

#The constants that define the message bar's position and size are: 
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

MAX_INVENTORY_ITEMS = 26

MAX_OPTIONS = MAX_INVENTORY_ITEMS

HEAL_AMOUNT = 4 

class Item:
	#an item that can be picked up and used.
	def __init__(self, use_function = None):
		self.use_function = use_function
	def pick_up(self):
		#add to the player's inventory and remove from the map
		if len(inventory) >= MAX_INVENTORY_ITEMS:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
	def use(self):
		#just call the "use_function" if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason
			
class Rect:
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.x2 = x + w
		self.y1 = y
		self.y2 = y + h
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
	def intersect(self, other):
		# return true if rectanges intersected
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

def create_room(room):
	global map
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
			
def create_h_tunnel(x1, x2, y):
	global map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def create_v_tunnel(y1, y2, x):
	global map
	#vertical tunnel
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def get_names_under_mouse():
	global mouse
	
	#return a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)  #join the names, separated by commas
	return names.capitalize()
		
def handle_keys():
	global playerx, playery, fov_recompute, key
	
	#key = libtcod.console_check_for_keypress()  #real-time
	#key = libtcod.console_wait_for_keypress(True)  #turn-based

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'  #exit game
	
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP:
			player_move_or_attack(0, -1)
			fov_recompute = True

		elif key.vk == libtcod.KEY_DOWN:
			player_move_or_attack(0, 1)
			fov_recompute = True
	 
		elif key.vk == libtcod.KEY_LEFT:
			player_move_or_attack(-1, 0)
			fov_recompute = True

		elif key.vk == libtcod.KEY_RIGHT:
			player_move_or_attack(1, 0)
			fov_recompute = True
		else:
			#test for other keys
			key_char = chr(key.c)
			
			if key_char == 'g':
				#pick up an item
				for object in objects:  #look for an item in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			elif key_char == 'i':
				#show the inventory
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
			return 'didnt-take-turn'

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, color, name = '', blocks = False, fighter = None, ai = None, item = None):
		self.x = x
		self.y = y
		self.char = char
		self.color = color
		self.name = name
		self.blocks = blocks
		self.fighter = fighter
		if self.fighter:
			#let the fighter component know who owns it
			self.fighter.owner = self
			
		self.ai = ai
		if self.ai:
			#let the ai component know who owns it
			self.ai.owner = self
		self.item = item
		if self.item:
			self.item.owner = self
 
	def move(self, dx, dy):
		#move by the given amount
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
 
	def draw(self):
		if libtcod.map_is_in_fov(fov_map, self.x, self.y):
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
	
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)

		#normalize it to length 1 (preserving direction), then round it and
		#convert to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
		
	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
		
	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile.
		global objects
		objects.remove(self)
		objects.insert(0, self)
		
class Tile:
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None:
			block_sight = blocked
		self.block_sight = block_sight
		self.explored = False
		
class Fighter:
	#combat-related properties and methods (monster, player, NPC).
	def __init__(self, hp, defense, power, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.death_function = death_function
	def take_damage(self, damage):
		#apply damage if possible
		if damage > 0:
			self.hp -= damage
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)
	def attack(self, target):
		#a simple formula for attack damage
		damage = self.power - target.fighter.defense
		
		if damage > 0:
			#make the target take some damage
			message( self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.fighter.take_damage(damage)
		else:
			message (self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
	def heal(self, amount):
		#heal by the given amount, without going over the maximum
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp

		
class BasicMonster:
	#AI for a basic monster.
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			message( 'The ' + self.owner.name + ' growls!')
			#move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)
		
def place_objects(room):
	#place monsters
	#choose random number of monsters
	num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
	
	for i in range(num_monsters):
		#choose random spot for this monster
		x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
		y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
		
		if not is_blocked(x, y):
		
			if libtcod.random_get_int(0, 0, 100) < 80:  #80% chance of getting an orc
				#create an orc
				fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'o', libtcod.desaturated_green, 'orc', True, fighter_component, ai_component)
			else:
				#create a troll
				fighter_component = Fighter(hp=16, defense=1, power=4, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'T', libtcod.darker_green, 'troll', True, fighter_component, ai_component)
				
			objects.append(monster)
	#place items
	num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)
	
	for i in range(num_items):
		#choose random spot for this item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			#create a healing potion
			item_component = Item(use_function=cast_heal)
			item = Object(x, y, '!', name = 'healing potion', color = libtcod.violet, item=item_component)
			
			objects.append(item)
			item.send_to_back()  #items appear below other objects
		

def is_blocked(x, y):
	#first test the map tile
	if map[x][y].blocked:
		return True
		
	#now check for any blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False

def player_move_or_attack(dx, dy):
	global fov_recompute
	
	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy
	#try to find an attackable object there
	target = None
	for object in objects:
		if object.x == x and object.y == y and object.fighter:
			target = object
			break
	
	#attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True
	
def make_map():
	global map
	
	#fill map with "unblocked" tiles
	map = [[Tile(True)
		for y in range(MAP_HEIGHT)]
			for i in range(MAP_WIDTH)]
	#room1 = Rect(20, 15, 10, 15)
	#room2 = Rect(50, 15, 10, 15)
	#create_room(room1)
	#create_room(room2)
	#create_h_tunnel(25, 55, 23)
	rooms = []
	num_rooms = 0
	for i in range(MAX_ROOMS):
		width = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		height = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - width - 1 )
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - height - 1 )
		
		#"Rect" class makes rectangles easier to work with
		new_room = Rect(x, y, width, height)
		#run through the other rooms and see if they intersect with this one
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		if not failed:
			#this means there are no intersections, so this room is valid
			
			#"paint" it to the map's tiles
			create_room(new_room)
			
			#center coordinates of new room, will be useful later
			(new_x, new_y) = new_room.center()
			
			if num_rooms == 0:
				#this is the first room, where the player starts at
				player.x = new_x
				player.y = new_y
			else:
				#all rooms after the first:
				#connect it to the previous room with a tunnel
				
				#center coordinates of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				#draw a coin (random number that is either 0 or 1)
				if libtcod.random_get_int(0, 0, 1) == 1:
					#first move horizontally, then vertically
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#first move vertically, then horizontally
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
				#firsr room always safe
				#add some contents to this room, such as monsters
				place_objects(new_room)
 
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1
			room_no = Object(new_x, new_y, chr(65+num_rooms), libtcod.white, 'room number')
			objects.insert(0, room_no) #draw early, so monsters are drawn on top
	
	
def player_death(player):
	#the game ended!
	global game_state
	message( 'You died!', libtcod.red)
	game_state = 'dead'
	
	#for added effect, transform the player into a corpse!
	player.char = '%'
	player.color = libtcod.dark_red
 
def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be
	#attacked and doesn't move
	message( monster.name.capitalize() + ' is dead!', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
	
def render_all():
	global color_light_wall
	global color_light_ground
	global fov_recompute
	global game_msgs
	
	if fov_recompute:
		#recompute FOV if needed (the player moved or something)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			wall = map[x][y].block_sight
			visible = libtcod.map_is_in_fov(fov_map, x, y)
			if not(visible):
				#if it's not visible right now, the player can only see it if it's explored
				if map[x][y].explored:
					#it's out of the player's FOV
					if wall:
						if not(old_map_style):
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET )
						else:
							libtcod.console_put_char_ex(con, x, y, '#', libtcod.grey, libtcod.black)
					else:
						if not(old_map_style):
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET )
						else:
							libtcod.console_put_char_ex(con, x, y, '.', libtcod.grey, libtcod.black)
			else:
				if wall:
					if not(old_map_style):
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
					else:
						libtcod.console_put_char_ex(con, x, y, '#', libtcod.white, libtcod.black)
				else:
					if not(old_map_style):
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
					else:
						libtcod.console_put_char_ex(con, x, y, '.', libtcod.white, libtcod.black)
				map[x][y].explored = True
	#draw all objects in the list, except the player. we want it to
	#always appear over all other objects! so it's drawn later.
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
	#show the player's stats
	#libtcod.console_set_default_foreground(con, libtcod.white)
	#libtcod.console_print_ex(0, 1, SCREEN_HEIGHT - 2, libtcod.BKGND_NONE, libtcod.LEFT,
    #    'HP: ' + str(player.fighter.hp) + '/' + str(player.fighter.max_hp))
	#prepare to render the GUI panel
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
 
	#show the player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
        libtcod.light_red, libtcod.darker_red)
	
	#display names of objects under the mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	
	#print the game messages, one line at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
    #blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
	
		
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)
	
	#render the background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
	#finally, some centered text with the values
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
        name + ': ' + str(value) + '/' + str(maximum))
	
	
def message(new_msg, color = libtcod.white):
	global game_msgs
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		#add the new line as a tuple, with the text and the color
		game_msgs.append((line, color))
	

def menu(header, options, width):
	if len(options) > MAX_OPTIONS: raise ValueError('Cannot have a menu with more than 26 options.')
	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	height = len(options) + header_height
	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)
	
	#print the header, with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	# 0.7 background transparacy
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None

def inventory_menu(header):
	#show a menu with each item of the inventory as an option
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = [item.name for item in inventory]
	
	index = menu(header, options, INVENTORY_WIDTH)
	#if an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item
	
def cast_heal():
	#heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', libtcod.red)
		return 'cancelled'

	message('Your wounds start to feel better!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)
	
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)

con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

#For a real-time roguelike, you wanna limit the speed of the game (frames-per-second or FPS). If you want it to be turn-based, ignore this line. (This line will simply have no effect if your game is turn-based.) 
libtcod.sys_set_fps(LIMIT_FPS)

playerx = SCREEN_WIDTH/2
playery = SCREEN_HEIGHT/2

game_state = 'playing'
player_action = None

fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
player = Object(MAP_WIDTH/2, MAP_HEIGHT/2, '@', libtcod.white, 'player', blocks = True, fighter = fighter_component)
player.x = 25
player.y = 23
#npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, '@', libtcod.yellow)
#objects = [npc, player]
objects = [ player]

color_dark_wall = libtcod.Color(0, 0, 100)
color_dark_ground = libtcod.Color(50, 50, 150)

color_light_wall = libtcod.Color(130, 110, 50)
color_light_ground = libtcod.Color(200, 180, 50)

# TODO: make choice
global old_map_style
old_map_style = False

global fov_recompute
fov_recompute = True



make_map()

#create the FOV map, according to the generated map
fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
	for x in range(MAP_WIDTH):
		libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
		
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

#create the list of game messages and their colors, starts empty
global game_msgs
game_msgs = []

inventory = []

#a warm welcoming message!
message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', libtcod.red)

mouse = libtcod.Mouse()
key = libtcod.Key()

while not libtcod.console_is_window_closed():	
	
	libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
	render_all()
	
	libtcod.console_flush()
	
	for object in objects:
		object.clear()
		
	#handle keys and exit game if needed
	player_action = handle_keys()
	if player_action == 'exit':
		break
	#let monsters take their turn
	if game_state == 'playing' and player_action != 'didnt-take-turn':
		for object in objects:
			if object.ai:
				object.ai.take_turn()
				

