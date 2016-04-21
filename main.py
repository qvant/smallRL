import libtcodpy as libtcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 45

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

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

def handle_keys():
	global playerx, playery, fov_recompute
	
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
		fov_recompute = True

	elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
		player.move(0, 1)
		fov_recompute = True
 
	elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
		player.move(-1, 0)
		fov_recompute = True

	elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
		player.move(1, 0)
		fov_recompute = True

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
		
class Tile:
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None:
			block_sight = blocked
		self.block_sight = block_sight
		self.explored = False
		
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
 
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1
			room_no = Object(new_x, new_y, chr(65+num_rooms), libtcod.white)
			objects.insert(0, room_no) #draw early, so monsters are drawn on top
	
def render_all():
	global color_light_wall
	global color_light_ground
	global fov_recompute
	
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
player.x = 25
player.y = 23
npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, '@', libtcod.yellow)
objects = [npc, player]

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

fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
	for x in range(MAP_WIDTH):
		libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
		


while not libtcod.console_is_window_closed():	
	
	render_all()
	
	libtcod.console_flush()
	
	for object in objects:
		object.clear()
		
	#handle keys and exit game if needed
	exit = handle_keys()
	if exit:
		break